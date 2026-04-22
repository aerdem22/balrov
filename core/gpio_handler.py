import platform
import threading
from PyQt5.QtCore import QThread, pyqtSignal

IS_PI = platform.machine().startswith("arm") or platform.machine().startswith("aarch")

GPIO = None
if IS_PI:
    try:
        import RPi.GPIO as GPIO
    except ImportError:
        IS_PI = False


ENCODER_A = 17
ENCODER_B = 18
LUMEN_PWM_PIN = 12
EMERGENCY_PIN = 27
LEAK_PIN = 22


class GPIOHandler(QThread):
    tether_updated = pyqtSignal(float)   # meters
    leak_detected = pyqtSignal(bool)
    emergency_triggered = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._tether_count = 0
        self._pwm = None
        self._lock = threading.Lock()

        # Mock state for non-Pi
        self._mock_lumen = 0
        self._mock_leak = False
        self._mock_tether = 0.0

    def setup(self):
        if not IS_PI:
            return
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(ENCODER_A, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(ENCODER_B, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(EMERGENCY_PIN, GPIO.OUT, initial=GPIO.LOW)
        GPIO.setup(LEAK_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(LUMEN_PWM_PIN, GPIO.OUT)

        self._pwm = GPIO.PWM(LUMEN_PWM_PIN, 1000)
        self._pwm.start(0)

        GPIO.add_event_detect(ENCODER_A, GPIO.BOTH, callback=self._encoder_callback)

    def _encoder_callback(self, channel):
        if not IS_PI:
            return
        b = GPIO.input(ENCODER_B)
        with self._lock:
            if b == GPIO.HIGH:
                self._tether_count += 1
            else:
                self._tether_count -= 1

    def set_lumen(self, brightness: int):
        """brightness 0-100"""
        if IS_PI and self._pwm:
            self._pwm.ChangeDutyCycle(brightness)
        else:
            self._mock_lumen = brightness

    def trigger_emergency(self):
        if IS_PI:
            GPIO.output(EMERGENCY_PIN, GPIO.HIGH)
        self.emergency_triggered.emit()

    def release_emergency(self):
        if IS_PI:
            GPIO.output(EMERGENCY_PIN, GPIO.LOW)

    def run(self):
        self._running = True
        self.setup()
        import time
        while self._running:
            if IS_PI:
                leak = GPIO.input(LEAK_PIN) == GPIO.LOW
                with self._lock:
                    tether_m = self._tether_count * 0.01  # 1 pulse = 1cm
                self.leak_detected.emit(leak)
                self.tether_updated.emit(tether_m)
            else:
                self.leak_detected.emit(self._mock_leak)
                self.tether_updated.emit(self._mock_tether)
            time.sleep(0.5)

    def stop(self):
        self._running = False
        if IS_PI and GPIO:
            if self._pwm:
                self._pwm.stop()
            GPIO.cleanup()
        self.quit()
        self.wait()
