import csv
import os
import threading
from datetime import datetime


class Logger:
    def __init__(self):
        self._file = None
        self._writer = None
        self._lock = threading.Lock()
        self._path = None
        self._size = 0

    def start(self, directory="logs"):
        os.makedirs(directory, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._path = os.path.join(directory, f"balrov_{ts}.csv")
        self._file = open(self._path, "w", newline="")
        self._writer = csv.writer(self._file)
        self._writer.writerow([
            "timestamp", "heading", "pitch", "roll", "depth",
            "battery_pct", "battery_volt", "arm", "mode",
            "m1", "m2", "m3", "m4", "m5", "m6",
            "leak", "ping_ms", "tether_m"
        ])
        self._file.flush()

    def log(self, data: dict):
        if not self._writer:
            return
        with self._lock:
            row = [
                datetime.now().isoformat(),
                data.get("heading", 0),
                data.get("pitch", 0),
                data.get("roll", 0),
                data.get("depth", 0),
                data.get("battery_pct", 0),
                data.get("battery_volt", 0),
                data.get("arm", False),
                data.get("mode", "UNKNOWN"),
                *[data.get(f"m{i}", 0) for i in range(1, 7)],
                data.get("leak", False),
                data.get("ping_ms", 0),
                data.get("tether_m", 0),
            ]
            self._writer.writerow(row)
            self._file.flush()
            self._size = os.path.getsize(self._path)

    def log_event(self, event: str):
        if not self._writer:
            return
        with self._lock:
            self._writer.writerow([datetime.now().isoformat(), "EVENT", event] + [""] * 15)
            self._file.flush()

    def size_kb(self) -> float:
        return self._size / 1024

    def stop(self):
        if self._file:
            self._file.close()
            self._file = None
            self._writer = None
