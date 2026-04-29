import math
import platform
import time
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QSlider, QFrame, QSizePolicy, QGridLayout,
    QProgressBar, QStackedWidget, QGraphicsDropShadowEffect,
)
from PyQt5.QtCore import (
    Qt, QTimer, QTime, pyqtSlot, QSize, QRect, QPoint, QPointF,
)
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QFont, QImage, QPixmap,
    QPainterPath, QFontDatabase, QPolygonF,
)

# ── colour palette ────────────────────────────────────────────────────────────
BG       = "#080d17"
BG2      = "#0d1525"
BG3      = "#111d33"
ACCENT   = "#1e7fff"
ACCENT2  = "#0055cc"
TEXT     = "#d0dff5"
TEXT_DIM = "#4a6080"
GREEN    = "#00e676"
RED      = "#ff1744"
YELLOW   = "#ffea00"
ORANGE   = "#ff6d00"

MONO_FONT = "Menlo" if platform.system() == "Darwin" else "Consolas"


def _style(extra=""):
    return f"""
        QWidget {{ background: {BG}; color: {TEXT}; font-family: '{MONO_FONT}', 'Courier New'; }}
        QLabel  {{ background: transparent; }}
        {extra}
    """


# ── reusable widgets ──────────────────────────────────────────────────────────

class Separator(QFrame):
    def __init__(self, vertical=True):
        super().__init__()
        self.setFrameShape(QFrame.VLine if vertical else QFrame.HLine)
        self.setStyleSheet(f"color: {BG3};")
        self.setFixedWidth(1) if vertical else self.setFixedHeight(1)


class Badge(QLabel):
    def __init__(self, text, color=ACCENT):
        super().__init__(text)
        self._color = color
        self.setAlignment(Qt.AlignCenter)
        self._apply()

    def set_text(self, text, color=None):
        self.setText(text)
        if color:
            self._color = color
            self._apply()

    def _apply(self):
        self.setStyleSheet(
            f"background: {self._color}22; color: {self._color}; "
            f"border: 1px solid {self._color}55; border-radius: 4px; "
            f"padding: 2px 8px; font-size: 11px; font-weight: bold;"
        )


