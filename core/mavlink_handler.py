import time
import math
import logging
from PyQt5.QtCore import QThread, pyqtSignal

try:
    from pymavlink import mavutil
    MAVLINK_AVAILABLE = True
except ImportError:
    MAVLINK_AVAILABLE = False

log = logging.getLogger(__name__)

# ArduSub custom_mode → display string
MODE_MAP = {
    0:  "STABILIZE",
    1:  "ACRO",
    2:  "ALT_HOLD",
    3:  "AUTO",
    4:  "GUIDED",
    7:  "CIRCLE",
    9:  "SURFACE",
    16: "POSHOLD",
    19: "MANUAL",
    20: "MOTORDETECT",
    21: "SURFTRAK",
}

# UI button name → ArduSub custom_mode id
MODE_NAME_MAP = {
    "STABİL":     0,
    "MANUEL":    19,
    "OTONOM NAV": 3,
    "HAT TAKİBİ": 7,
}

# Seawater density (kg/m³) × g (m/s²) / 100  →  hPa per metre of depth
_SEA_DIVISOR   = 1025.0 * 9.80665 / 100.0   # ≈ 100.52
_FRESH_DIVISOR = 1000.0 * 9.80665 / 100.0   # ≈ 98.07
DEPTH_DIVISOR  = _SEA_DIVISOR                # change to _FRESH_DIVISOR for freshwater


