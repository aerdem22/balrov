import time
import math
import threading
import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.executors import SingleThreadedExecutor
from sensor_msgs.msg import Image, Imu
from geometry_msgs.msg import WrenchStamped
from cv_bridge import CvBridge as ROS2CvBridge
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QImage


class Ros2Handler(QThread):
    """
    ROS 2 to UI bridge for Gazebo simulation mode.
    Drop-in replacement for MAVLinkHandler + CameraHandler + GPIOHandler.
    Emits the exact same signals the UI expects.
    """
    attitude_updated = pyqtSignal(float, float, float)
    depth_updated = pyqtSignal(float)
    battery_updated = pyqtSignal(float, float)
    arm_updated = pyqtSignal(bool)
    mode_updated = pyqtSignal(str)
    motors_updated = pyqtSignal(list)
    ping_updated = pyqtSignal(float)
    frame_ready = pyqtSignal(object)
    connected = pyqtSignal(bool)
    connection_lost = pyqtSignal()
    heartbeat_received = pyqtSignal()

    tether_updated = pyqtSignal(float)
    leak_detected = pyqtSignal(bool)
    emergency_triggered = pyqtSignal()

    recording_started = pyqtSignal(str)
    recording_stopped = pyqtSignal()
    fps_updated = pyqtSignal(float)

    MAX_SURGE = 10.0
    MAX_SWAY  = 10.0
    MAX_HEAVE = 7.0
    MAX_YAW   = 1.5

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._cv = ROS2CvBridge()
        self._node = None
        self._executor = None
        self._imu = None
        self._wrench = None
        self._depth = 0.0
        self._recording = False
        self._writer = None

    # ── QThread overrides ─────────────────────────────────────────────────
    def run(self):
        self._running = True
        try:
            rclpy.init()
        except Exception:
            pass

        self._node = Node("ui_bridge")
        self._node.create_subscription(
            Imu, "/balrov/sensors/imu", self._on_imu, 10)
        self._node.create_subscription(
            Image, "/balrov/front/image_raw", self._on_front, 10)
        self._node.create_subscription(
            Image, "/balrov/bottom/image_raw", self._on_bottom, 10)
        self._node.create_subscription(
            WrenchStamped, "/balrov/cmd/wrench", self._on_wrench, 10)

        self.connected.emit(True)
        self.heartbeat_received.emit()

        self._executor = SingleThreadedExecutor()
        self._executor.add_node(self._node)

        t = 0.0
        while self._running and rclpy.ok():
            self._executor.spin_once(timeout_sec=0.05)

            if self._imu:
                roll, pitch, yaw = self._imu
                heading = (math.degrees(yaw) % 360.0)
                self.attitude_updated.emit(heading, math.degrees(pitch), math.degrees(roll))

            self.depth_updated.emit(max(0.0, self._depth))

            if self._wrench:
                self.motors_updated.emit(self._wrench_to_motors(self._wrench))

            self.battery_updated.emit(85.0, 18.5)
            self.arm_updated.emit(True)
            self.mode_updated.emit("STABILIZE")
            self.ping_updated.emit(2.0)

            self.tether_updated.emit(0.0)
            self.leak_detected.emit(False)

            time.sleep(0.033)
            t += 0.033

        self._shutdown()

    # ── callbacks ─────────────────────────────────────────────────────────
    def _on_imu(self, msg):
        q = msg.orientation
        roll = math.atan2(
            2.0 * (q.w * q.x + q.y * q.z),
            1.0 - 2.0 * (q.x * q.x + q.y * q.y))
        pitch = math.asin(2.0 * (q.w * q.y - q.z * q.x))
        yaw = math.atan2(
            2.0 * (q.w * q.z + q.x * q.y),
            1.0 - 2.0 * (q.y * q.y + q.z * q.z))
        self._imu = (roll, pitch, yaw)
        lin = msg.linear_acceleration
        if lin.z != 0:
            self._depth = max(0.0, -lin.z / 9.80665)

    def _on_front(self, msg):
        try:
            cv_img = self._cv.imgmsg_to_cv2(msg, desired_encoding="bgr8")
            h, w, ch = cv_img.shape
            qimg = QImage(cv_img.data, w, h, ch * w, QImage.Format_BGR888).copy()
            self.frame_ready.emit(qimg)

            if self._recording and self._writer:
                self._writer.write(cv_img)
        except Exception:
            pass

    def _on_bottom(self, msg):
        pass

    def _on_wrench(self, msg):
        self._wrench = msg

    # ── motor calculation ─────────────────────────────────────────────────
    def _wrench_to_motors(self, wrench_msg):
        fx = abs(wrench_msg.wrench.force.x)
        fy = abs(wrench_msg.wrench.force.y)
        fz = abs(wrench_msg.wrench.force.z)
        tz = abs(wrench_msg.wrench.torque.z)

        surge_pct = min(100.0, fx / self.MAX_SURGE * 100.0)
        sway_pct  = min(100.0, fy / self.MAX_SWAY  * 100.0)
        heave_pct = min(100.0, fz / self.MAX_HEAVE * 100.0)
        yaw_pct   = min(100.0, tz / self.MAX_YAW   * 100.0)

        m1 = min(100.0, surge_pct * 0.5 + yaw_pct * 0.5)
        m2 = min(100.0, surge_pct * 0.5 + yaw_pct * 0.5)
        m3 = min(100.0, surge_pct * 0.5 + yaw_pct * 0.5)
        m4 = min(100.0, surge_pct * 0.5 + yaw_pct * 0.5)
        m5 = min(100.0, heave_pct)
        m6 = min(100.0, heave_pct)
        return [m1, m2, m3, m4, m5, m6]

    # ── commands (no-op for simulation, but keep interface) ──────────────
    def send_mode(self, mode_name):
        pass

    def send_arm(self, arm):
        pass

    def send_emergency_stop(self):
        pass

    def set_lumen(self, brightness):
        pass

    def trigger_emergency(self):
        self.emergency_triggered.emit()

    def start_recording(self):
        self._recording = True

    def stop_recording(self):
        self._recording = False
        if self._writer:
            self._writer.release()
            self._writer = None
        self.recording_stopped.emit()

    # ── shutdown ──────────────────────────────────────────────────────────
    def _shutdown(self):
        if self._executor:
            self._executor.shutdown()
        if self._node:
            self._node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        self.connected.emit(False)

    def stop(self):
        self._running = False
        self.quit()
        self.wait()