class SignalBars(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._bars = 0
        self.setFixedSize(28, 18)

    def set_bars(self, n):
        self._bars = max(0, min(5, n))
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        bw = 4
        gap = 2
        for i in range(5):
            bh = 4 + i * 3
            x = i * (bw + gap)
            y = h - bh
            color = QColor(ACCENT) if i < self._bars else QColor(BG3)
            p.fillRect(x, y, bw, bh, color)


class CompassStrip(QWidget):
    """Circular rotating compass rose."""
    _DIAL_SIZE = 52

    def __init__(self, parent=None):
        super().__init__(parent)
        self._heading = 0.0
        self.setFixedSize(self._DIAL_SIZE + 2, self._DIAL_SIZE + 2)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def set_heading(self, deg):
        self._heading = deg % 360
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        d = self._DIAL_SIZE
        cx, cy = d // 2 + 1, d // 2 + 1

        # ── rotate ring opposite to heading so needle always points to north ──
        p.save()
        p.translate(cx, cy)
        p.rotate(-self._heading)

        # outer filled circle
        p.setPen(QPen(QColor("#1565C0"), 2))
        p.setBrush(QColor("#0a1828"))
        p.drawEllipse(-d // 2, -d // 2, d, d)

        # degree tick marks (every 10°)
        for tick_deg in range(0, 360, 10):
            rad = math.radians(tick_deg)
            is_major = (tick_deg % 90 == 0)
            outer_r = d // 2 - 1
            inner_r = outer_r - (5 if is_major else 3)
            x1 = math.sin(rad) * outer_r
            y1 = -math.cos(rad) * outer_r
            x2 = math.sin(rad) * inner_r
            y2 = -math.cos(rad) * inner_r
            pen_color = "#1565C0" if is_major else "#2a4a70"
            p.setPen(QPen(QColor(pen_color), 1))
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        # cardinal labels inside the ring
        cardinals = {0: ("N", "#EF5350"), 90: ("E", "#ffffff"),
                     180: ("S", "#ffffff"), 270: ("W", "#ffffff")}
        font_card = QFont(MONO_FONT, 6, QFont.Bold)
        p.setFont(font_card)
        label_r = d // 2 - 10
        for card_deg, (label, color) in cardinals.items():
            rad = math.radians(card_deg)
            lx = math.sin(rad) * label_r
            ly = -math.cos(rad) * label_r
            p.setPen(QColor(color))
            fm = p.fontMetrics()
            lw = fm.horizontalAdvance(label)
            lh = fm.height()
            p.drawText(QPointF(lx - lw / 2, ly + lh / 3), label)

        p.restore()

        # ── needle (fixed, always points up = north) ──────────────────────────
        needle_len = d // 2 - 6
        needle_w = 3
        path_n = QPainterPath()
        path_n.moveTo(cx, cy - needle_len)
        path_n.lineTo(cx - needle_w, cy)
        path_n.lineTo(cx + needle_w, cy)
        path_n.closeSubpath()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#EF5350"))
        p.drawPath(path_n)
        path_s = QPainterPath()
        path_s.moveTo(cx, cy + needle_len)
        path_s.lineTo(cx - needle_w, cy)
        path_s.lineTo(cx + needle_w, cy)
        path_s.closeSubpath()
        p.setBrush(QColor("#90CAF9"))
        p.drawPath(path_s)
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QPointF(cx, cy), 2.5, 2.5)

        # ── heading readout inside the dial (bottom interior, fixed) ──────────
        font_hdg = QFont(MONO_FONT, 5)
        p.setFont(font_hdg)
        p.setPen(QColor("#64B5F6"))
        hdg_txt = f"{int(self._heading):03d}°"
        fm = p.fontMetrics()
        tx = cx - fm.horizontalAdvance(hdg_txt) // 2
        ty = cy + d // 2 - 5
        p.drawText(tx, ty, hdg_txt)


class BatteryBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pct = 100.0
        self._volt = 0.0
        self.setFixedSize(120, 20)

    def set_value(self, pct, volt):
        self._pct = pct
        self._volt = volt
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        r = 4
        border = QColor(BG3)
        p.setPen(QPen(border, 1))
        p.setBrush(QColor(BG2))
        p.drawRoundedRect(0, 0, w - 8, h, r, r)
        # tip
        p.fillRect(w - 7, h // 4, 6, h // 2, border)

        fill_w = int((w - 10) * self._pct / 100)
        if self._pct > 50:
            color = QColor(GREEN)
        elif self._pct > 20:
            color = QColor(YELLOW)
        else:
            color = QColor(RED)
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawRoundedRect(2, 2, fill_w, h - 4, r - 1, r - 1)


class MotorBar(QWidget):
    def __init__(self, label, parent=None):
        super().__init__(parent)
        self._pct = 0.0
        self._label = label
        self.setFixedWidth(32)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

    def set_value(self, pct):
        self._pct = max(0, min(100, pct))
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        label_h = 18
        bar_h = h - label_h - 4
        bar_y = 2

        p.fillRect(0, bar_y, w, bar_h, QColor(BG3))

        fill_h = int(bar_h * self._pct / 100)
        color = QColor(ACCENT)
        if self._pct >= 80:
            color = QColor(RED)
        elif self._pct >= 60:
            color = QColor(YELLOW)

        p.fillRect(0, bar_y + bar_h - fill_h, w, fill_h, color)

        p.setPen(QColor(TEXT_DIM))
        p.setFont(QFont(MONO_FONT, 8))
        p.drawText(QRect(0, h - label_h, w, label_h), Qt.AlignCenter, self._label)

        p.setPen(QColor(TEXT))
        p.setFont(QFont(MONO_FONT, 7))
        p.drawText(QRect(0, bar_y, w, 14), Qt.AlignCenter, f"{int(self._pct)}%")


class ROV3DWidget(QWidget):
    """Wireframe ROV attitude indicator."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pitch = 0.0
        self._roll = 0.0
        self._heading = 0.0
        self.setMinimumSize(180, 120)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def set_attitude(self, heading, pitch, roll):
        self._heading = heading
        self._pitch = pitch
        self._roll = roll
        self.update()

    def _project(self, x, y, z, cx, cy, scale=50):
        px = cx + x * scale
        py = cy - y * scale + z * scale * 0.3
        return QPointF(px, py)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        p.fillRect(0, 0, w, h, QColor(0, 0, 0, 100))

        cx, cy = w / 2, h / 2
        pr = math.radians(self._pitch)
        rr = math.radians(self._roll)

        def rot(x, y, z):
            # Roll
            y2 = y * math.cos(rr) - z * math.sin(rr)
            z2 = y * math.sin(rr) + z * math.cos(rr)
            # Pitch
            x3 = x * math.cos(pr) + z2 * math.sin(pr)
            z3 = -x * math.sin(pr) + z2 * math.cos(pr)
            return x3, y2, z3

        scale = min(w, h) * 0.28

        # ROV body
        body = [(-1, 0, 0.3), (1, 0, 0.3), (1, 0, -0.3), (-1, 0, -0.3)]
        pts_body = [self._project(*rot(bx, by, bz), cx, cy, scale) for bx, by, bz in body]

        pen_body = QPen(QColor(ACCENT), 2)
        p.setPen(pen_body)
        poly = QPolygonF(pts_body)
        p.drawPolygon(poly)

        # Thrusters
        thrusters = [(-0.8, 0.6, 0.3), (0.8, 0.6, 0.3), (-0.8, -0.6, 0.3), (0.8, -0.6, 0.3)]
        p.setPen(QPen(QColor(ACCENT2), 1))
        for tx, ty, tz in thrusters:
            pt = self._project(*rot(tx, ty, tz), cx, cy, scale)
            p.drawEllipse(pt, 5, 5)

        # Axes
        axis_len = 0.6
        axes = [(axis_len, 0, 0, RED), (0, axis_len, 0, GREEN), (0, 0, axis_len, ACCENT)]
        for ax, ay, az, col in axes:
            end = self._project(*rot(ax, ay, az), cx, cy, scale)
            origin = self._project(*rot(0, 0, 0), cx, cy, scale)
            p.setPen(QPen(QColor(col), 1, Qt.DashLine))
            p.drawLine(origin, end)

        # Labels
        p.setPen(QColor(TEXT_DIM))
        p.setFont(QFont(MONO_FONT, 7))
        p.drawText(4, h - 4, f"P:{self._pitch:.1f}° R:{self._roll:.1f}° H:{self._heading:.0f}°")


class CameraView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._image = None
        self._warning = False
        self.setMinimumSize(640, 400)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_frame(self, img: QImage):
        self._image = img
        self.update()

    def set_low_battery_warning(self, on: bool):
        self._warning = on
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        w, h = self.width(), self.height()

        if self._image:
            scaled = self._image.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = (w - scaled.width()) // 2
            y = (h - scaled.height()) // 2
            p.drawImage(x, y, scaled)
        else:
            p.fillRect(0, 0, w, h, QColor(BG2))
            p.setPen(QColor(TEXT_DIM))
            p.setFont(QFont(MONO_FONT, 14))
            p.drawText(self.rect(), Qt.AlignCenter, "KAMERA BEKLENIYOR…")

        if self._warning:
            p.fillRect(0, 0, w, 40, QColor(255, 23, 68, 200))
            p.setPen(QColor("white"))
            p.setFont(QFont(MONO_FONT, 13, QFont.Bold))
            p.drawText(QRect(0, 0, w, 40), Qt.AlignCenter, "⚠  BATARYA DÜŞÜK — %20 ALTI")


# ── top bar ───────────────────────────────────────────────────────────────────

class TopBar(QWidget):
    lumen_changed = __import__("PyQt5.QtCore", fromlist=["pyqtSignal"]).pyqtSignal(int)
    emergency_clicked = __import__("PyQt5.QtCore", fromlist=["pyqtSignal"]).pyqtSignal()
    connect_clicked = __import__("PyQt5.QtCore", fromlist=["pyqtSignal"]).pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(64)
        self.setStyleSheet(f"background: {BG2}; border-bottom: 1px solid {BG3};")
        self._build()

    def _build(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 4, 12, 4)
        lay.setSpacing(16)

        # Logo
        logo = self._make_logo()
        lay.addWidget(logo)
        lay.addWidget(Separator())

        # Battery
        batt_group = QVBoxLayout()
        batt_group.setSpacing(2)
        self.bat_bar = BatteryBar()
        self.bat_label = QLabel("— %  —.— V")
        self.bat_label.setStyleSheet(f"font-size: 11px; color: {TEXT};")
        self.bat_extra = QLabel("Log: 0 KB  |  Tether: 0.0 m")
        self.bat_extra.setStyleSheet(f"font-size: 9px; color: {TEXT_DIM};")
        batt_group.addWidget(self.bat_bar)
        batt_group.addWidget(self.bat_label)
        batt_group.addWidget(self.bat_extra)
        lay.addLayout(batt_group)
        lay.addWidget(Separator())

        # Attitude
        att_group = QVBoxLayout()
        att_group.setSpacing(1)
        self.hdg_label = QLabel("HDG  ---°")
        self.pit_label = QLabel("PITCH  ---°")
        self.rol_label = QLabel("ROLL   ---°")
        for lbl in (self.hdg_label, self.pit_label, self.rol_label):
            lbl.setStyleSheet(f"font-size: 11px; color: {TEXT}; font-family: {MONO_FONT};")
            att_group.addWidget(lbl)
        lay.addLayout(att_group)
        lay.addWidget(Separator())

        # Depth
        depth_frame = QFrame()
        depth_frame.setStyleSheet(
            f"background: {BG3}; border: 1px solid {ACCENT}44; border-radius: 6px;"
        )
        depth_lay = QVBoxLayout(depth_frame)
        depth_lay.setContentsMargins(10, 2, 10, 2)
        depth_lay.setSpacing(0)
        dlbl = QLabel("DERİNLİK")
        dlbl.setStyleSheet(f"font-size: 9px; color: {TEXT_DIM}; letter-spacing: 2px;")
        self.depth_val = QLabel("0.00 m")
        self.depth_val.setStyleSheet(
            f"font-size: 22px; font-weight: bold; color: {ACCENT}; font-family: {MONO_FONT};"
        )
        depth_lay.addWidget(dlbl)
        depth_lay.addWidget(self.depth_val)
        lay.addWidget(depth_frame)
        lay.addWidget(Separator())

        # Connection
        conn_group = QVBoxLayout()
        conn_group.setSpacing(4)
        conn_row = QHBoxLayout()
        self.connect_btn = QPushButton("BAĞLAN")
        self.connect_btn.setFixedWidth(90)
        self.connect_btn.setStyleSheet(self._btn_style(ACCENT))
        self.connect_btn.clicked.connect(self.connect_clicked)
        self.signal_bars = SignalBars()
        conn_row.addWidget(self.connect_btn)
        conn_row.addWidget(self.signal_bars)
        self.ping_label = QLabel("--- ms")
        self.ping_label.setStyleSheet(f"font-size: 10px; color: {TEXT_DIM};")
        conn_group.addLayout(conn_row)
        conn_group.addWidget(self.ping_label)
        lay.addLayout(conn_group)
        lay.addWidget(Separator())

        # Lumen
        lumen_group = QVBoxLayout()
        lumen_group.setSpacing(2)
        lumen_lbl = QLabel("LÜMEN")
        lumen_lbl.setStyleSheet(f"font-size: 9px; color: {TEXT_DIM}; letter-spacing: 2px;")
        self.lumen_slider = QSlider(Qt.Horizontal)
        self.lumen_slider.setRange(0, 100)
        self.lumen_slider.setValue(0)
        self.lumen_slider.setFixedWidth(100)
        self.lumen_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{ background:{BG3}; height:6px; border-radius:3px; }}
            QSlider::handle:horizontal {{ background:{ACCENT}; width:14px; height:14px;
                                          border-radius:7px; margin:-4px 0; }}
            QSlider::sub-page:horizontal {{ background:{ACCENT}; border-radius:3px; }}
        """)
        self.lumen_slider.valueChanged.connect(self.lumen_changed)
        lumen_group.addWidget(lumen_lbl)
        lumen_group.addWidget(self.lumen_slider)
        lay.addLayout(lumen_group)
        lay.addWidget(Separator())

        # Compass
        self.compass = CompassStrip()
        lay.addWidget(self.compass, alignment=Qt.AlignVCenter)
        lay.addStretch()

        # Emergency stop
        self.emg_btn = QPushButton("ACİL\nDURDUR")
        self.emg_btn.setFixedSize(80, 52)
        self.emg_btn.setStyleSheet(f"""
            QPushButton {{
                background: {BG2}; color: {RED};
                border: 2px solid {RED}; border-radius: 6px;
                font-weight: bold; font-size: 11px;
            }}
            QPushButton:hover {{ background: {RED}33; }}
            QPushButton:pressed {{ background: {RED}66; }}
        """)
        self.emg_btn.clicked.connect(self.emergency_clicked)
        lay.addWidget(self.emg_btn)

    def _make_logo(self):
        w = QWidget()
        w.setFixedSize(44, 44)
        class _Logo(QWidget):
            def __init__(self):
                super().__init__()
                self.setFixedSize(44, 44)
            def paintEvent(self, _):
                p = QPainter(self)
                p.setRenderHint(QPainter.Antialiasing)
                p.setPen(QPen(QColor(ACCENT), 2))
                p.setBrush(QColor(ACCENT + "22"))
                p.drawEllipse(2, 2, 40, 40)
                p.setPen(QColor(ACCENT))
                p.setFont(QFont(MONO_FONT, 12, QFont.Bold))
                p.drawText(QRect(2, 2, 40, 40), Qt.AlignCenter, "BR")
        return _Logo()

    def _btn_style(self, color):
        return (
            f"QPushButton {{ background: {color}22; color: {color}; "
            f"border: 1px solid {color}66; border-radius: 4px; font-size: 11px; "
            f"font-weight: bold; padding: 4px 8px; }}"
            f"QPushButton:hover {{ background: {color}44; }}"
        )

    @pyqtSlot(bool)
    def set_connected(self, connected):
        if connected:
            self.connect_btn.setText("BAĞLI")
            self.connect_btn.setStyleSheet(self._btn_style(GREEN))
            self.signal_bars.set_bars(5)
        else:
            self.connect_btn.setText("BAĞLAN")
            self.connect_btn.setStyleSheet(self._btn_style(ACCENT))
            self.signal_bars.set_bars(0)

    @pyqtSlot(float, float)
    def update_battery(self, pct, volt):
        self.bat_bar.set_value(pct, volt)
        self.bat_label.setText(f"{pct:.0f}%  {volt:.1f} V")
        color = GREEN if pct > 50 else YELLOW if pct > 20 else RED
        self.bat_label.setStyleSheet(f"font-size: 11px; color: {color};")

    @pyqtSlot(float, float, float)
    def update_attitude(self, heading, pitch, roll):
        self.hdg_label.setText(f"HDG  {heading:6.1f}°")
        self.pit_label.setText(f"PITCH {pitch:+6.1f}°")
        self.rol_label.setText(f"ROLL  {roll:+6.1f}°")
        self.compass.set_heading(heading)

    @pyqtSlot(float)
    def update_depth(self, depth):
        self.depth_val.setText(f"{depth:.2f} m")

    @pyqtSlot(float)
    def update_ping(self, ms):
        self.ping_label.setText(f"{ms:.0f} ms")
        bars = 5 if ms < 20 else 4 if ms < 50 else 3 if ms < 100 else 2 if ms < 200 else 1
        self.signal_bars.set_bars(bars)

    def update_extras(self, log_kb, tether_m):
        self.bat_extra.setText(f"Log: {log_kb:.0f} KB  |  Tether: {tether_m:.1f} m")


# ── right panel sections ──────────────────────────────────────────────────────

class SectionFrame(QFrame):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"QFrame {{ background: {BG2}; border: 1px solid {BG3}; border-radius: 6px; }}"
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(8)

        hdr = QLabel(title)
        hdr.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 9px; letter-spacing: 2px; font-weight: bold; "
            f"border: none; border-bottom: 1px solid {BG3}; padding-bottom: 4px;"
        )
        outer.addWidget(hdr)

        self.body = QVBoxLayout()
        self.body.setSpacing(6)
        outer.addLayout(self.body)


