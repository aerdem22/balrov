import sys
import logging
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)

from core.mavlink_handler import MAVLinkHandler
from core.camera_handler import CameraHandler
from core.gpio_handler import GPIOHandler
from core.watchdog import Watchdog
from utils.logger import Logger
from ui.main_window import MainWindow


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    app = QApplication(sys.argv)

    logger = Logger()
    mavlink = MAVLinkHandler("udpin:0.0.0.0:14550")
    camera = CameraHandler()
    gpio = GPIOHandler()
    watchdog = Watchdog(timeout_sec=3.0)

    window = MainWindow(mavlink, camera, gpio, watchdog, logger)
    window.show()

    # Start background threads immediately so mock data flows
    mavlink.start()
    camera.start()
    gpio.start()
    watchdog.start()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
