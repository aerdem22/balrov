import time
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal, QMutex
from PyQt5.QtGui import QImage

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

# ROV companion pushes RTP video → topside listens on port 5600.
# GStreamer pipeline: listen on UDP 5600, decode H.264 RTP.
# OpenCV fallback:   "@:5600" binds locally (ffmpeg udp listen syntax).
GSTREAMER_PIPELINE = (
    "udpsrc port=5600 ! application/x-rtp,payload=96 ! "
    "rtph264depay ! avdec_h264 ! videoconvert ! "
    "appsink max-buffers=1 drop=true"
)
OPENCV_LISTEN_URL = "udp://@:5600"


class CameraHandler(QThread):
    frame_ready = pyqtSignal(QImage)
    recording_started = pyqtSignal(str)
    recording_stopped = pyqtSignal()
    fps_updated = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._recording = False
        self._writer = None
        self._mutex = QMutex()
        self._cap = None
        self._use_mock = False
        self._mock_t = 0.0
        self._frame_count = 0
        self._fps_ts = time.time()
        self._last_good_frame = 0.0   # timestamp of last successful cap.read()

    def run(self):
        self._running = True
        if CV2_AVAILABLE:
            self._try_open_stream()
        else:
            self._use_mock = True

        while self._running:
            if self._use_mock:
                frame = self._make_mock_frame()
            else:
                ret, frame = self._cap.read()
                if ret:
                    self._last_good_frame = time.time()
                else:
                    # Stream stalled: show mock and attempt reconnect after 3s
                    frame = self._make_mock_frame()
                    if time.time() - self._last_good_frame > 3.0:
                        self._cap.release()
                        self._try_open_stream()
                        self._last_good_frame = time.time()

            self._maybe_record(frame)
            self._emit_frame(frame)
            self._update_fps()
            time.sleep(0.033)

        if self._cap:
            self._cap.release()
        if self._writer:
            self._writer.release()

    def _try_open_stream(self):
        try:
            cap = cv2.VideoCapture(GSTREAMER_PIPELINE, cv2.CAP_GSTREAMER)
            if not cap.isOpened():
                raise RuntimeError("GStreamer failed")
            self._cap = cap
            self._use_mock = False
        except Exception:
            try:
                # Fallback: ffmpeg UDP listen (topside binds local port 5600)
                cap = cv2.VideoCapture(OPENCV_LISTEN_URL)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                if not cap.isOpened():
                    raise RuntimeError("OpenCV UDP listen failed")
                self._cap = cap
                self._use_mock = False
            except Exception:
                self._use_mock = True

    def _make_mock_frame(self):
        self._mock_t += 0.033
        h, w = 720, 1280
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[:, :] = (13, 20, 35)

        if CV2_AVAILABLE:
            # Grid lines
            for x in range(0, w, 80):
                cv2.line(frame, (x, 0), (x, h), (30, 40, 60), 1)
            for y in range(0, h, 80):
                cv2.line(frame, (0, y), (w, y), (30, 40, 60), 1)

            # Center crosshair
            cx, cy = w // 2, h // 2
            cv2.line(frame, (cx - 40, cy), (cx + 40, cy), (0, 180, 255), 2)
            cv2.line(frame, (cx, cy - 40), (cx, cy + 40), (0, 180, 255), 2)
            cv2.circle(frame, (cx, cy), 20, (0, 180, 255), 1)

            cv2.putText(frame, "BALROV CAM — NO SIGNAL",
                        (cx - 180, cy - 60), cv2.FONT_HERSHEY_SIMPLEX,
                        1.0, (0, 180, 255), 2)
            cv2.putText(frame, f"MOCK FEED {self._mock_t:.1f}s",
                        (cx - 120, cy + 80), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (100, 100, 150), 1)
        return frame

    def _emit_frame(self, frame):
        if CV2_AVAILABLE:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        else:
            rgb = frame
        h, w, ch = rgb.shape
        img = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888).copy()
        self.frame_ready.emit(img)

    def _maybe_record(self, frame):
        if not self._recording or frame is None:
            return
        if self._writer is None and CV2_AVAILABLE:
            h, w = frame.shape[:2]
            import datetime
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            path = f"recordings/balrov_{ts}.avi"
            import os; os.makedirs("recordings", exist_ok=True)
            fourcc = cv2.VideoWriter_fourcc(*"XVID")
            self._writer = cv2.VideoWriter(path, fourcc, 30, (w, h))
            self.recording_started.emit(path)
        if self._writer:
            self._writer.write(frame)

    def _update_fps(self):
        self._frame_count += 1
        now = time.time()
        elapsed = now - self._fps_ts
        if elapsed >= 1.0:
            fps = self._frame_count / elapsed
            self.fps_updated.emit(fps)
            self._frame_count = 0
            self._fps_ts = now

    def start_recording(self):
        self._recording = True

    def stop_recording(self):
        self._recording = False
        if self._writer:
            self._writer.release()
            self._writer = None
        self.recording_stopped.emit()

    def stop(self):
        self._running = False
        self.quit()
        self.wait()