class VehicleStatusPanel(SectionFrame):
    def __init__(self, parent=None):
        super().__init__("ARAÇ DURUMU", parent)

        grid = QGridLayout()
        grid.setSpacing(6)

        def row(r, key, val_widget):
            lbl = QLabel(key)
            lbl.setStyleSheet(f"font-size: 10px; color: {TEXT_DIM}; border: none;")
            grid.addWidget(lbl, r, 0)
            grid.addWidget(val_widget, r, 1)

        # Connection dot
        self.conn_dot = QLabel("●  BAĞLANTI YOK")
        self.conn_dot.setStyleSheet(f"color: {RED}; font-size: 11px; border: none;")
        row(0, "BAĞLANTI", self.conn_dot)

        self.arm_badge = Badge("DISARM", RED)
        row(1, "ARM", self.arm_badge)

        self.mode_badge = Badge("MANUEL", ACCENT)
        row(2, "MOD", self.mode_badge)

        self.batt_label = QLabel("—")
        self.batt_label.setStyleSheet(f"font-size: 11px; border: none; color: {TEXT};")
        row(3, "BATARYA", self.batt_label)

        self.leak_badge = Badge("NORMAL", GREEN)
        row(4, "SIZINTI", self.leak_badge)

        self.body.addLayout(grid)

    @pyqtSlot(bool)
    def set_connected(self, v):
        if v:
            self.conn_dot.setText("●  BAĞLI")
            self.conn_dot.setStyleSheet(f"color: {GREEN}; font-size: 11px; border: none;")
        else:
            self.conn_dot.setText("●  BAĞLANTI YOK")
            self.conn_dot.setStyleSheet(f"color: {RED}; font-size: 11px; border: none;")

    @pyqtSlot(bool)
    def set_arm(self, armed):
        self.arm_badge.set_text("ARMED" if armed else "DISARM", GREEN if armed else RED)

    @pyqtSlot(str)
    def set_mode(self, mode):
        colors = {"STABILIZE": ACCENT, "MANUAL": TEXT, "AUTO": GREEN, "CIRCLE": YELLOW}
        color = colors.get(mode, ACCENT)
        self.mode_badge.set_text(mode, color)

    @pyqtSlot(float, float)
    def set_battery(self, pct, volt):
        color = GREEN if pct > 50 else YELLOW if pct > 20 else RED
        self.batt_label.setText(f"{pct:.0f}%  {volt:.1f}V")
        self.batt_label.setStyleSheet(f"font-size: 11px; border: none; color: {color};")

    @pyqtSlot(bool)
    def set_leak(self, leak):
        self.leak_badge.set_text("SIZINTI!" if leak else "NORMAL", RED if leak else GREEN)


