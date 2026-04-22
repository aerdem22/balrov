import time
from PyQt5.QtCore import QThread, pyqtSignal


class Watchdog(QThread):
    timeout_triggered = pyqtSignal()

    def __init__(self, timeout_sec=3.0, parent=None):
        super().__init__(parent)
        self._timeout = timeout_sec
        self._last_ping = time.time()
        self._running = False
        self._armed = False

    def feed(self):
        self._last_ping = time.time()

    def arm(self):
        self._armed = True
        self._last_ping = time.time()

    def disarm(self):
        self._armed = False

    def run(self):
        self._running = True
        while self._running:
            if self._armed:
                elapsed = time.time() - self._last_ping
                if elapsed > self._timeout:
                    self.timeout_triggered.emit()
                    self._armed = False
            time.sleep(0.5)

    def stop(self):
        self._running = False
        self.quit()
        self.wait()