class MAVLinkHandler(QThread):
    attitude_updated   = pyqtSignal(float, float, float)  # heading°, pitch°, roll°
    depth_updated      = pyqtSignal(float)                # metres
    battery_updated    = pyqtSignal(float, float)         # pct, voltage
    arm_updated        = pyqtSignal(bool)
    mode_updated       = pyqtSignal(str)
    motors_updated     = pyqtSignal(list)                 # [m1..m6] 0-100 %
    ping_updated       = pyqtSignal(float)                # ms round-trip
    connected          = pyqtSignal(bool)
    heartbeat_received = pyqtSignal()
    connection_lost    = pyqtSignal()

    def __init__(self, connection_string="udpin:0.0.0.0:14550", parent=None):
        super().__init__(parent)
        self._conn_str  = connection_string
        self._running   = False
        self._vehicle   = None
        self._surface_pressure = None   # calibrated at first surface reading
        self._timesync_t1 = None        # ns timestamp of last TIMESYNC send
        self._last_timesync_send = 0.0  # wall-clock time, rate-limit to 1 Hz
        self._vfrhud_received = False   # once True, suppress SCALED_PRESSURE2 depth

    def run(self):
        self._running = True
        if MAVLINK_AVAILABLE:
            self._run_real()
        else:
            self._run_mock()

    # ── real MAVLink loop ──────────────────────────────────────────────────────

    def _run_real(self):
        try:
            self._vehicle = mavutil.mavlink_connection(self._conn_str)
            msg = self._vehicle.wait_heartbeat(timeout=5)
            if msg is None:
                raise TimeoutError("no heartbeat")
            self._vehicle.target_system    = msg.get_srcSystem()
            self._vehicle.target_component = msg.get_srcComponent()
            self.connected.emit(True)
            self._request_data_streams()
            self._send_timesync()
        except Exception as exc:
            log.warning("MAVLink connection failed: %s", exc)
            self.connected.emit(False)
            self._run_mock()
            return

        last_hb = time.time()

        while self._running:
            try:
                msg = self._vehicle.recv_match(blocking=True, timeout=1.0)
                if msg is None:
                    if time.time() - last_hb > 5.0:
                        log.warning("Heartbeat timeout")
                        self.connection_lost.emit()
                        last_hb = time.time()
                    continue

                t = msg.get_type()

                if t == "HEARTBEAT":
                    # Ignore GCS heartbeats — only process autopilot
                    if msg.type == mavutil.mavlink.MAV_TYPE_GCS:
                        continue
                    last_hb = time.time()
                    self.heartbeat_received.emit()
                    armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
                    self.arm_updated.emit(armed)
                    mode = MODE_MAP.get(msg.custom_mode, f"MODE_{msg.custom_mode}")
                    self.mode_updated.emit(mode)

                elif t == "ATTITUDE":
                    # yaw is -π..π  →  0..360°
                    heading = math.degrees(msg.yaw) % 360
                    pitch   = math.degrees(msg.pitch)
                    roll    = math.degrees(msg.roll)
                    self.attitude_updated.emit(heading, pitch, roll)

                elif t == "VFR_HUD":
                    # ArduSub reports depth here (negative altitude = below surface).
                    # EKF-filtered and surface-calibrated by the autopilot — primary source.
                    depth = max(0.0, -msg.alt)
                    self._vfrhud_received = True
                    self.depth_updated.emit(depth)

                elif t == "SCALED_PRESSURE2":
                    # Raw Bar30/D300 pressure — fallback only when VFR_HUD not yet seen.
                    if self._vfrhud_received:
                        pass  # VFR_HUD is authoritative; ignore raw pressure for depth
                    else:
                        if self._surface_pressure is None:
                            self._surface_pressure = msg.press_abs
                            log.info("Surface pressure calibrated: %.2f hPa", self._surface_pressure)
                        depth = max(0.0, (msg.press_abs - self._surface_pressure) / DEPTH_DIVISOR)
                        self.depth_updated.emit(depth)

                elif t == "BATTERY_STATUS":
                    pct  = float(max(0, msg.battery_remaining))
                    # voltages[] is in mV; 65535 == unknown
                    volt = msg.voltages[0] / 1000.0 if msg.voltages[0] != 65535 else 0.0
                    self.battery_updated.emit(pct, volt)

                elif t == "SERVO_OUTPUT_RAW":
                    raw  = [msg.servo1_raw, msg.servo2_raw, msg.servo3_raw,
                            msg.servo4_raw, msg.servo5_raw, msg.servo6_raw]
                    pcts = [self._pwm_to_pct(v) for v in raw]
                    self.motors_updated.emit(pcts)

                elif t == "TIMESYNC":
                    # tc1 == 0: this is a request FROM the vehicle (ignore or echo back).
                    # tc1 != 0: this is the vehicle echoing our timestamp back to us.
                    if msg.tc1 != 0:
                        # RTT = now − the nanosecond timestamp we put in ts1 when we sent
                        rtt_ms = (int(time.time() * 1e9) - msg.tc1) / 1e6
                        if 0 < rtt_ms < 2000:
                            self.ping_updated.emit(rtt_ms)
                    # Send a new timesync probe at most once per second
                    self._send_timesync()

            except Exception as exc:
                log.debug("recv error: %s", exc)

    def _request_data_streams(self):
        """Ask ArduSub to start streaming the messages we need."""
        if not self._vehicle:
            return
        streams = [
            (mavutil.mavlink.MAV_DATA_STREAM_RAW_SENSORS,     10),
            (mavutil.mavlink.MAV_DATA_STREAM_EXTENDED_STATUS, 2),
            (mavutil.mavlink.MAV_DATA_STREAM_RC_CHANNELS,     10),
            (mavutil.mavlink.MAV_DATA_STREAM_POSITION,        10),
            (mavutil.mavlink.MAV_DATA_STREAM_EXTRA1,          20),  # ATTITUDE
            (mavutil.mavlink.MAV_DATA_STREAM_EXTRA2,          10),  # VFR_HUD
        ]
        for stream_id, rate in streams:
            self._vehicle.mav.request_data_stream_send(
                self._vehicle.target_system,
                self._vehicle.target_component,
                stream_id, rate, 1
            )

    def _send_timesync(self):
        """Send a TIMESYNC probe at most once per second."""
        if not self._vehicle:
            return
        now = time.time()
        if now - self._last_timesync_send < 1.0:
            return
        self._last_timesync_send = now
        # We put our current ns timestamp in ts1.
        # The vehicle echoes it back in tc1, letting us measure RTT.
        self._timesync_t1 = int(now * 1e9)
        self._vehicle.mav.timesync_send(0, self._timesync_t1)

    # ── PWM helper ─────────────────────────────────────────────────────────────

    def _pwm_to_pct(self, pwm: int) -> float:
        """Convert raw PWM (µs) to 0-100 % thrust (symmetric around 1500)."""
        if pwm == 0 or pwm == 65535:   # not assigned / unknown
            return 0.0
        val = pwm - 1500
        if abs(val) < 25:              # deadband
            return 0.0
        return min(100.0, abs(val) / 5.0)

    # ── mock loop (no hardware) ────────────────────────────────────────────────

    def _run_mock(self):
        self.connected.emit(True)
        t = 0.0
        while self._running:
            heading = (t * 10) % 360
            pitch   = math.sin(t * 0.3) * 15
            roll    = math.cos(t * 0.2) * 10
            self.attitude_updated.emit(heading, pitch, roll)
            self.depth_updated.emit(max(0.0, math.sin(t * 0.1) * 5 + 3))
            self.battery_updated.emit(75.0, 15.8)
            self.arm_updated.emit(False)
            self.mode_updated.emit("STABILIZE")
            self.motors_updated.emit([abs(math.sin(t + i) * 60) for i in range(6)])
            self.ping_updated.emit(12.0 + math.sin(t) * 3)
            self.heartbeat_received.emit()
            time.sleep(0.05)
            t += 0.05

    # ── commands ───────────────────────────────────────────────────────────────

    def send_mode(self, mode_name: str):
        """Send DO_SET_MODE command to ArduSub."""
        if not self._vehicle or not MAVLINK_AVAILABLE:
            return
        mode_id = MODE_NAME_MAP.get(mode_name)
        if mode_id is None:
            log.warning("Unknown mode: %s", mode_name)
            return
        self._vehicle.mav.command_long_send(
            self._vehicle.target_system,
            self._vehicle.target_component,
            mavutil.mavlink.MAV_CMD_DO_SET_MODE,
            0,
            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            mode_id, 0, 0, 0, 0, 0
        )

    def send_arm(self, arm: bool):
        if not self._vehicle or not MAVLINK_AVAILABLE:
            return
        self._vehicle.mav.command_long_send(
            self._vehicle.target_system,
            self._vehicle.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            1 if arm else 0,
            0, 0, 0, 0, 0, 0
        )

    def send_emergency_stop(self):
        """Force-disarm (magic number 21196 bypasses arm checks)."""
        if not self._vehicle or not MAVLINK_AVAILABLE:
            return
        self._vehicle.mav.command_long_send(
            self._vehicle.target_system,
            self._vehicle.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            0,       # disarm
            21196,   # force disarm magic
            0, 0, 0, 0, 0
        )

    def stop(self):
        self._running = False
        self.quit()
        self.wait()