class MotorStatusPanel(SectionFrame):
    def __init__(self, parent=None):
        super().__init__("MOTOR DURUMU", parent)
        row = QHBoxLayout()
        row.setSpacing(4)
        self._bars = []
        for i in range(1, 7):
            b = MotorBar(f"M{i}")
            b.setFixedHeight(90)
            self._bars.append(b)
            row.addWidget(b)
        self.body.addLayout(row)

    @pyqtSlot(list)
    def update_motors(self, values):
        for i, v in enumerate(values[:6]):
            self._bars[i].set_value(v)


class AutonomousPanel(SectionFrame):
    mode_selected = __import__("PyQt5.QtCore", fromlist=["pyqtSignal"]).pyqtSignal(str)

    MODES = ["STABİL", "HAT TAKİBİ", "OTONOM NAV", "MANUEL"]

    def __init__(self, parent=None):
        super().__init__("OTONOM MOD", parent)
        self._active = "STABİL"
        row = QHBoxLayout()
        row.setSpacing(6)
        self._btns = {}
        for m in self.MODES:
            btn = QPushButton(m)
            btn.setCheckable(True)
            btn.setStyleSheet(self._btn_style(False))
            btn.clicked.connect(lambda checked, mode=m: self._select(mode))
            self._btns[m] = btn
            row.addWidget(btn)
        self._btns["STABİL"].setChecked(True)
        self._btns["STABİL"].setStyleSheet(self._btn_style(True))
        self.body.addLayout(row)

    def _select(self, mode):
        for m, btn in self._btns.items():
            active = m == mode
            btn.setChecked(active)
            btn.setStyleSheet(self._btn_style(active))
        self._active = mode
        self.mode_selected.emit(mode)

    def _btn_style(self, active):
        bg = ACCENT if active else BG3
        col = "white" if active else TEXT_DIM
        return (
            f"QPushButton {{ background: {bg}; color: {col}; border: none; "
            f"border-radius: 4px; font-size: 9px; padding: 4px; }}"
        )

    def reflect_mode(self, mode_str):
        mode_map = {
            "STABILIZE": "STABİL", "MANUAL": "MANUEL",
            "AUTO": "OTONOM NAV", "CIRCLE": "HAT TAKİBİ",
        }
        ui_mode = mode_map.get(mode_str, "STABİL")
        self._select(ui_mode)


class MiniROVPanel(SectionFrame):
    transfer_clicked = __import__("PyQt5.QtCore", fromlist=["pyqtSignal"]).pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__("MİNİ ROV", parent)
        self._transferred = False

        row = QHBoxLayout()
        self.status_lbl = QLabel("● Hazır")
        self.status_lbl.setStyleSheet(f"color: {GREEN}; font-size: 11px; border: none;")

        self.transfer_btn = QPushButton("Kontrolü Devret")
        self.transfer_btn.setStyleSheet(self._btn_style(False))
        self.transfer_btn.clicked.connect(self._toggle)

        row.addWidget(self.status_lbl)
        row.addStretch()
        row.addWidget(self.transfer_btn)
        self.body.addLayout(row)

    def _toggle(self):
        self._transferred = not self._transferred
        if self._transferred:
            self.status_lbl.setText("● Kontrol Devredildi")
            self.status_lbl.setStyleSheet(f"color: {YELLOW}; font-size: 11px; border: none;")
            self.transfer_btn.setStyleSheet(self._btn_style(True))
        else:
            self.status_lbl.setText("● Hazır")
            self.status_lbl.setStyleSheet(f"color: {GREEN}; font-size: 11px; border: none;")
            self.transfer_btn.setStyleSheet(self._btn_style(False))
        self.transfer_clicked.emit(self._transferred)

    def _btn_style(self, active):
        color = GREEN if active else ACCENT
        return (
            f"QPushButton {{ background: {color}22; color: {color}; "
            f"border: 1px solid {color}66; border-radius: 4px; "
            f"font-size: 10px; padding: 4px 10px; }}"
            f"QPushButton:hover {{ background: {color}44; }}"
        )


# ── main window ───────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self, mavlink, camera, gpio, watchdog, logger):
        super().__init__()
        self._mav = mavlink
        self._cam = camera
        self._gpio = gpio
        self._watchdog = watchdog
        self._logger = logger

        self._connected = False
        self._battery_pct = 100.0
        self._heading = 0.0
        self._pitch = 0.0
        self._roll = 0.0
        self._depth = 0.0
        self._tether_m = 0.0
        self._arm = False
        self._mode = "STABILIZE"
        self._motors = [0.0] * 6
        self._ping_ms = 0.0

        self._elapsed_timer = QTimer()
        self._elapsed_timer.timeout.connect(self._tick_timer)
        self._elapsed_start = None
        self._recording = False

        self.setWindowTitle("BALROV — Kontrol Paneli")
        self.showFullScreen()
        self.setStyleSheet(_style())
        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top bar
        self.topbar = TopBar()
        root.addWidget(self.topbar)

        # Content
        content = QHBoxLayout()
        content.setContentsMargins(8, 8, 8, 8)
        content.setSpacing(8)
        root.addLayout(content)

        # Left: camera
        left = QVBoxLayout()
        left.setSpacing(0)
        content.addLayout(left, stretch=3)

        # Camera container
        cam_container = QWidget()
        cam_container.setStyleSheet(f"background: black;")
        cam_lay = QVBoxLayout(cam_container)
        cam_lay.setContentsMargins(0, 0, 0, 0)

        self.cam_view = CameraView()
        cam_lay.addWidget(self.cam_view)

        # Timer + record overlay (top-right of camera)
        overlay = QWidget(cam_container)
        overlay.setAttribute(Qt.WA_TranslucentBackground)
        ol = QVBoxLayout(overlay)
        ol.setContentsMargins(8, 8, 8, 8)
        ol.setAlignment(Qt.AlignTop | Qt.AlignRight)

        self.timer_label = QLabel("00:00:00")
        self.timer_label.setStyleSheet(
            f"color: {TEXT}; font-size: 18px; font-weight: bold; "
            f"background: rgba(0,0,0,180); padding: 4px 10px; border-radius: 4px;"
        )
        ol.addWidget(self.timer_label, alignment=Qt.AlignRight)

        self.record_btn = QPushButton("⏺  KAYIT")
        self.record_btn.setStyleSheet(self._rec_btn_style(False))
        self.record_btn.setFixedWidth(110)
        self.record_btn.clicked.connect(self._toggle_recording)
        ol.addWidget(self.record_btn, alignment=Qt.AlignRight)

        # Resolution label (bottom-left)
        self.res_label = QLabel("1080p • 30fps")
        self.res_label.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: 10px; "
            f"background: rgba(0,0,0,150); padding: 2px 8px; border-radius: 3px;"
        )

        # ROV 3D widget (bottom-center)
        self.rov3d = ROV3DWidget()
        self.rov3d.setFixedSize(200, 130)

        # We use absolute layout for overlays on camera
        # Use resize event to position them
        cam_container.resizeEvent = self._on_cam_resize
        cam_container._overlay = overlay
        cam_container._res = self.res_label
        cam_container._rov3d = self.rov3d
        self.res_label.setParent(cam_container)
        self.rov3d.setParent(cam_container)

        left.addWidget(cam_container)

        # Right panel
        right = QVBoxLayout()
        right.setSpacing(8)
        right.setContentsMargins(0, 0, 0, 0)
        content.addLayout(right, stretch=1)

        self.vehicle_panel = VehicleStatusPanel()
        self.motor_panel = MotorStatusPanel()
        self.auto_panel = AutonomousPanel()
        self.mini_rov_panel = MiniROVPanel()

        right.addWidget(self.vehicle_panel)
        right.addWidget(self.motor_panel)
        right.addWidget(self.auto_panel)
        right.addWidget(self.mini_rov_panel)
        right.addStretch()

        self._cam_container = cam_container

    def _on_cam_resize(self, event):
        c = self._cam_container
        w, h = c.width(), c.height()
        ov = c._overlay
        ov.setGeometry(0, 0, w, h)

        res = c._res
        res.adjustSize()
        res.move(8, h - res.height() - 8)

        rov = c._rov3d
        rov.move(w // 2 - rov.width() // 2, h - rov.height() - 8)
        rov.raise_()

    def _rec_btn_style(self, active):
        color = RED if active else ACCENT
        return (
            f"QPushButton {{ background: rgba(0,0,0,180); color: {color}; "
            f"border: 1px solid {color}; border-radius: 4px; "
            f"font-size: 11px; font-weight: bold; padding: 4px 8px; }}"
        )

    def _connect_signals(self):
        # MAVLink → UI
        self._mav.attitude_updated.connect(self._on_attitude)
        self._mav.depth_updated.connect(self._on_depth)
        self._mav.battery_updated.connect(self._on_battery)
        self._mav.arm_updated.connect(self._on_arm)
        self._mav.mode_updated.connect(self._on_mode)
        self._mav.motors_updated.connect(self._on_motors)
        self._mav.ping_updated.connect(self._on_ping)
        self._mav.connected.connect(self._on_connected)
        self._mav.connection_lost.connect(self._on_connection_lost)
        self._mav.heartbeat_received.connect(self._watchdog.feed)

        # Camera
        self._cam.frame_ready.connect(self.cam_view.set_frame)

        # GPIO
        self._gpio.tether_updated.connect(self._on_tether)
        self._gpio.leak_detected.connect(self._on_leak)
        self._gpio.emergency_triggered.connect(self._emergency_activated)

        # Watchdog
        self._watchdog.timeout_triggered.connect(self._on_watchdog_timeout)

        # TopBar
        self.topbar.lumen_changed.connect(self._gpio.set_lumen)
        self.topbar.emergency_clicked.connect(self._on_emergency_btn)
        self.topbar.connect_clicked.connect(self._on_connect_btn)

        # Autonomous panel
        self.auto_panel.mode_selected.connect(self._mav.send_mode)

        # Mini ROV
        self.mini_rov_panel.transfer_clicked.connect(self._on_mini_rov_transfer)

    # ── slots ─────────────────────────────────────────────────────────────────

    @pyqtSlot(float, float, float)
    def _on_attitude(self, heading, pitch, roll):
        self._heading = heading
        self._pitch = pitch
        self._roll = roll
        self.topbar.update_attitude(heading, pitch, roll)
        self.rov3d.set_attitude(heading, pitch, roll)
        self._log_row()

    @pyqtSlot(float)
    def _on_depth(self, depth):
        self._depth = depth
        self.topbar.update_depth(depth)

    @pyqtSlot(float, float)
    def _on_battery(self, pct, volt):
        self._battery_pct = pct
        self.topbar.update_battery(pct, volt)
        self.vehicle_panel.set_battery(pct, volt)
        self.cam_view.set_low_battery_warning(pct < 20)

    @pyqtSlot(bool)
    def _on_arm(self, armed):
        self._arm = armed
        self.vehicle_panel.set_arm(armed)

    @pyqtSlot(str)
    def _on_mode(self, mode):
        self._mode = mode
        self.vehicle_panel.set_mode(mode)
        self.auto_panel.reflect_mode(mode)

    @pyqtSlot(list)
    def _on_motors(self, motors):
        self._motors = motors
        self.motor_panel.update_motors(motors)

    @pyqtSlot(float)
    def _on_ping(self, ms):
        self._ping_ms = ms
        self.topbar.update_ping(ms)

    @pyqtSlot(bool)
    def _on_connected(self, conn):
        self._connected = conn
        self.topbar.set_connected(conn)
        self.vehicle_panel.set_connected(conn)
        if conn and self._elapsed_start is None:
            self._elapsed_start = QTime.currentTime()
            self._elapsed_timer.start(1000)
            self._logger.start()
            self._watchdog.arm()

    @pyqtSlot(float)
    def _on_tether(self, meters):
        self._tether_m = meters
        self.topbar.update_extras(self._logger.size_kb(), meters)

    @pyqtSlot(bool)
    def _on_leak(self, leak):
        self.vehicle_panel.set_leak(leak)
        if leak:
            self._logger.log_event("LEAK_DETECTED")

    @pyqtSlot()
    def _on_connection_lost(self):
        self._connected = False
        self.topbar.set_connected(False)
        self.vehicle_panel.set_connected(False)
        self._logger.log_event("CONNECTION_LOST")

    def _on_connect_btn(self):
        if not self._connected:
            self._mav.start()
            self._gpio.start()

    def _on_emergency_btn(self):
        self._gpio.trigger_emergency()
        self._mav.send_emergency_stop()
        self._logger.log_event("EMERGENCY_STOP_OPERATOR")

    def _emergency_activated(self):
        self._logger.log_event("EMERGENCY_GPIO_TRIGGERED")

    def _on_watchdog_timeout(self):
        self._gpio.trigger_emergency()
        self._mav.send_emergency_stop()
        self._logger.log_event("WATCHDOG_TIMEOUT_EMERGENCY")

    def _on_mini_rov_transfer(self, transferred):
        self._logger.log_event(f"MINI_ROV_TRANSFER={'ON' if transferred else 'OFF'}")

    def _toggle_recording(self):
        self._recording = not self._recording
        self.record_btn.setStyleSheet(self._rec_btn_style(self._recording))
        self.record_btn.setText("⏹  DURDUR" if self._recording else "⏺  KAYIT")
        if self._recording:
            self._cam.start_recording()
        else:
            self._cam.stop_recording()

    def _tick_timer(self):
        if self._elapsed_start is None:
            return
        elapsed = self._elapsed_start.secsTo(QTime.currentTime())
        h = elapsed // 3600
        m = (elapsed % 3600) // 60
        s = elapsed % 60
        self.timer_label.setText(f"{h:02d}:{m:02d}:{s:02d}")
        self.topbar.update_extras(self._logger.size_kb(), self._tether_m)

    def _log_row(self):
        self._logger.log({
            "heading": self._heading, "pitch": self._pitch, "roll": self._roll,
            "depth": self._depth, "battery_pct": self._battery_pct,
            "battery_volt": 0, "arm": self._arm, "mode": self._mode,
            **{f"m{i+1}": v for i, v in enumerate(self._motors)},
            "ping_ms": self._ping_ms, "tether_m": self._tether_m,
        })

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()

    def closeEvent(self, event):
        self._mav.stop()
        self._cam.stop()
        self._gpio.stop()
        self._watchdog.stop()
        self._logger.stop()
        event.accept()
