"""SmartRPA GUI — 视觉驱动的智能桌面自动化程序"""
#
import sys, os, json, datetime, time
from typing import List
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def resource_path(relative_path):
    """Get absolute path for bundled resources (dev / PyInstaller frozen)."""
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def data_dir(subdir: str = "") -> str:
    """Get writable directory for user data (tasks, templates, etc.).
    Uses %APPDATA%/SmartRPA on Windows, ~/.smartrpa on other platforms.
    Created automatically if it doesn't exist.

    On first run from release zip, also copies data from
    <exe_dir>/SmartRPA_data/ if present (seeded by pack.bat)."""
    if os.name == "nt":
        base = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "SmartRPA")
    else:
        base = os.path.join(os.path.expanduser("~"), ".smartrpa")
    if subdir:
        base = os.path.join(base, subdir)
    os.makedirs(base, exist_ok=True)
    return base


from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QCheckBox, QComboBox, QFileDialog,
    QTextEdit, QProgressBar,
    QFrame, QSplitter, QScrollArea, QDialog,
    QInputDialog, QSpinBox, QStatusBar, QSizePolicy,
    QStackedWidget, QGraphicsDropShadowEffect,
    QListWidget, QListWidgetItem, QAbstractItemView,
    QSystemTrayIcon, QMenu, QDateTimeEdit,
    QMessageBox,
)
from PySide6.QtCore import Qt, QThread, Signal, QRect, QTimer, QSettings, Slot, QSize
from PySide6.QtGui import QFont, QPainter, QPen, QColor, QLinearGradient, QIcon, QPixmap, QDesktopServices
from PySide6.QtCore import QUrl

from smartrpa import Controller, Vision, TaskEngine, BTEngine, PopupHandler, __version__
from smartrpa.core.behavior_tree import ActionNode
from smartrpa.ui.flow_editor import FlowEditor


# ═══════════════════════════════════════════════
#  2026 Design System — Theme Tokens
# ═══════════════════════════════════════════════

class Theme:
    """Dual-theme design tokens — call Theme.apply('light'|'dark') to switch."""

    # Shared (invariant across themes)
    SP_XS   = 4
    SP_SM   = 6
    SP_MD   = 10
    SP_LG   = 14
    SP_XL   = 20
    SP_2XL  = 28
    SP_3XL  = 40
    R_SM    = 2
    R_MD    = 3
    R_LG    = 4
    R_XL    = 20
    ACCENT     = "#7c6ff7"
    ACCENT2    = "#a78bfa"
    GREEN      = "#5a5a6a"
    ORANGE     = "#fbbf24"
    RED        = "#f87171"
    BLUE       = "#60a5fa"

    def __init__(self):
        self.mode = "light"

    # ── Theme-dependent properties ──

    @property
    def BG(self):          return "#f4f4f8" if self.mode == "light" else "#0c0c12"
    @property
    def SURFACE(self):     return "#e8e9ee" if self.mode == "light" else "#14141e"
    @property
    def CARD(self):        return "#ffffff"  if self.mode == "light" else "#1c1c28"
    @property
    def CARD_HOVER(self):  return "#f0f0f5" if self.mode == "light" else "#24243a"
    @property
    def LOG_BG(self):      return "#f5f5f8"  if self.mode == "light" else "#0e0e16"
    @property
    def LOG_TEXT(self):    return "#4a4a5a"  if self.mode == "light" else "#94a1b8"

    @property
    def ACCENT_DIM(self):  return "#eae6ff" if self.mode == "light" else "#2e2656"
    @property
    def GREEN_BG(self):    return "#f5f5f5" if self.mode == "light" else "#1a1a24"
    @property
    def ORANGE_BG(self):   return "#fffbeb" if self.mode == "light" else "#2d2510"
    @property
    def RED_BG(self):      return "#fef2f2" if self.mode == "light" else "#2d1418"
    @property
    def BLUE_BG(self):     return "#eff6ff" if self.mode == "light" else "#1a2540"

    # ── Text colors: 6 independent values (light/dark pair) ──
    TEXT_LIGHT  = "#1d1d1f"    # 主文本
    TEXT2_LIGHT = "#4a4a5a"    # 次要文本
    TEXT3_LIGHT = "#7a7a82"    # 三级/弱文本
    TEXT_DARK   = "#e8eaf0"    # 主文本
    TEXT2_DARK  = "#b0b4c0"    # 次要文本
    TEXT3_DARK  = "#8c90a0"    # 改为浅灰，暗背景清晰可见

    @property
    def TEXT(self):   return self.TEXT_LIGHT if self.mode == "light" else self.TEXT_DARK
    @property
    def TEXT2(self):  return self.TEXT2_LIGHT if self.mode == "light" else self.TEXT2_DARK
    @property
    def TEXT3(self):  return self.TEXT3_LIGHT if self.mode == "light" else self.TEXT3_DARK

    @property
    def LINE(self):       return "#e2e2e8" if self.mode == "light" else "#252536"
    @property
    def LINE_LIGHT(self): return "#c8c8d0" if self.mode == "light" else "#32324a"

    @property
    def DANGER_BORDER(self): return "#fca5a5" if self.mode == "light" else "#5c2024"
    @property
    def DANGER_HOVER_BG(self): return "#fee2e2" if self.mode == "light" else "#3d1a1e"

    def apply(self, mode):
        self.mode = mode


# Global theme instance (default light)
T = Theme()


# ═══════════════════════════════════════════════
#  Global QSS Builder
# ═══════════════════════════════════════════════

def build_base_qss():
    """Re-generate QSS from current theme tokens."""
    return f"""
* {{
    font-family: "Microsoft YaHei", "PingFang SC", "SF Pro Display", sans-serif;  /* # ← 自定义字体族 */
    font-size: 13px;  /* # ← 字体 全局默认字号 */
    outline: none;
}}

QMainWindow {{
    background: {T.BG};
}}

QLabel {{
    color: {T.TEXT};
    background: transparent;
}}

QCheckBox {{
    color: {T.TEXT};
    spacing: 10px;
}}
QCheckBox::indicator {{
    width: 18px; height: 18px;
    border-radius: 5px;
    border: 2px solid {T.LINE_LIGHT};
    background: {T.CARD};
}}
QCheckBox::indicator:checked {{
    background: {T.ACCENT};
    border-color: {T.ACCENT};
}}
QCheckBox::indicator:hover {{
    border-color: {T.ACCENT2};
}}

QComboBox, QSpinBox {{
    background: {T.CARD};
    color: {T.TEXT};
    border: 1px solid {T.LINE};
    border-radius: {T.R_SM}px;
    padding: 7px 14px;
    min-height: 34px;
    max-height: 38px;
}}
QComboBox:focus, QSpinBox:focus {{
    border-color: {T.ACCENT};
}}
QComboBox:drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background: {T.CARD};
    color: {T.TEXT};
    border: 1px solid {T.LINE};
    outline: none;
    selection-background-color: {T.ACCENT};
    selection-color: white;
    border-radius: {T.R_SM}px;
    padding: 4px;
}}

QPushButton {{
    background: {T.CARD};
    color: {T.TEXT2};
    border: 1px solid {T.LINE};
    border-radius: {T.R_SM}px;
    padding: 8px 18px;
    min-height: 34px;
    font-weight: 500;
}}
QPushButton:hover {{
    background: {T.CARD_HOVER};
    border-color: {T.LINE_LIGHT};
    color: {T.TEXT};
}}
QPushButton:pressed {{
    background: {T.SURFACE};
}}

QScrollArea {{
    border: none;
    background: transparent;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: {T.LINE_LIGHT};
    border-radius: 3px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {T.TEXT3};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QProgressBar {{
    background: {T.LINE};
    border: none;
    border-radius: 2px;
    height: 3px;
}}
QProgressBar::chunk {{
    background: {T.ACCENT};
    border-radius: 2px;
}}

QTextEdit {{
    background: {T.CARD};
    color: {T.TEXT};
    border: 1px solid {T.LINE};
    border-radius: {T.R_SM}px;
    padding: 12px;
    font-size: 12px;
}}

QSplitter::handle {{
    background: {T.LINE};
    width: 1px;
}}

QStatusBar {{
    background: {T.SURFACE};
    color: {T.TEXT3};
    font-size: 12px;
    border-top: 1px solid {T.LINE};
    padding: 3px 12px;
}}
QStatusBar::item {{
    border: none;
}}
"""


# ═══════════════════════════════════════════════
#  UI Helper Functions (theme-aware)
# ═══════════════════════════════════════════════

def btn_primary(text):
    """Primary action button — flat solid accent color."""
    b = QPushButton(text)
    b.setStyleSheet(f"""
        QPushButton {{
            background: {T.ACCENT};
            color: white;
            border: none;
            border-radius: {T.R_SM}px;
            font-weight: 600;
            padding: 5px 14px;
            font-size: 12px;
            min-height: 26px;
            max-height: 26px;
        }}
        QPushButton:hover {{
            background: {T.ACCENT2};
        }}
        QPushButton:pressed {{
            background: #5a4fd1;
        }}
        QPushButton:disabled {{
            background: {T.LINE};
            color: {T.TEXT3};
        }}
    """)
    return b


def btn_danger(text):
    """Danger button — same size as primary"""
    b = QPushButton(text)
    b.setStyleSheet(f"""
        QPushButton {{
            background: {T.RED_BG};
            color: {T.RED};
            border: 1px solid {T.DANGER_BORDER};
            border-radius: {T.R_SM}px;
            font-weight: 600;
            padding: 5px 14px;
            font-size: 12px;
            min-height: 26px;
            max-height: 26px;
        }}
        QPushButton:hover {{
            background: {T.DANGER_HOVER_BG};
            border-color: {T.RED};
        }}
        QPushButton:disabled {{
            background: {T.CARD};
            color: {T.TEXT3};
            border-color: {T.LINE};
        }}
    """)
    return b


def btn_ghost(text, icon=""):
    """Ghost button — subtle, for secondary actions"""
    b = QPushButton(f"{icon}  {text}" if icon else text)
    b.setStyleSheet(f"""
        QPushButton {{
            background: transparent;
            color: {T.TEXT2};
            border: 1px solid {T.LINE};
            border-radius: {T.R_SM}px;
            padding: 4px 10px;
            min-height: 26px;
            max-height: 26px;
            font-weight: 500;
            font-size: 12px;
        }}
        QPushButton:hover {{
            background: {T.CARD};
            color: {T.TEXT};
            border-color: {T.LINE_LIGHT};
        }}
    """)
    return b


def section_header(text):
    """Section header label — uppercase, muted, tracking"""
    l = QLabel(text.upper())
    l.setStyleSheet(f"""
        font-size: 13px;
        font-weight: 700;
        color: {T.TEXT};
        letter-spacing: 2px;
        padding-bottom: 2px;
    """)
    return l


def section_title(text):
    """Section sub-title — medium weight, secondary color"""
    l = QLabel(text)
    l.setStyleSheet(f"font-size:13px; font-weight:700; color:{T.TEXT};")  # ← 自定义分区标题字号
    return l


def page_title(text):
    """Page title — large, bold, primary color"""
    l = QLabel(text)
    l.setStyleSheet(f"font-size:24px; font-weight:700; color:{T.TEXT}; letter-spacing:-0.5px;")
    return l


def page_subtitle(text):
    """Page subtitle — descriptive, secondary color"""
    l = QLabel(text)
    l.setStyleSheet(f"font-size:14px; color:{T.TEXT2}; font-weight:400;")  # ← 自定义描述文字字号
    return l


def sep():
    """Horizontal separator line"""
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet(f"color:{T.LINE}; max-height:1px; margin:4px 0;")
    return f


def status_pill(text, color=None, bg=None):
    """Status pill label — rounded, colored"""
    if color is None:
        color = T.TEXT2
    if bg is None:
        bg = T.SURFACE
    l = QLabel(text)
    l.setStyleSheet(f"""
        color: {color};
        font-size: 12px;
        font-weight: 600;
        padding: 5px 14px;
        min-height: 26px;
        max-height: 26px;
        background: {bg};
        border-radius: {T.R_SM}px;
        border: 1px solid {T.LINE};
    """)
    return l


# ═══════════════════════════════════════════════
#  Task Worker (unchanged)
# ═══════════════════════════════════════════════

class TaskWorker(QThread):
    log = Signal(str, str); finished = Signal(dict); step = Signal(str)

    def __init__(self, task_file, tpl_dir=None, no_popup=False, region=None, fast_mode=False):
        super().__init__()
        self.task_file = task_file
        self.tpl_dir = tpl_dir
        self.no_popup = no_popup
        self.region = region
        self.fast_mode = fast_mode
        self._active = True
        self._engine = None  # BTEngine or TaskEngine

    def _is_bt_format(self, path):
        """Detect if a task file uses the Behavior Tree format."""
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return "root" in data
        except Exception:
            return False

    def run(self):
        try:
            v = Vision()
            if self.tpl_dir:
                v.set_template_dir(self.tpl_dir)
            c = Controller()
            p = PopupHandler(v, c)
            p.enabled = not self.no_popup
            p.register_builtin_strategies()

            if self.fast_mode:
                c.human.fast_mode = True

            use_bt = self._is_bt_format(self.task_file)

            if use_bt:
                # ── Behavior Tree Engine ──
                engine = BTEngine(c, v, p)
                if self.region:
                    engine._ctx.anchor_offset = (self.region[0], self.region[1])
                engine.load(self.task_file)
                win_title = engine._meta.get("window")
                if win_title:
                    engine.set_window_title(win_title)
                    self.log.emit(f"窗口锚定: '{win_title}'", "INFO")
                self.log.emit(f"BT任务: {os.path.basename(self.task_file)}", "INFO")
                self._engine = engine
                engine.run()
                s = engine._ctx.stats
                self.log.emit(f"完成: {s['steps']}步 {s['popups_handled']}弹窗 {s['errors']}错误", "SUCCESS")
                self.finished.emit(s)

            else:
                # ── Classic State Machine Engine ──
                engine = TaskEngine(c, v, p)
                engine.region = self.region
                engine._user_log = lambda m, l: self.log.emit(m, l)
                engine.load(self.task_file)
                entry = list(engine._tasks.keys())[0]
                win_title = engine._meta.get("window")
                if win_title:
                    engine.set_window_title(win_title)
                    self.log.emit(f"窗口锚定: '{win_title}'", "INFO")
                self.log.emit(f"任务: {os.path.basename(self.task_file)}", "INFO")
                self._engine = engine
                orig = engine._execute_step
                cnt = [0]

                def hook(ss, t):
                    if not self._active:
                        engine.stop()
                        return False
                    cnt[0] += 1
                    self.step.emit(t.get("desc", ""))
                    return orig(ss, t)

                engine._execute_step = hook
                engine.run(entry)
                s = engine._stats
                self.log.emit(f"完成: {s['steps']}步 {s['popups_handled']}弹窗 {s['errors']}错误", "SUCCESS")
                self.finished.emit(s)

        except Exception as e:
            import traceback
            self.log.emit(str(e), "ERROR")
            self.log.emit(traceback.format_exc(), "ERROR")

    def stop(self):
        self._active = False
        if self._engine:
            self._engine.stop()


# ═══════════════════════════════════════════════
#  Region Selector
# ═══════════════════════════════════════════════

class RegionSelector(QDialog):
    def __init__(self):
        super().__init__()
        self.region = None
        self.s = None
        self.e = None
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setWindowState(Qt.WindowFullScreen)
        self.setCursor(Qt.CrossCursor)
        screen = QApplication.primaryScreen()
        self.bg = screen.grabWindow(0)
        self.setGeometry(screen.geometry())

    def paintEvent(self, ev):
        p = QPainter(self)
        p.drawPixmap(0, 0, self.bg)
        p.fillRect(self.rect(), QColor(10, 10, 18, 180))
        if self.s and self.e:
            r = QRect(self.s, self.e).normalized()
            p.drawPixmap(r, self.bg, r)
            p.setPen(QPen(QColor(T.ACCENT), 3))
            p.drawRect(r)
            c = QColor(T.ACCENT2)
            c.setAlpha(120)
            p.setPen(QPen(c, 1))
            p.drawRect(r.adjusted(2, 2, -2, -2))
            p.setPen(QColor("#ffffff"))
            p.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
            label = f"{r.width()} x {r.height()}"
            p.drawText(r.left() + 8, r.top() + 24, label)

    def mousePressEvent(self, e):
        self.s = self.e = e.pos()
        self.update()

    def mouseMoveEvent(self, e):
        self.e = e.pos()
        self.update()

    def mouseReleaseEvent(self, e):
        self.e = e.pos()
        r = QRect(self.s, self.e).normalized()
        if r.width() > 20 and r.height() > 20:
            self.region = (r.x(), r.y(), r.width(), r.height())
            self.accept()
        else:
            self.reject()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.reject()


# ═══════════════════════════════════════════════
#  Tab Navigation Button
# ═══════════════════════════════════════════════

class SidebarButton(QWidget):
    """Left sidebar navigation — icon + text aligned horizontally"""
    clicked = Signal()

    def __init__(self, icon, label, parent=None):
        super().__init__(parent)
        self._active = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(34)
        ly = QHBoxLayout(self)
        ly.setContentsMargins(12, 0, 8, 0)
        ly.setSpacing(6)
        ly.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self._icon = QLabel(icon)
        self._icon.setStyleSheet("font-size:14px;background:transparent;border:none;")
        self._icon.setFixedWidth(18)
        self._icon.setAlignment(Qt.AlignCenter)
        ly.addWidget(self._icon)

        self._text = QLabel(label)
        self._text.setStyleSheet("font-size:12px;background:transparent;border:none;")
        ly.addWidget(self._text)
        ly.addStretch(1)

        self._update_style()

    def set_active(self, active):
        self._active = active
        self._update_style()

    def _update_style(self):
        if self._active:
            self.setStyleSheet(f"""
                SidebarButton {{background:{T.ACCENT_DIM};border:none;border-left:3px solid {T.ACCENT};border-radius:0 4px 4px 0;}}
                QLabel {{color:{T.TEXT};font-weight:600;}}
            """)
        else:
            self.setStyleSheet(f"""
                SidebarButton {{background:transparent;border:none;border-left:3px solid transparent;border-radius:0 4px 4px 0;}}
                QLabel {{color:{T.TEXT2};font-weight:500;}}
                SidebarButton:hover {{background:{T.CARD_HOVER};}}
                SidebarButton:hover QLabel {{color:{T.TEXT};}}
            """)

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


# ═══════════════════════════════════════════════
#  Pulse Dot — Animated Status Indicator
# ═══════════════════════════════════════════════

class PulseDot(QWidget):
    """Animated pulsing dot for running status"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self._opacity = 1.0
        self._growing = False
        self._color = T.TEXT3
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def set_color(self, color):
        self._color = color
        self.update()

    def start_pulse(self):
        self._timer.start(600)

    def stop_pulse(self):
        self._timer.stop()
        self._opacity = 1.0
        self._growing = False
        self.update()

    def _tick(self):
        if self._growing:
            self._opacity += 0.3
            if self._opacity >= 1.0:
                self._opacity = 1.0
                self._growing = False
        else:
            self._opacity -= 0.3
            if self._opacity <= 0.3:
                self._opacity = 0.3
                self._growing = True
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QColor(self._color)
        c.setAlphaF(self._opacity * 0.3)
        p.setBrush(c)
        p.setPen(Qt.NoPen)
        p.drawEllipse(0, 0, 12, 12)
        c2 = QColor(self._color)
        c2.setAlphaF(self._opacity)
        p.setBrush(c2)
        p.drawEllipse(2, 2, 8, 8)
        p.end()


# ═══════════════════════════════════════════════
#  Theme Toggle Switch
# ═══════════════════════════════════════════════

class ThemeSwitch(QWidget):
    """A light/dark segmented control — horizontal pill with '浅色' / '深色' labels."""
    toggled = Signal(str)   # emits 'light' or 'dark'

    def __init__(self, initial="light", parent=None):
        super().__init__(parent)
        self._is_dark = (initial == "dark")
        self.setFixedSize(100, 32)
        self.setCursor(Qt.PointingHandCursor)
        self._update_style()

    def mousePressEvent(self, e):
        self._is_dark = not self._is_dark
        self._update_style()
        self.toggled.emit("dark" if self._is_dark else "light")

    def set_mode(self, mode):
        self._is_dark = (mode == "dark")
        self._update_style()

    def _update_style(self):
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        half = w // 2
        r = h // 2  # full pill radius

        # Container background
        c = QColor(T.LINE)
        p.setBrush(c)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(0, 0, w, h, r, r)

        # Active pill — slides to left (light) or right (dark)
        active_rect = QRect(2, 2, half - 2, h - 4)
        if self._is_dark:
            active_rect = QRect(half, 2, half - 2, h - 4)

        p.setBrush(QColor(T.CARD))
        p.drawRoundedRect(active_rect, r - 2, r - 2)

        # Text
        p.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Medium))
        for i, (txt, is_active) in enumerate([("浅色", not self._is_dark), ("深色", self._is_dark)]):
            tx = i * half
            p.setPen(QColor(T.TEXT) if is_active else QColor(T.TEXT3))
            p.drawText(QRect(tx, 0, half, h), Qt.AlignCenter, txt)

        p.end()


# ═══════════════════════════════════════════════
#  Action Recorder — record mouse/keyboard → task JSON
# ═══════════════════════════════════════════════

class ActionRecorder(QThread):
    """Record user mouse clicks and key presses to generate a task."""
    log = Signal(str, str)  # message, level
    finished = Signal(str)  # task_json_path

    def __init__(self, parent=None, stop_key=None):
        super().__init__(parent)
        self._active = False
        self._events = []
        self._stop_key = stop_key or "Key.f6"  # default: F6

    def stop(self):
        self._active = False

    def run(self):
        self._active = True
        self._events = []
        try:
            from pynput import mouse, keyboard
        except ImportError:
            self.log.emit("请安装 pynput: pip install pynput", "ERROR")
            return

        def on_click(x, y, button, pressed):
            if not self._active:
                return False
            if not pressed:
                return
            if self._events and self._events[-1][1] == "click":
                last_x, last_y = self._events[-1][2][:2]
                if abs(x - last_x) < 3 and abs(y - last_y) < 3:
                    return
            self._events.append((time.time(), "click", (x, y)))
            self.log.emit(f"  📍 点击 ({x}, {y})", "INFO")

        def on_press(key):
            if not self._active:
                return False
            # Check stop key
            current = str(key) if hasattr(key, 'char') else str(key)
            if self._stop_key == current:
                self.log.emit(f"检测到停止快捷键，正在停止录制...", "INFO")
                self._active = False
                return False
            try:
                k = key.char
            except AttributeError:
                k = str(key).replace("Key.", "")
            self._events.append((time.time(), "press", k))
            self.log.emit(f"  ⌨ 按键 {k}", "INFO")

        m_listener = mouse.Listener(on_click=on_click)
        k_listener = keyboard.Listener(on_press=on_press)
        m_listener.start()
        k_listener.start()

        # Keep running until stopped
        while self._active:
            time.sleep(0.1)

        m_listener.stop()
        k_listener.stop()
        self._build_task()

    def _build_task(self):
        if not self._events:
            self.log.emit("没有记录到任何操作", "WARN")
            return
        # Filter: merge clicks at same position, remove sub-second duplicates
        filtered = []
        for ev in self._events:
            if not filtered:
                filtered.append(ev)
                continue
            # Merge if same type and very close position (click) or same key (press)
            if ev[1] == "click" and filtered[-1][1] == "click":
                lx, ly = filtered[-1][2]
                cx, cy = ev[2]
                if abs(cx - lx) < 5 and abs(cy - ly) < 5:
                    continue  # skip duplicate at same spot
            filtered.append(ev)

        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:21]
        task_dir = data_dir(f"tasks/{now}")
        tpl_dir = os.path.join(task_dir, "templates")
        os.makedirs(tpl_dir, exist_ok=True)

        tasks, step_num = {}, 0
        prev_time = filtered[0][0]
        import mss as _m, cv2 as _c

        for ev in filtered:
            ts, etype, data = ev
            gap = ts - prev_time
            prev_time = ts

            # Note: gaps > 2s are intentionally not auto-inserted as steps.
            # Users should use wait_until (visual detection) in the flow editor
            # for robust timing instead of fixed delays.

            step_num += 1
            sid = f"Step{step_num}"

            if etype == "click":
                x, y = data
                # Capture area around click (60x60, focused on target)
                with _m.mss() as sct:
                    cx, cy = max(0, x-30), max(0, y-30)
                    region = {"left": cx, "top": cy, "width": 60, "height": 60}
                    img = sct.grab(region)
                    tpl_name = f"s{step_num}"
                    _c.imwrite(
                        os.path.join(tpl_dir, f"{tpl_name}.png"),
                        _c.cvtColor(np.array(img), _c.COLOR_BGRA2BGR)
                    )
                # Use lower threshold + multi-scale for recorded templates
                tasks[sid] = {
                    "desc": f"点击({x},{y})",
                    "action": "click",
                    "params": {"template": tpl_name, "threshold": 0.7,
                               "multi_scale": True}
                }
            elif etype == "press":
                tasks[sid] = {
                    "desc": f"按键 {data}",
                    "action": "press",
                    "params": {"key": data}
                }

            if step_num > 1:
                tasks[f"Step{step_num-1}"]["next"] = [sid]

        # Write task JSON
        tasks["_meta"] = {
            "name": f"录制_{datetime.datetime.now().strftime('%m月%d日_%H%M')}",
            "created": now,
            "modified": datetime.datetime.now().isoformat()
        }
        with open(os.path.join(task_dir, "task.json"), "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)

        self.log.emit(f"录制完成: {step_num}步 → {task_dir}/task.json", "SUCCESS")
        self.finished.emit(os.path.join(task_dir, "task.json"))


# ═══════════════════════════════════════════════
#  Main Window (2026 Layout)
# ═══════════════════════════════════════════════

class SmartRPAGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = None
        self._running = False
        self._task_map = {}
        sz = QApplication.primaryScreen().size()
        self._region = (0, 0, sz.width(), sz.height())
        self._ed = []
        self._nav_idx = 0
        self._settings = QSettings("SmartRPA", "SmartRPA")
        # Restore theme preference
        saved = self._settings.value("theme", "light")
        T.apply(saved)
        self._build()
        self._scan()
        # Restore schedule preference
        sched_enabled = self._settings.value("schedule/enabled", "false") == "true"
        if hasattr(self, 'sched_cb'):
            self.sched_cb.setChecked(sched_enabled)
        self.setWindowTitle("SmartRPA")
        self.setWindowIcon(QIcon(resource_path("SmartRPA.ico")))
        self.resize(1160, 760)
        self.setMinimumSize(940, 600)
        # Restore schedule task name
        saved_task = self._settings.value("schedule/task", "")
        if saved_task:
            idx = self.task_combo.findText(saved_task)
            if idx >= 0:
                self.task_combo.setCurrentIndex(idx)
        # Restore schedule frequency and time
        saved_freq = self._settings.value("schedule/freq", "每天")
        idx = self.sched_combo.findText(saved_freq)
        if idx >= 0:
            self.sched_combo.setCurrentIndex(idx)
        saved_time = self._settings.value("schedule/time", "")
        if saved_time:
            from PySide6.QtCore import QTime
            self.sched_time.setTime(QTime.fromString(saved_time, "HH:mm"))
        # Check for updates on startup (non-blocking)
        self._check_version()
        # Start global hotkey listener
        self._start_global_hotkey()

    def closeEvent(self, event):
        """Override close: minimize to tray if schedule is active."""
        if hasattr(self, 'sched_cb') and self.sched_cb.isChecked():
            self.hide()
            self._tray.showMessage(
                "SmartRPA",
                "定时已启用，程序继续在后台运行",
                QSystemTrayIcon.MessageIcon.Information, 2000
            )
            event.ignore()
        else:
            event.accept()
        self._stop_global_hotkey()

    def _build(self):
        cw = QWidget()
        self.setCentralWidget(cw)
        root = QHBoxLayout(cw)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ═══ LEFT: Sidebar ═══
        sidebar = QWidget()
        sidebar.setFixedWidth(180)
        sidebar.setStyleSheet(f"background: {T.BG};")
        sb_ly = QVBoxLayout(sidebar)
        sb_ly.setContentsMargins(0, 0, 0, 0)
        sb_ly.setSpacing(0)

        logo_w = QWidget()
        logo_w.setStyleSheet("background: transparent;")
        logo_ly = QHBoxLayout(logo_w)
        logo_ly.setContentsMargins(16, 16, 16, 12)
        self._logo_label = QLabel("SmartRPA")
        self._logo_label.setStyleSheet(f"font-size:16px;font-weight:700;color:{T.TEXT};letter-spacing:-0.3px;")
        logo_ly.addWidget(self._logo_label)
        logo_ly.addStretch()
        sb_ly.addWidget(logo_w)

        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {T.LINE};")
        sb_ly.addWidget(sep)
        sb_ly.addSpacing(8)

        self.nav_btns = []
        nav_items = [("📋","自动化任务"),("🗂","流程编辑"),("✏️","任务编辑器"),("⚙","设置"),("ℹ","关于")]
        for icon, label in nav_items:
            btn = SidebarButton(icon, label)
            btn.clicked.connect(lambda idx=len(self.nav_btns): self._switch_page(idx))
            sb_ly.addWidget(btn)
            self.nav_btns.append(btn)
        self.nav_btns[0].set_active(True)
        sb_ly.addStretch(1)

        bottom_w = QWidget()
        bottom_w.setStyleSheet("background: transparent;")
        bot_ly = QVBoxLayout(bottom_w)
        bot_ly.setContentsMargins(12, 8, 12, 12)
        bot_ly.setSpacing(6)
        self.state_lbl = QLabel("就绪")
        self.state_lbl.setStyleSheet(f"color:{T.TEXT3};font-size:11px;padding:0 4px;")
        bot_ly.addWidget(self.state_lbl)
        self.theme_switch = ThemeSwitch(T.mode)
        self.theme_switch.toggled.connect(self._on_theme_toggle)
        bot_ly.addWidget(self.theme_switch)
        self._ver_label = QLabel(f"v{__version__}")
        self._ver_label.setStyleSheet(f"color:{T.TEXT3};font-size:10px;padding:0 4px;")
        bot_ly.addWidget(self._ver_label)
        sb_ly.addWidget(bottom_w)

        self.sidebar = sidebar
        root.addWidget(sidebar)

        # ═══ Content Area ═══
        self.right_widget = QWidget()
        self.right_widget.setStyleSheet(f"background: {T.BG};")
        right_ly = QVBoxLayout(self.right_widget)
        right_ly.setContentsMargins(0, 0, 0, 0)
        right_ly.setSpacing(0)

        # ── Thin progress bar at top of content area ──
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setMaximumHeight(2)
        self.progress.hide()
        right_ly.addWidget(self.progress)

        # ── Content Stack ──
        self.content_stack = QStackedWidget()
        self._tasks_page = self._tasks_content()
        self._flow_page = self._flow_content()
        self._editor_page = self._editor_content()
        self._settings_page = self._settings_content()
        self._about_page = self._about_content()
        self.content_stack.addWidget(self._tasks_page)     # 0
        self.content_stack.addWidget(self._flow_page)      # 1
        self.content_stack.addWidget(self._editor_page)    # 2
        self.content_stack.addWidget(self._settings_page)  # 3
        self.content_stack.addWidget(self._about_page)     # 4
        right_ly.addWidget(self.content_stack, 1)

        # ── Status Bar ──
        self.status = QStatusBar()
        self.status_lbl = QLabel(" 选择任务后点击「开始运行」")
        self.status_lbl.setStyleSheet(f"color:{T.TEXT3};")
        self.status.addWidget(self.status_lbl, 1)
        self.version_lbl = QLabel(f"v{__version__}")
        self.version_lbl.setStyleSheet(f"color:{T.TEXT3}; font-size:11px; padding:0 8px;")
        self.version_lbl.setCursor(Qt.PointingHandCursor)
        self.status.addPermanentWidget(self.version_lbl)
        self.setStatusBar(self.status)

        root.addWidget(self.right_widget, 1)

        # ── Schedule Timer ──
        self.sched_timer = QTimer(self)
        self.sched_timer.timeout.connect(self._check_schedule)
        self.sched_timer.start(30000)

        # ── System Tray ──
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(QIcon(resource_path("SmartRPA.ico")))
        self._tray.setToolTip("SmartRPA")
        tray_menu = QMenu()
        show_action = tray_menu.addAction("显示窗口")
        show_action.triggered.connect(self.showNormal)
        quit_action = tray_menu.addAction("退出")
        quit_action.triggered.connect(QApplication.quit)
        self._tray.setContextMenu(tray_menu)
        self._tray.activated.connect(lambda reason: self.showNormal() if reason == QSystemTrayIcon.DoubleClick else None)
        self._tray.show()

    # ── Theme Toggle ──

    def _on_theme_toggle(self, mode):
        T.apply(mode)
        self._settings.setValue("theme", mode)
        self.theme_switch.set_mode(mode)
        # Re-apply global QSS
        QApplication.instance().setStyleSheet(build_base_qss())
        # Rebuild all inline styles by refreshing the whole UI
        self._refresh_all_styles()

    def _refresh_all_styles(self):
        """Refresh all inline styles after theme switch."""
        # Top nav bar
        self.sidebar.setStyleSheet(f"background: {T.BG};")

        self.right_widget.setStyleSheet(f"background: {T.BG};")

        # Logo
        if hasattr(self, '_logo_label'):
            self._logo_label.setStyleSheet(f"font-size:16px;font-weight:700;color:{T.TEXT};letter-spacing:-0.3px;")

        # Version label
        if hasattr(self, '_ver_label'):
            self._ver_label.setStyleSheet(f"""
                font-size: 11px;
                color: {T.TEXT3};
                padding: 0 4px 0 8px;
            """)

        # Status label
        if not self._running:
            self.state_lbl.setStyleSheet(f"color:{T.TEXT2}; font-size:12px; font-weight:500; padding: 0 8px 0 4px;")
        else:
            self.state_lbl.setStyleSheet(f"color:{T.ACCENT2}; font-size:12px; font-weight:600; padding: 0 8px 0 4px;")

        # Re-style run button
        self.run_btn.setStyleSheet("")  # clear cached template
        self._update_run_btn_style()



        # Bottom status bar
        self.status_lbl.setStyleSheet(f"color:{T.TEXT3};")
        if hasattr(self, 'version_lbl'):
            cur_text = self.version_lbl.text()
            if cur_text.startswith("⬆"):
                self.version_lbl.setStyleSheet(
                    f"color:{T.ACCENT2}; font-size:11px; font-weight:600; padding:0 8px; text-decoration:underline;")
            else:
                self.version_lbl.setStyleSheet(f"color:{T.TEXT3}; font-size:11px; padding:0 8px;")

        # Nav buttons
        for i, btn in enumerate(self.nav_btns):
            btn._update_style()

        # Theme switch
        self.theme_switch._update_style()

        # Refresh content pages
        self._refresh_tasks_styles()
        self._refresh_editor_styles()
        self._refresh_settings_styles()
        self._refresh_about_styles()

    def _refresh_tasks_styles(self):
        """Refresh the tasks page inline styles."""
        page = self._tasks_page
        page.setStyleSheet(f"background:{T.BG};")

        # Config card
        if hasattr(self, '_config_card'):
            self._config_card.setStyleSheet(f"""
                background: {T.CARD};
                border: none;
                border-radius: {T.R_LG}px;
            """)

        # Log card
        if hasattr(self, '_log_card'):
            self._log_card.setStyleSheet(f"""
                background: {T.CARD};
                border: none;
                border-radius: {T.R_LG}px;
            """)

        # Task combo & template combo (green pills)
        for combo in [self.task_combo, self.tpl_combo]:
            if hasattr(self, 'task_combo'):
                combo.setStyleSheet(f"""
                    QComboBox {{
                        background: {T.CARD};
                        color: {T.TEXT};
                        border: 1px solid {T.LINE};
                        border-radius: {T.R_SM}px;
                        padding: 5px 14px;
                        min-height: 26px;
                        max-height: 26px;
                        font-weight: 600;
                        font-size: 12px;
                    }}
                    QComboBox::drop-down {{ border: none; width: 24px; }}
                    QComboBox:hover {{
                        background: {T.SURFACE};
                        border: 1px solid {T.LINE_LIGHT};
                    }}
                """)

        # QSplitter handle
        for splitter in page.findChildren(QSplitter):
            splitter.setStyleSheet(f"QSplitter::handle{{background:{T.LINE};}}")

        # Log panel
        self.log.setStyleSheet(f"""
            background: {T.LOG_BG};
            color: {T.LOG_TEXT};
            border: 1px solid {T.LINE};
            border-radius: {T.R_MD}px;
            padding: 14px;
            font-size: 12px;
            selection-background-color: {T.ACCENT_DIM};
        """)

        # Region pill
        self.region_lbl.setStyleSheet(f"""
            color: {T.GREEN};
            font-size: 12px;
            font-weight: 600;
            padding: 4px 10px;
            min-height: 26px;
            max-height: 26px;
            background: {T.GREEN_BG};
            border-radius: {T.R_SM}px;
            border: 1px solid {T.GREEN}22;
        """)

    def _refresh_editor_styles(self):
        """Refresh the editor page inline styles."""
        self._editor_page.setStyleSheet(f"background:{T.BG};")

        # Editor name combo
        if hasattr(self, 'ed_name'):
            self.ed_name.setStyleSheet(f"""QComboBox{{background:{T.CARD};color:{T.TEXT};border:1px solid {T.LINE};border-radius:{T.R_SM}px;padding:5px 14px;min-height:26px;max-height:26px;font-weight:600;font-size:12px;}}QComboBox::drop-down{{border:none;width:24px;}}QComboBox:hover{{background:{T.SURFACE};border:1px solid {T.LINE_LIGHT};}}""")

        # Editor steps list
        if hasattr(self, 'ed_list'):
            self.ed_list.setStyleSheet(f"""QListWidget{{background:{T.SURFACE};color:{T.TEXT};border:1px solid {T.LINE};border-radius:{T.R_MD}px;padding:8px;font-size:12px;outline:none;}}QListWidget::item{{padding:6px 10px;border-radius:4px;}}QListWidget::item:selected{{background:{T.ACCENT_DIM};color:{T.TEXT};}}QListWidget::item:hover{{background:{T.CARD_HOVER};}}""")

        # Editor loop spinbox
        if hasattr(self, 'run_loop'):
            self.run_loop.setStyleSheet(f"QSpinBox{{background:{T.CARD};color:{T.TEXT};border:1px solid {T.LINE};border-radius:{T.R_SM}px;padding:5px 14px;min-height:26px;max-height:26px;font-weight:600;font-size:12px;}}QSpinBox::up-button,QSpinBox::down-button{{border:none;width:20px;background:transparent;}}QSpinBox:hover{{border:1px solid {T.LINE_LIGHT};}}")

        # Preview label
        if hasattr(self, '_ed_preview'):
            self._ed_preview.setStyleSheet(f"background:{T.SURFACE};color:{T.TEXT3};border:1px solid {T.LINE};border-radius:{T.R_SM}px;font-size:11px;")

        # Page title & subtitle
        for label in self._editor_page.findChildren(QLabel):
            txt = label.text()
            if txt == "任务编辑器":
                label.setStyleSheet(f"font-size:24px; font-weight:700; color:{T.TEXT}; letter-spacing:-0.5px;")
            elif txt == "无需写代码，点击屏幕即可创建自动化任务。":
                label.setStyleSheet(f"font-size:14px; color:{T.TEXT2}; font-weight:400;")

        # Recording button
        if hasattr(self, 'rec_btn'):
            self.rec_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {T.RED_BG}; color: {T.RED};
                    border: 1px solid {T.RED}33; border-radius: {T.R_SM}px;
                    padding: 5px 14px; font-weight: 600; font-size: 12px;
                }}
                QPushButton:hover {{ border: 1px solid {T.RED}66; }}
            """)

    def _refresh_about_styles(self):
        """Refresh the about page inline styles."""
        self._about_page.setStyleSheet(f"background:{T.BG};")
        if hasattr(self, '_about_card'):
            self._about_card.setStyleSheet(f"""
                background: {T.CARD};
                border: none;
                border-radius: {T.R_XL}px;
            """)
        # About page text labels
        if hasattr(self, '_about_icon'):
            self._about_icon.setStyleSheet(f"font-size:48px; color:{T.ACCENT}; background:transparent;")
        if hasattr(self, '_about_title'):
            self._about_title.setStyleSheet(f"font-size:28px; font-weight:800; color:{T.TEXT}; letter-spacing:-1px;")
        if hasattr(self, '_about_desc'):
            self._about_desc.setStyleSheet(f"color:{T.TEXT2}; font-size:15px;")
        if hasattr(self, '_about_ver'):
            self._about_ver.setStyleSheet(f"color:{T.ACCENT}; font-size:13px; font-weight:600; padding:4px 16px; background:{T.ACCENT_DIM}; border-radius:{T.R_SM}px;")
        if hasattr(self, '_about_tech'):
            self._about_tech.setStyleSheet(f"color:{T.TEXT3}; font-size:12px; letter-spacing:0.5px;")

    # ── Page Switching ──

    def _switch_page(self, idx):
        self._nav_idx = idx
        self.content_stack.setCurrentIndex(idx)
        for i, btn in enumerate(self.nav_btns):
            btn.set_active(i == idx)

    # ── Schedule ──

    def _on_sched_toggle(self, enabled):
        self._settings.setValue("schedule/enabled", enabled)
        self._settings.setValue("schedule/freq", self.sched_combo.currentText())
        self._settings.setValue("schedule/time", self.sched_time.time().toString("HH:mm"))
        # Save current task name
        task_name = self.task_combo.currentText()
        if task_name and enabled:
            self._settings.setValue("schedule/task", task_name)
        if enabled:
            self._update_sched_next()
            self._tray.setToolTip(f"SmartRPA - 定时已启用 ({self.sched_combo.currentText()} {self.sched_time.time().toString('HH:mm')})")
            self.showMinimized()
            self.log_msg(f"定时已启用: {self.sched_combo.currentText()} {self.sched_time.time().toString('HH:mm')} - 任务: {task_name}", "INFO")
        else:
            self.sched_next.setText("")
            self._tray.setToolTip("SmartRPA")

    def _calc_next_run(self):
        from datetime import datetime, timedelta
        if not self.sched_cb.isChecked():
            return None
        now = datetime.now()
        if self.sched_combo.currentText() == "每小时":
            return now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        t = self.sched_time.time()
        nxt = now.replace(hour=t.hour(), minute=t.minute(), second=0, microsecond=0)
        return nxt + timedelta(days=1) if nxt <= now else nxt

    def _update_sched_next(self):
        nxt = self._calc_next_run()
        self.sched_next.setText(f"下次运行: {nxt.strftime('%H:%M')}" if nxt else "")

    def _check_schedule(self):
        if not self.sched_cb.isChecked() or self._running:
            self._update_sched_next()
            return
        from datetime import datetime
        nxt = self._calc_next_run()
        if nxt and datetime.now() >= nxt:
            # Run the scheduled task (not necessarily the currently selected one)
            sched_task = self._settings.value("schedule/task", "")
            if sched_task and sched_task in self._task_map:
                idx = self.task_combo.findText(sched_task)
                if idx >= 0:
                    self.task_combo.setCurrentIndex(idx)
            self.log_msg("定时触发: 自动开始运行", "INFO")
            self._start()

    def _check_version(self, force_notify=False):
        """Background thread: check GitHub for newer release."""
        repo = "virmuran/SmartRPA"
        import threading

        def _do_check():
            import json, urllib.request, ssl
            url = f"https://api.github.com/repos/{repo}/releases/latest"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "SmartRPA/0.5"})
                # Try to use system proxy if available
                proxy_handler = urllib.request.ProxyHandler()
                opener = urllib.request.build_opener(proxy_handler)
                with opener.open(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
                    latest = data.get("tag_name", "").lstrip("v")

                    # Compare versions
                    cur = tuple(int(x) for x in __version__.split("."))
                    lat = tuple(int(x) for x in latest.split("."))
                    if lat > cur:
                        self._on_new_version(latest, data.get("html_url", url))
                    elif force_notify:
                        self._on_no_update()
            except Exception as e:
                if force_notify:
                    # If check failed but user clicked button, offer to open browser
                    self._on_check_failed_with_option()

        threading.Thread(target=_do_check, daemon=True).start()

    def _on_new_version(self, latest, url):
        """Called from background thread; schedule UI update on main thread."""
        from PySide6.QtCore import QMetaObject, Qt, Q_ARG
        QMetaObject.invokeMethod(
            self, "_show_update_banner",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, latest), Q_ARG(str, url)
        )

    @Slot(str, str)
    def _show_update_banner(self, latest, url):
        self.version_lbl.setText(f"⬆ v{latest} 可用")
        self.version_lbl.setStyleSheet(
            f"color:{T.ACCENT2}; font-size:11px; font-weight:600; padding:0 8px; text-decoration:underline;")
        self.version_lbl.setToolTip(f"点击下载 SmartRPA v{latest}")
        self.version_lbl.mousePressEvent = lambda e: QDesktopServices.openUrl(QUrl(url))
        if hasattr(self, '_update_status'):
            self._update_status.setText(f"发现新版本 v{latest}")
            self._update_status.setStyleSheet(f"font-size:12px; color:{T.ACCENT2}; font-weight:600;")
            self._update_status.mousePressEvent = lambda e: QDesktopServices.openUrl(QUrl(url))
            self._update_status.setCursor(Qt.PointingHandCursor)
        self.log_msg(f"新版本 v{latest} 可用，点击状态栏下载", "INFO")

    @Slot()
    def _on_no_update(self):
        self._update_status.setText("已是最新版 ✓")
        self._update_status.setStyleSheet(f"font-size:12px; color:{T.TEXT2};")
        self.log_msg(f"当前已是 v{__version__} 最新版", "SUCCESS")

    @Slot()
    def _on_check_failed_with_option(self):
        self._update_status.setText("检查失败，点此手动查看")
        self._update_status.setStyleSheet(f"font-size:12px; color:{T.ORANGE}; text-decoration:underline;")
        repo_url = "https://github.com/virmuran/SmartRPA/releases"
        self._update_status.mousePressEvent = lambda e: QDesktopServices.openUrl(QUrl(repo_url))
        self._update_status.setCursor(Qt.PointingHandCursor)
        self.log_msg("版本检查失败（网络/代理），可手动查看 Releases", "WARN")

    # ══════════════════════════════════════
    #  PAGE: 自动化任务 (3-column Bento)
    # ══════════════════════════════════════
    #  PAGE: 流程编辑 (full-screen BT/flow view)
    # ══════════════════════════════════════

    def _flow_content(self):
        w = QWidget()
        w.setStyleSheet(f"background:{T.BG};")
        ly = QVBoxLayout(w)
        ly.setContentsMargins(0, 0, 0, 0)
        ly.setSpacing(0)

        # ── Top bar: task selector ──
        top = QWidget()
        top.setStyleSheet(f"background:{T.CARD};border-bottom:1px solid {T.LINE};")
        top_ly = QHBoxLayout(top)
        top_ly.setContentsMargins(T.SP_LG, T.SP_SM, T.SP_LG, T.SP_SM)
        top_ly.setSpacing(T.SP_MD)

        top_ly.addWidget(section_header("任务"))

        self.flow_task_combo = QComboBox()
        self.flow_task_combo.setMinimumWidth(240)
        self.flow_task_combo.setStyleSheet(f"""
            QComboBox {{background:{T.SURFACE};color:{T.TEXT};border:1px solid {T.LINE};
                border-radius:{T.R_SM}px;padding:4px 12px;min-height:26px;max-height:26px;
                font-size:12px;}}
            QComboBox::drop-down {{border:none;width:22px;}}
            QComboBox QAbstractItemView {{background:{T.CARD};color:{T.TEXT};}}
        """)
        self.flow_task_combo.currentTextChanged.connect(self._on_flow_task_selected)
        top_ly.addWidget(self.flow_task_combo)
        top_ly.addStretch(1)

        ly.addWidget(top)

        # ── Flow editor (full canvas) ──
        self.flow_editor = FlowEditor()
        self.flow_editor.taskEdited.connect(lambda path, data: self._on_flow_saved(path))
        ly.addWidget(self.flow_editor, 1)
        return w

    def _on_flow_saved(self, path):
        """Refresh task list after flow editor save."""
        self.log_msg(f"已保存: {os.path.basename(path)}", "SUCCESS")
        self._scan()

    def _on_flow_task_selected(self, name):
        """When a task is selected in the flow editor page, load it."""
        if not name:
            return
        path = self._task_map.get(name)
        if not path:
            return
        self.flow_editor.set_current_file(path)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            self.log_msg(f"加载失败: {e}", "ERROR")
            return
        if "root" in data:
            self.flow_editor.load_bt_tree(data["root"])
        else:
            steps = {k: v for k, v in data.items()
                     if isinstance(v, dict) and not k.startswith('_') and "action" in v}
            if steps:
                referenced = set()
                for k, v in steps.items():
                    for n in (v.get("next") or []):
                        referenced.add(n)
                entry = next((k for k in steps if k not in referenced), list(steps.keys())[0])
                self.flow_editor.load_flat_tasks(steps, entry)

    # ══════════════════════════════════════

    def _tasks_content(self):
        page = QWidget()
        page.setStyleSheet(f"background:{T.BG};")
        ly = QVBoxLayout(page)
        ly.setContentsMargins(T.SP_LG, T.SP_LG, T.SP_LG, T.SP_LG)
        ly.setSpacing(T.SP_LG)
        # Two columns: left (task list top, config bottom) | right (log)
        h_split = QSplitter(Qt.Horizontal)
        h_split.setHandleWidth(1)
        h_split.setStyleSheet(f"QSplitter::handle{{background:{T.LINE};}}")

        # LEFT: MAA-style task panel
        left_w = QWidget()
        left_w.setStyleSheet(f"background:{T.BG};")
        left_ly = QVBoxLayout(left_w)
        left_ly.setContentsMargins(0, 0, 0, 0)
        left_ly.setSpacing(T.SP_LG)

        # Task checklist panel
        task_panel = QWidget()
        task_panel.setStyleSheet(f"background:{T.CARD}; border:none; border-radius:{T.R_LG}px;")
        task_layout = QVBoxLayout(task_panel)
        task_layout.setContentsMargins(T.SP_LG, T.SP_LG, T.SP_LG, T.SP_LG)
        task_layout.setSpacing(T.SP_MD)

        task_header = QHBoxLayout()
        task_header.addWidget(section_title("任务"))
        task_header.addStretch()
        task_layout.addLayout(task_header)

        self.task_list = QListWidget()
        self.task_list.setFont(QFont("Microsoft YaHei", 10))
        self.task_list.setStyleSheet(f"""
            QListWidget {{
                background: {T.SURFACE};
                color: {T.TEXT};
                border: 1px solid {T.LINE};
                border-radius: {T.R_MD}px;
                padding: 8px;
                font-size: 12px;
                outline: none;
            }}
            QListWidget::item {{
                padding: 0px;
                border-radius: 4px;
                min-height: 32px;
            }}
            QListWidget::item:selected {{
                background: {T.ACCENT_DIM};
                color: {T.TEXT};
            }}
            QListWidget::item:hover {{
                background: {T.CARD_HOVER};
            }}
        """)
        task_layout.addWidget(self.task_list, 1)

        # Bulk action buttons
        bulk_row = QHBoxLayout()
        bulk_row.setSpacing(T.SP_SM)
        select_all_btn = btn_ghost("全选")
        select_all_btn.clicked.connect(self._select_all_tasks)
        bulk_row.addWidget(select_all_btn)

        invert_btn = btn_ghost("反选")
        invert_btn.clicked.connect(self._invert_task_selection)
        bulk_row.addWidget(invert_btn)

        clear_sel_btn = btn_ghost("清空")
        clear_sel_btn.clicked.connect(self._clear_task_checks)
        bulk_row.addWidget(clear_sel_btn)
        bulk_row.addStretch()
        task_layout.addLayout(bulk_row)

        left_ly.addWidget(task_panel, 1)

        # Config card
        self._config_card = QWidget()
        self._config_card.setStyleSheet(f"""
            background: {T.CARD};
            border: none;
            border-radius: {T.R_LG}px;
        """)
        Cl = QVBoxLayout(self._config_card)
        Cl.setContentsMargins(T.SP_XL, T.SP_XL, T.SP_XL, T.SP_XL)
        Cl.setSpacing(T.SP_LG)

        # Hidden combo for logic (synced with task_list)
        self.task_combo = QComboBox()
        self.task_combo.setStyleSheet(f"""
            QComboBox {{
                background: {T.CARD};
                color: {T.TEXT};
                border: 1px solid {T.LINE};
                border-radius: {T.R_SM}px;
                padding: 5px 14px;
                min-height: 26px;
                max-height: 26px;
                font-weight: 600;
                font-size: 12px;
            }}
            QComboBox::drop-down {{ border: none; width: 24px; }}
            QComboBox:hover {{ background: {T.SURFACE}; border: 1px solid {T.LINE_LIGHT}; }}
        """)
        self.task_combo.currentIndexChanged.connect(self._on_task_changed)
        self.task_combo.hide()
        Cl.addWidget(self.task_combo)
        Cl.addWidget(section_title("模板路径"))
        tpb = QHBoxLayout()
        tpb.setSpacing(T.SP_SM)
        self.tpl_combo = QComboBox()
        self.tpl_combo.setEditable(True)
        self.tpl_combo.setStyleSheet(f"""
            QComboBox {{
                background: {T.CARD};
                color: {T.TEXT};
                border: 1px solid {T.LINE};
                border-radius: {T.R_SM}px;
                padding: 5px 14px;
                min-height: 26px;
                max-height: 26px;
                font-weight: 600;
                font-size: 12px;
            }}
            QComboBox::drop-down {{ border: none; width: 24px; }}
            QComboBox:hover {{ background: {T.SURFACE}; border: 1px solid {T.LINE_LIGHT}; }}
        """)
        tpb.addWidget(self.tpl_combo, 1)
        browse_btn = btn_ghost("浏览")
        browse_btn.setFixedWidth(64)
        browse_btn.clicked.connect(self._browse_tpl)
        tpb.addWidget(browse_btn)
        Cl.addLayout(tpb)

        # Compact row: 操作区域 + 重复 + 速度
        compact_row = QHBoxLayout()
        compact_row.setSpacing(T.SP_SM)
        self.region_lbl = status_pill("全屏")
        compact_row.addWidget(self.region_lbl, 1)
        region_btn = btn_ghost("框选")
        region_btn.setFixedWidth(48)
        region_btn.clicked.connect(self._select_region)
        compact_row.addWidget(region_btn)
        compact_row.addSpacing(T.SP_MD)
        self.run_loop = QSpinBox()
        self.run_loop.setRange(1, 9999)
        self.run_loop.setValue(1)
        self.run_loop.setFixedWidth(64)
        self.run_loop.setStyleSheet(f"QSpinBox{{background:{T.CARD};color:{T.TEXT};border:1px solid {T.LINE};border-radius:{T.R_SM}px;padding:5px 14px;min-height:26px;max-height:26px;font-weight:600;font-size:12px;}}QSpinBox::up-button,QSpinBox::down-button{{border:none;width:20px;background:transparent;}}QSpinBox:hover{{border:1px solid {T.LINE_LIGHT};}}")
        compact_row.addWidget(self.run_loop)
        tl = QLabel("次")
        tl.setStyleSheet(f"font-size:13px;font-weight:500;color:{T.TEXT2};")
        compact_row.addWidget(tl)
        compact_row.addSpacing(T.SP_MD)
        self.fast_toggle = QPushButton("⚡ 极速")
        self.fast_toggle.setCheckable(True)
        self.fast_toggle.setCursor(Qt.PointingHandCursor)
        self.fast_toggle.setMinimumHeight(26)
        self.fast_toggle.setMaximumHeight(26)
        self.fast_toggle.toggled.connect(self._on_speed_toggle)
        self._update_speed_btn_style(False)
        compact_row.addWidget(self.fast_toggle)
        compact_row.addStretch()
        Cl.addLayout(compact_row)
        Cl.addStretch(1)

        self.run_btn = QPushButton("▶  开始运行")
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.setMinimumHeight(36)
        self.run_btn.setMaximumHeight(36)
        self.run_btn.clicked.connect(self._toggle_run)
        Cl.addWidget(self.run_btn)
        self._update_run_btn_style()

        left_ly.addWidget(self._config_card)
        h_split.addWidget(left_w)

        # RIGHT: Log Panel (full height)
        self._log_card = QWidget()
        self._log_card.setStyleSheet(f"""
            background: {T.CARD};
            border: none;
            border-radius: {T.R_LG}px;
        """)
        Rl = QVBoxLayout(self._log_card)
        Rl.setContentsMargins(T.SP_LG, T.SP_XL, T.SP_LG, T.SP_LG)
        Rl.setSpacing(T.SP_MD)
        log_header = QHBoxLayout()
        log_header.setSpacing(T.SP_SM)
        log_header.addWidget(section_header("日志"))
        log_header.addStretch()
        copy_btn = btn_ghost("复制")
        copy_btn.setToolTip("复制日志到剪贴板")
        copy_btn.clicked.connect(self._copy_log)
        log_header.addWidget(copy_btn)
        Rl.addLayout(log_header)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet(f"""
            background: {T.LOG_BG};
            color: {T.LOG_TEXT};
            border: 1px solid {T.LINE};
            border-radius: {T.R_MD}px;
            padding: 14px;
            font-size: 12px;
            selection-background-color: {T.ACCENT_DIM};
        """)
        self.log.setFont(QFont("Cascadia Code,Consolas,monospace", 10))
        self.log.document().setMaximumBlockCount(2000)
        Rl.addWidget(self.log, 1)
        clr_log_row = QHBoxLayout()
        clr_log_row.setSpacing(T.SP_SM)
        clr_log_btn = btn_ghost("清空日志")
        clr_log_btn.clicked.connect(self._clear_log)
        clr_log_row.addWidget(clr_log_btn)
        clr_log_row.addStretch()
        Rl.addLayout(clr_log_row)

        h_split.addWidget(self._log_card)
        h_split.setSizes([460, 560])
        ly.addWidget(h_split, 1)
        return page
    def _on_task_list_selected(self, idx):
        """Clicking a task row selects it for configuration (without toggling checkbox)."""
        if idx < 0:
            return
        item = self.task_list.item(idx)
        if not item:
            return
        task_name = item.data(Qt.UserRole)
        combo_idx = self.task_combo.findText(task_name)
        if combo_idx >= 0:
            self.task_combo.setCurrentIndex(combo_idx)

    def _add_task_checklist_item(self, name: str, checked: bool = True):
        """Add a MAA-style checklist row: checkbox + name + settings gear."""
        item = QListWidgetItem()
        item.setData(Qt.UserRole, name)
        item.setSizeHint(QSize(self.task_list.width() - 20, 34))
        self.task_list.addItem(item)

        row_w = QWidget()
        row_ly = QHBoxLayout(row_w)
        row_ly.setContentsMargins(8, 2, 8, 2)
        row_ly.setSpacing(8)

        cb = QCheckBox()
        cb.setChecked(checked)
        cb.stateChanged.connect(lambda state, it=item: it.setData(Qt.UserRole + 1, state == Qt.Checked))
        row_ly.addWidget(cb)

        lbl = QLabel(name)
        lbl.setStyleSheet(f"font-size:12px; color:{T.TEXT};")
        lbl.setWordWrap(False)
        row_ly.addWidget(lbl, 1)

        gear = QPushButton("⚙")
        gear.setFixedSize(24, 24)
        gear.setCursor(Qt.PointingHandCursor)
        gear.setToolTip("配置此任务")
        gear.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {T.TEXT2}; font-size: 12px;
                border-radius: 4px;
            }}
            QPushButton:hover {{ background: {T.SURFACE}; color: {T.ACCENT}; }}
        """)
        gear.clicked.connect(lambda checked, n=name: self._configure_task(n))
        row_ly.addWidget(gear)

        self.task_list.setItemWidget(item, row_w)
        # Store initial check state
        item.setData(Qt.UserRole + 1, checked)

    def _configure_task(self, name: str):
        """Select a task in the combo so the global config applies to it."""
        combo_idx = self.task_combo.findText(name)
        if combo_idx >= 0:
            self.task_combo.setCurrentIndex(combo_idx)
        # Also select in list
        for i in range(self.task_list.count()):
            if self.task_list.item(i).data(Qt.UserRole) == name:
                self.task_list.setCurrentRow(i)
                break
        self.log_msg(f"已选择任务进行配置: {name}", "INFO")

    def _checked_task_names(self) -> List[str]:
        """Return list of currently checked task display names."""
        names = []
        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            if item.data(Qt.UserRole + 1):
                names.append(item.data(Qt.UserRole))
        return names

    def _select_all_tasks(self):
        """Check all tasks."""
        self._set_all_tasks_checked(True)

    def _clear_task_checks(self):
        """Uncheck all tasks."""
        self._set_all_tasks_checked(False)

    def _invert_task_selection(self):
        """Invert check state of all tasks."""
        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            widget = self.task_list.itemWidget(item)
            if widget:
                cb = widget.layout().itemAt(0).widget()
                cb.setChecked(not cb.isChecked())

    def _set_all_tasks_checked(self, checked: bool):
        """Set all task checkboxes to the given state."""
        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            widget = self.task_list.itemWidget(item)
            if widget:
                cb = widget.layout().itemAt(0).widget()
                cb.setChecked(checked)

    def _toggle_run(self):
        if self._running:
            self._stop()
        else:
            self._start()

    def _update_run_btn_style(self):
        """Update the run/stop button style based on running state."""
        if self._running:
            self.run_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {T.RED_BG};
                    color: {T.RED};
                    border: 1px solid {T.DANGER_BORDER};
                    border-radius: {T.R_SM}px;
                    font-weight: 600;
                    font-size: 12px;
                    padding: 5px 0;
                    min-height: 26px;
                    max-height: 26px;
                }}
                QPushButton:hover {{
                    background: {T.DANGER_HOVER_BG};
                    border-color: {T.RED};
                }}
            """)
        else:
            self.run_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {T.ACCENT};
                    color: white;
                    border: none;
                    border-radius: {T.R_SM}px;
                    font-weight: 600;
                    font-size: 12px;
                    padding: 5px 0;
                    min-height: 26px;
                    max-height: 26px;
                }}
                QPushButton:hover {{
                    background: {T.ACCENT2};
                }}
            """)

    def _on_speed_toggle(self, checked):
        self._update_speed_btn_style(checked)

    def _update_speed_btn_style(self, fast):
        if fast:
            self.fast_toggle.setStyleSheet(
                f"QPushButton{{background:{T.SURFACE};color:{T.TEXT};"
                f"border:1px solid {T.LINE_LIGHT};border-radius:{T.R_SM}px;"
                f"padding:4px 10px;font-weight:700;font-size:12px;"
                f"min-height:26px;max-height:26px;}}"
                f"QPushButton:hover{{border:1px solid {T.TEXT2};}}"
            )
        else:
            self.fast_toggle.setStyleSheet(
                f"QPushButton{{background:{T.CARD};color:{T.TEXT2};"
                f"border:1px solid {T.LINE};border-radius:{T.R_SM}px;"
                f"padding:4px 10px;font-weight:600;font-size:12px;"
                f"min-height:26px;max-height:26px;}}"
                f"QPushButton:hover{{border:1px solid {T.LINE_LIGHT};}}"
            )

    def _editor_content(self):
        w = QWidget()
        w.setStyleSheet(f"background:{T.BG};")
        ly = QVBoxLayout(w)
        ly.setContentsMargins(T.SP_LG, T.SP_LG, T.SP_LG, T.SP_LG)
        ly.setSpacing(0)

        split = QSplitter(Qt.Horizontal)
        split.setHandleWidth(1)
        split.setStyleSheet(f"QSplitter::handle{{background:{T.LINE};}}")

        # ═══ LEFT: task list ═══
        left_panel = QWidget()
        left_panel.setStyleSheet(f"background:{T.CARD}; border:none; border-radius:{T.R_LG}px;")
        left_ly = QVBoxLayout(left_panel)
        left_ly.setContentsMargins(T.SP_LG, T.SP_LG, T.SP_LG, T.SP_LG)
        left_ly.setSpacing(T.SP_MD)

        left_ly.addWidget(section_title("任务列表"))
        self.ed_task_list = QListWidget()
        self.ed_task_list.setFont(QFont("Microsoft YaHei", 10))
        self.ed_task_list.setStyleSheet(f"""QListWidget{{background:{T.SURFACE};color:{T.TEXT};border:1px solid {T.LINE};border-radius:{T.R_MD}px;padding:8px;font-size:12px;outline:none;}}QListWidget::item{{padding:6px 10px;border-radius:4px;}}QListWidget::item:selected{{background:{T.ACCENT_DIM};color:{T.TEXT};}}QListWidget::item:hover{{background:{T.CARD_HOVER};}}""")
        self.ed_task_list.currentRowChanged.connect(self._ed_task_selected)
        left_ly.addWidget(self.ed_task_list, 1)
        split.addWidget(left_panel)

        # ═══ MID: operations ═══
        mid_panel = QWidget()
        mid_panel.setStyleSheet(f"background:{T.CARD}; border:none; border-radius:{T.R_LG}px;")
        mid_ly = QVBoxLayout(mid_panel)
        mid_ly.setContentsMargins(T.SP_LG, T.SP_LG, T.SP_LG, T.SP_LG)
        mid_ly.setSpacing(T.SP_MD)

        mid_ly.addWidget(section_title("任务名称"))
        self.ed_name = QComboBox()
        self.ed_name.setEditable(True)
        self.ed_name.setStyleSheet(f"""QComboBox{{background:{T.CARD};color:{T.TEXT};border:1px solid {T.LINE};border-radius:{T.R_SM}px;padding:5px 14px;min-height:26px;max-height:26px;font-weight:600;font-size:12px;}}QComboBox::drop-down{{border:none;width:24px;}}QComboBox:hover{{background:{T.SURFACE};border:1px solid {T.LINE_LIGHT};}}""")
        mid_ly.addWidget(self.ed_name)

        mid_ly.addWidget(section_title("操作"))
        op_row = QHBoxLayout(); op_row.setSpacing(T.SP_SM)
        for label, act in [("+ 点击","click"), ("+ 按键","press"), ("+ 等到","wait_until")]:
            b = btn_ghost(label); b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda checked, a=act: self._ed_add(a))
            op_row.addWidget(b)
        op_row.addStretch()
        mid_ly.addLayout(op_row)

        # Recording row
        rec_row = QHBoxLayout(); rec_row.setSpacing(T.SP_SM)
        self.rec_btn = QPushButton("⏺ 录制")
        self.rec_btn.setCursor(Qt.PointingHandCursor)
        self.rec_btn.setMinimumHeight(26)
        self.rec_btn.setMaximumHeight(26)
        self.rec_btn.clicked.connect(self._toggle_record)
        self.rec_btn.setStyleSheet(f"""
            QPushButton {{
                background: {T.RED_BG}; color: {T.RED};
                border: 1px solid {T.RED}33; border-radius: {T.R_SM}px;
                padding: 4px 10px; font-weight: 600; font-size: 12px;
                min-height: 26px; max-height: 26px;
            }}
            QPushButton:hover {{ border: 1px solid {T.RED}66; }}
        """)
        rec_row.addWidget(self.rec_btn)
        rec_row.addStretch()
        mid_ly.addLayout(rec_row)

        mid_ly.addWidget(section_title("预览"))
        self._ed_preview = QLabel("选择步骤查看预览")
        self._ed_preview.setMinimumHeight(160)
        self._ed_preview.setAlignment(Qt.AlignCenter)
        self._ed_preview.setStyleSheet(f"background:{T.SURFACE};color:{T.TEXT3};border:1px solid {T.LINE};border-radius:{T.R_SM}px;font-size:11px;")
        mid_ly.addWidget(self._ed_preview)

        del_row = QHBoxLayout(); del_row.setSpacing(T.SP_SM)
        del_btn = btn_ghost("删除"); del_btn.setToolTip("删除选中步骤")
        del_btn.clicked.connect(self._ed_del); del_row.addWidget(del_btn)
        edit_btn = btn_ghost("编辑"); edit_btn.setToolTip("编辑选中步骤参数")
        edit_btn.clicked.connect(self._ed_edit_step); del_row.addWidget(edit_btn)
        copy_btn = btn_ghost("复制"); copy_btn.setToolTip("复制选中步骤")
        copy_btn.clicked.connect(self._ed_copy_step); del_row.addWidget(copy_btn)
        clr_btn = btn_ghost("清空"); clr_btn.clicked.connect(self._ed_clr); del_row.addWidget(clr_btn)
        del_row.addStretch(); mid_ly.addLayout(del_row)

        mid_ly.addStretch(1)
        save = btn_primary("保存任务")
        save.clicked.connect(self._ed_save)
        mid_ly.addWidget(save)
        split.addWidget(mid_panel)

        # ═══ RIGHT: steps list ═══
        right_panel = QWidget()
        right_panel.setStyleSheet(f"background:{T.CARD};border:none;border-radius:{T.R_LG}px;")
        right_ly = QVBoxLayout(right_panel)
        right_ly.setContentsMargins(T.SP_LG, T.SP_LG, T.SP_LG, T.SP_LG)
        right_ly.setSpacing(T.SP_MD)
        right_ly.addWidget(section_title("步骤 (拖拽排序)"))

        self.ed_list = QListWidget()
        self.ed_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.ed_list.setDefaultDropAction(Qt.MoveAction)
        self.ed_list.setFont(QFont("Microsoft YaHei", 10))
        self.ed_list.setStyleSheet(f"""QListWidget{{background:{T.SURFACE};color:{T.TEXT};border:1px solid {T.LINE};border-radius:{T.R_MD}px;padding:8px;font-size:12px;outline:none;}}QListWidget::item{{padding:6px 10px;border-radius:4px;}}QListWidget::item:selected{{background:{T.ACCENT_DIM};color:{T.TEXT};}}QListWidget::item:hover{{background:{T.CARD_HOVER};}}""")
        self.ed_list.currentRowChanged.connect(self._on_ed_step_selected)
        self.ed_list.itemDoubleClicked.connect(self._ed_edit_step)
        right_ly.addWidget(self.ed_list, 1)
        split.addWidget(right_panel)

        split.setSizes([180, 260, 460])
        ly.addWidget(split, 1)
        return w

    # ══════════════════════════════════════
    #  PAGE: 设置
    # ══════════════════════════════════════

    def _settings_content(self):
        w = QWidget()
        w.setStyleSheet(f"background:{T.BG};")
        outer = QVBoxLayout(w)
        outer.setContentsMargins(T.SP_LG, T.SP_LG, T.SP_LG, T.SP_LG)
        outer.setSpacing(T.SP_LG)

        # Scrollable container
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setStyleSheet(f"background:transparent;")
        ly = QVBoxLayout(inner)
        ly.setContentsMargins(0, 0, T.SP_SM, 0)
        ly.setSpacing(T.SP_LG)
        scroll.setWidget(inner)

        # ── Card: 选项 ──
        self._set_card_options = QWidget()
        self._set_card_options.setStyleSheet(f"background:{T.CARD};border:none;border-radius:{T.R_LG}px;")
        opt_ly = QVBoxLayout(self._set_card_options)
        opt_ly.setContentsMargins(T.SP_XL, T.SP_LG, T.SP_XL, T.SP_LG)
        opt_ly.setSpacing(T.SP_MD)
        opt_ly.addWidget(section_header("选项"))
        self.popup_cb = QCheckBox("自动处理弹窗")
        self.popup_cb.setChecked(True)
        opt_ly.addWidget(self.popup_cb)
        ly.addWidget(self._set_card_options)

        # ── Card: 定时 ──
        self._set_card_sched = QWidget()
        self._set_card_sched.setStyleSheet(f"background:{T.CARD};border:none;border-radius:{T.R_LG}px;")
        sch_ly = QVBoxLayout(self._set_card_sched)
        sch_ly.setContentsMargins(T.SP_XL, T.SP_LG, T.SP_XL, T.SP_LG)
        sch_ly.setSpacing(T.SP_MD)
        sch_ly.addWidget(section_header("定时"))
        sch_row = QHBoxLayout()
        sch_row.setSpacing(T.SP_SM)
        self.sched_cb = QCheckBox("启用")
        self.sched_cb.toggled.connect(self._on_sched_toggle)
        sch_row.addWidget(self.sched_cb)
        self.sched_combo = QComboBox()
        self.sched_combo.addItems(["每天", "每小时"])
        self.sched_combo.setStyleSheet(f"""
            QComboBox {{
                background: {T.CARD}; color: {T.TEXT};
                border: 1px solid {T.LINE}; border-radius: {T.R_SM}px;
                padding: 3px 10px; min-height: 26px; max-height: 26px;
                font-weight: 600; font-size: 11px;
            }}
            QComboBox::drop-down {{ border: none; width: 20px; }}
        """)
        sch_row.addWidget(self.sched_combo)
        self.sched_time = QDateTimeEdit()
        self.sched_time.setDisplayFormat("HH:mm")
        self.sched_time.setTime(self.sched_time.time().fromString("09:00", "HH:mm"))
        self.sched_time.setStyleSheet(f"""
            QDateTimeEdit {{
                background: {T.CARD}; color: {T.TEXT};
                border: 1px solid {T.LINE}; border-radius: {T.R_SM}px;
                padding: 3px 10px; min-height: 26px; max-height: 26px;
                font-weight: 600; font-size: 11px;
            }}
        """)
        sch_row.addWidget(self.sched_time)
        sch_row.addStretch()
        sch_ly.addLayout(sch_row)
        self.sched_next = QLabel("")
        self.sched_next.setStyleSheet(f"font-size:11px; color:{T.TEXT3};")
        sch_ly.addWidget(self.sched_next)
        ly.addWidget(self._set_card_sched)

        # ── Card: 录制快捷键 ──
        self._set_card_hk = QWidget()
        self._set_card_hk.setStyleSheet(f"background:{T.CARD};border:none;border-radius:{T.R_LG}px;")
        hk_ly = QVBoxLayout(self._set_card_hk)
        hk_ly.setContentsMargins(T.SP_XL, T.SP_LG, T.SP_XL, T.SP_LG)
        hk_ly.setSpacing(T.SP_MD)
        hk_ly.addWidget(section_header("录制快捷键"))
        hk_row = QHBoxLayout()
        hk_row.setSpacing(T.SP_SM)
        default_hk = self._settings.value("record/hotkey", "Key.f6")
        self.hk_label = QLabel(f"停止快捷键: {default_hk.replace('Key.','').upper()}")
        self.hk_label.setStyleSheet(f"font-size:13px; color:{T.TEXT2};")
        hk_row.addWidget(self.hk_label)
        hk_btn = btn_ghost("重新设置")
        hk_btn.setCursor(Qt.PointingHandCursor)
        hk_btn.clicked.connect(self._config_hotkey)
        hk_row.addWidget(hk_btn)
        hk_row.addStretch()
        hk_ly.addLayout(hk_row)
        ly.addWidget(self._set_card_hk)

        # ── Card: 全局快捷键 ──
        self._set_card_ghk = QWidget()
        self._set_card_ghk.setStyleSheet(f"background:{T.CARD};border:none;border-radius:{T.R_LG}px;")
        ghk_ly = QVBoxLayout(self._set_card_ghk)
        ghk_ly.setContentsMargins(T.SP_XL, T.SP_LG, T.SP_XL, T.SP_LG)
        ghk_ly.setSpacing(T.SP_MD)
        ghk_ly.addWidget(section_header("全局快捷键"))
        ghk_row = QHBoxLayout()
        ghk_row.setSpacing(T.SP_SM)
        default_ghk = self._settings.value("global_hotkey", "<ctrl>+<shift>+r")
        self.ghk_label = QLabel(f"运行任务: {default_ghk.replace('<','').replace('>','').upper()}")
        self.ghk_label.setStyleSheet(f"font-size:13px; color:{T.TEXT2};")
        ghk_row.addWidget(self.ghk_label)
        ghk_btn = btn_ghost("设置")
        ghk_btn.setCursor(Qt.PointingHandCursor)
        ghk_btn.clicked.connect(self._config_global_hotkey)
        ghk_row.addWidget(ghk_btn)
        ghk_row.addStretch()
        ghk_ly.addLayout(ghk_row)
        ly.addWidget(self._set_card_ghk)

        # ── Card: 版本 ──
        self._set_card_version = QWidget()
        self._set_card_version.setStyleSheet(f"background:{T.CARD};border:none;border-radius:{T.R_LG}px;")
        ver_ly = QVBoxLayout(self._set_card_version)
        ver_ly.setContentsMargins(T.SP_XL, T.SP_LG, T.SP_XL, T.SP_LG)
        ver_ly.setSpacing(T.SP_MD)
        ver_ly.addWidget(section_header(f"版本 {__version__}"))
        ver_row = QHBoxLayout()
        ver_row.setSpacing(T.SP_SM)
        update_btn = btn_ghost("检查更新")
        update_btn.setCursor(Qt.PointingHandCursor)
        update_btn.clicked.connect(lambda: self._check_version(force_notify=True))
        ver_row.addWidget(update_btn)
        self._update_status = QLabel("")
        self._update_status.setStyleSheet(f"font-size:12px; color:{T.TEXT3};")
        ver_row.addWidget(self._update_status)
        ver_row.addStretch()
        ver_ly.addLayout(ver_row)
        ly.addWidget(self._set_card_version)

        ly.addStretch(1)
        outer.addWidget(scroll, 1)
        return w

    def _refresh_settings_styles(self):
        """Refresh the settings page inline styles."""
        self._settings_page.setStyleSheet(f"background:{T.BG};")
        for card in [self._set_card_options, self._set_card_sched, self._set_card_hk, self._set_card_ghk, self._set_card_version]:
            card.setStyleSheet(f"background:{T.CARD};border:none;border-radius:{T.R_LG}px;")
        if hasattr(self, 'hk_label'):
            self.hk_label.setStyleSheet(f"font-size:13px; color:{T.TEXT2};")
        if hasattr(self, 'sched_next'):
            self.sched_next.setStyleSheet(f"font-size:11px; color:{T.TEXT3};")

    # ══════════════════════════════════════
    #  PAGE: 关于
    # ══════════════════════════════════════

    def _about_content(self):
        w = QWidget()
        w.setStyleSheet(f"background:{T.BG};")
        ly = QVBoxLayout(w)
        ly.setContentsMargins(T.SP_3XL, T.SP_2XL, T.SP_3XL, T.SP_2XL)
        ly.setSpacing(T.SP_LG)

        # Brand card
        self._about_card = QWidget()
        self._about_card.setStyleSheet(f"""
            background: {T.CARD};
            border: none;
            border-radius: {T.R_XL}px;
        """)
        br_ly = QVBoxLayout(self._about_card)
        br_ly.setContentsMargins(T.SP_2XL, T.SP_3XL, T.SP_2XL, T.SP_3XL)
        br_ly.setSpacing(T.SP_LG)
        br_ly.setAlignment(Qt.AlignCenter)

        # Logo icon area
        self._about_icon = QLabel("\u2699")
        self._about_icon.setStyleSheet(f"""
            font-size: 48px;  /* ← 自定义关于页品牌大字 */
            color: {T.ACCENT};
            background: transparent;
        """)
        self._about_icon.setAlignment(Qt.AlignCenter)
        br_ly.addWidget(self._about_icon)

        self._about_title = QLabel("SmartRPA")
        self._about_title.setAlignment(Qt.AlignCenter)
        self._about_title.setStyleSheet(f"""
            font-size: 28px;  /* ← 自定义关于页版本号 */
            font-weight: 800;
            color: {T.TEXT};
            letter-spacing: -1px;
        """)
        br_ly.addWidget(self._about_title)

        self._about_desc = QLabel("视觉驱动的智能桌面自动化程序")
        self._about_desc.setAlignment(Qt.AlignCenter)
        self._about_desc.setStyleSheet(f"color:{T.TEXT2}; font-size:15px;")
        br_ly.addWidget(self._about_desc)

        self._about_ver = QLabel(f"v{__version__}")
        self._about_ver.setAlignment(Qt.AlignCenter)
        self._about_ver.setStyleSheet(f"""
            color: {T.ACCENT};
            font-size: 13px;
            font-weight: 600;
            padding: 4px 16px;
            background: {T.ACCENT_DIM};
            border-radius: {T.R_SM}px;
        """)
        br_ly.addWidget(self._about_ver)

        br_ly.addSpacing(T.SP_XL)

        self._about_tech = QLabel("Python  \u00B7  OpenCV  \u00B7  PySide6  \u00B7  Tesseract OCR")
        self._about_tech.setAlignment(Qt.AlignCenter)
        self._about_tech.setStyleSheet(f"color:{T.TEXT3}; font-size:12px; letter-spacing:0.5px;")
        br_ly.addWidget(self._about_tech)

        ly.addWidget(self._about_card)
        ly.addStretch()
        return w

    # ══════════════════════════════════════
    #  Editor Logic (unchanged)
    # ══════════════════════════════════════

    def _ed_add(self, action):
        try:
            name = self.ed_name.currentText().strip()
            if not name:
                name = datetime.datetime.now().strftime("%m月%d日 %H:%M")
                self.ed_name.setEditText(name)
                self.log_msg(f"自动创建任务: {name}", "INFO")
            if action == "press":
                k, ok = QInputDialog.getText(self, "按键", "按键名:")
                if ok and k.strip():
                    self._ed.append((k.strip(), 0, 0, 0, 0, "press"))
                    self._ed_refresh()
                return
            if action == "wait_until":
                self.showMinimized()
                d = RegionSelector()
                if d.exec() and d.region:
                    x, y, w, h = d.region
                    self._snap(name, f"wait_{len(self._ed)+1}", x, y, w, h)
                    t, ok = QInputDialog.getInt(self, "超时", "最大秒:", 60, 1, 600, 1)
                    if ok:
                        self._ed.append((f"wait_{len(self._ed)+1}", x, y, w, h, "wait_until"))
                        self._ed_refresh()
                self.showNormal()
                return
            # click
            self.showMinimized()
            d = RegionSelector()
            if d.exec() and d.region:
                x, y, w, h = d.region
                tpl = f"s{len(self._ed)+1}"
                self._snap(name, tpl, x, y, w, h)
                self._ed.append((tpl, x, y, w, h, "click"))
                self._ed_refresh()
            self.showNormal()
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "操作失败", f"{type(e).__name__}: {e}")

    def _snap(self, task, tpl, x, y, w, h):
        import mss as _m, cv2 as _c
        # Create a unique task dir on first snap, reuse for this editing session
        if not hasattr(self, '_ed_task_dir') or not self._ed_task_dir:
            now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:21]
            self._ed_task_dir = data_dir(f"tasks/{now}")
        d = os.path.join(self._ed_task_dir, "templates")
        os.makedirs(d, exist_ok=True)
        with _m.mss() as sct:
            img = sct.grab({"left": x, "top": y, "width": w, "height": h})
            _c.imwrite(
                os.path.join(d, f"{tpl}.png"),
                _c.cvtColor(np.array(img), _c.COLOR_BGRA2BGR)
            )

    def _ed_refresh(self):
        self.ed_list.blockSignals(True)
        self.ed_list.clear()
        cm = {"click": "点", "press": "按键", "wait_until": "等到"}
        for i, s in enumerate(self._ed):
            n, _, _, _, _, a = s
            c = cm.get(a, a)
            if a == "press":
                text = f"  [{i+1}] 按 {n}"
            else:
                text = f"  [{i+1}] {c} {n}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, i)
            self.ed_list.addItem(item)
        self.ed_list.blockSignals(False)

    def _on_ed_step_selected(self, row):
        """Show template thumbnail when a step is selected."""
        if row < 0 or row >= len(self._ed):
            self._ed_preview.setText("选择步骤查看预览")
            return
        name = self.ed_name.currentText().strip()
        if not name:
            return
        tpl = self._ed[row][0]
        tpl_path = os.path.join(
            os.path.dirname(__file__), "examples", name, "templates", f"{tpl}.png"
        )
        if os.path.exists(tpl_path):
            pixmap = QPixmap(tpl_path)
            scaled = pixmap.scaled(240, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._ed_preview.setPixmap(scaled)
            self._ed_preview.setToolTip(f"{tpl}.png ({pixmap.width()}x{pixmap.height()})")
        else:
            self._ed_preview.setText(" 无预览")
            self._ed_preview.setPixmap(QPixmap())

    def _ed_del(self):
        if not self._ed:
            return
        row = self.ed_list.currentRow()
        if row < 0:
            row = len(self._ed) - 1
        self._ed.pop(row)
        self._ed_refresh()

    def _ed_clr(self):
        self._ed.clear()
        self._ed_refresh()

    def _ed_save(self):
        name = self.ed_name.currentText().strip()
        if not name:
            self.log_msg("请输入任务名称", "WARN")
            return
        if not self._ed:
            self.log_msg("请至少添加一个步骤", "WARN")
            return
        # Reorder self._ed to match list widget (drag-drop order)
        ordered = []
        for i in range(self.ed_list.count()):
            item = self.ed_list.item(i)
            idx = item.data(Qt.UserRole)
            if idx is not None and idx < len(self._ed):
                ordered.append(self._ed[idx])
        if ordered:
            self._ed[:] = ordered

        # Use existing editing dir if available, otherwise create new
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:21]
        if hasattr(self, '_ed_task_dir') and self._ed_task_dir and os.path.isdir(self._ed_task_dir):
            d = self._ed_task_dir
        else:
            d = data_dir(f"tasks/{now}")
        os.makedirs(d, exist_ok=True)

        # Store meta info (display name, timestamps)
        tasks, loop = {}, self.run_loop.value()
        tasks["_meta"] = {
            "name": name,
            "created": now,
            "modified": datetime.datetime.now().isoformat()
        }
        for i, s in enumerate(self._ed):
            try:
                tpl, x, y, w, h, a = s
                sid = f"Step{i+1}"
                e = {"desc": f"步骤{i+1}"}
                if a == "press":
                    e["action"] = "press"
                    e["params"] = {"key": tpl}
                elif a == "wait_until":
                    e["action"] = "wait_until"
                    e["params"] = {"template": tpl, "threshold": 0.8, "timeout": 60}
                elif a == "click":
                    e["action"] = "click"
                    e["params"] = {"template": tpl, "threshold": 0.8}
                if i < len(self._ed) - 1:
                    e["next"] = [f"Step{i+2}"]
                elif loop > 1:
                    e["next"] = ["Step1"]
                tasks[sid] = e
            except Exception as ex:
                self.log_msg(f"步骤{i+1}保存失败: {ex}", "WARN")
        if loop > 1 and "Step1" in tasks:
            tasks["Step1"]["maxTimes"] = loop
        with open(os.path.join(d, "task.json"), "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
        self.log_msg(f"已保存: {d}/task.json", "SUCCESS")
        self._ed_task_dir = None  # reset for next editing session
        self._scan()

    def _ed_task_selected(self, idx):
        """左列任务列表选中时自动加载到编辑器"""
        if idx < 0:
            return
        item = self.ed_task_list.item(idx)
        if not item:
            return
        task_name = item.text()
        path = self._task_map.get(task_name)
        if not path:
            return
        self._ed_load_path(path)

    def _ed_load_path(self, path):
        """从指定路径加载任务到编辑器"""
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            self.log_msg(f"读取任务失败: {e}", "ERROR")
            return
        self._ed_clr()
        meta = data.get("_meta", {})
        display_name = meta.get("name", os.path.basename(os.path.dirname(path)))
        idx = self.ed_name.findText(display_name)
        if idx >= 0:
            self.ed_name.setCurrentIndex(idx)
        self._ed_task_dir = os.path.dirname(path)

        # Behavior Tree format: skip flat extraction, hint user
        if "root" in data:
            self.log_msg("这是 BT 格式任务，请到「流程编辑」页面查看", "INFO")
            if hasattr(self, 'flow_editor'):
                self.flow_editor.load_bt_tree(data["root"])
            return

        # Classic flat format
        steps = {}
        for k, v in data.items():
            if k.startswith("_") or not isinstance(v, dict) or "action" not in v:
                continue
            steps[k] = v
        if not steps:
            self.log_msg("任务中没有有效步骤", "WARN")
            return
        referenced = set()
        for k, v in steps.items():
            for n in (v.get("next") or []):
                referenced.add(n)
            for n in (v.get("onErrorNext") or []):
                referenced.add(n)
        entry = None
        for k in steps:
            if k not in referenced:
                entry = k
                break
        if entry is None:
            entry = list(steps.keys())[0]
        ordered = []
        visited = set()
        current_key = entry
        while current_key and current_key in steps and current_key not in visited:
            visited.add(current_key)
            node = steps[current_key]
            action = node.get("action", "click")
            params = node.get("params", {})
            tpl = params.get("template", params.get("key", params.get("seconds", "")))
            if action == "click":
                self._ed.append((tpl, 0, 0, 0, 0, "click"))
            elif action == "press":
                self._ed.append((params.get("key", ""), 0, 0, 0, 0, "press"))
            elif action == "wait_until":
                self._ed.append((tpl, 0, 0, 0, 0, "wait_until"))
            else:
                self._ed.append((tpl or action, 0, 0, 0, 0, action))
            ordered.append(node.get("desc", current_key))
            next_nodes = node.get("next") or []
            current_key = next_nodes[0] if next_nodes and next_nodes[0] in steps else None
        for desc in ordered:
            self.ed_list.addItem(desc)
        self.log_msg(f"已加载 {len(self._ed)} 个步骤", "SUCCESS")

        # Update flow editor if visible on the flow page
        if hasattr(self, 'flow_editor') and "root" in data:
            self.flow_editor.load_bt_tree(data["root"])
        elif hasattr(self, 'flow_editor') and steps:
            self.flow_editor.load_flat_tasks(steps, entry)

    def _ed_rename(self):
        """Rename a user task by updating _meta.name in its task.json."""
        current = self.task_combo.currentText()
        path = self._task_map.get(current)
        if not path:
            self.log_msg("请先选择一个任务", "WARN")
            return
        # Only allow renaming user tasks (not built-in)
        if path.startswith(resource_path("examples")):
            self.log_msg("内置任务不能改名", "WARN")
            return
        new_name, ok = QInputDialog.getText(
            self, "改名", "新名称:", text=current
        )
        if not ok or not new_name.strip():
            return
        new_name = new_name.strip()
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if "_meta" not in data or not isinstance(data["_meta"], dict):
                data["_meta"] = {}
            data["_meta"]["name"] = new_name
            data["_meta"]["modified"] = datetime.datetime.now().isoformat()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.log_msg(f"已改名: {new_name}", "SUCCESS")
            self._scan()
        except (IOError, json.JSONDecodeError) as e:
            self.log_msg(f"改名失败: {e}", "ERROR")

    def _ed_delete_task(self):
        """Delete a user task folder."""
        current = self.task_combo.currentText()
        path = self._task_map.get(current)
        if not path:
            self.log_msg("请先选择一个任务", "WARN")
            return
        if path.startswith(resource_path("examples")):
            self.log_msg("内置任务不能删除", "WARN")
            return
        task_dir = os.path.dirname(path)
        reply = QMessageBox.warning(
            self, "确认删除",
            f"确定要删除用户任务「{current}」吗？\n{task_dir}\n\n此操作不可恢复！",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        import shutil
        try:
            shutil.rmtree(task_dir)
            self.log_msg(f"已删除: {current}", "SUCCESS")
            self._scan()
        except OSError as e:
            self.log_msg(f"删除失败: {e}", "ERROR")

    # ══════════════════════════════════════
    #  Tasks Logic (unchanged)
    # ══════════════════════════════════════

    def _scan(self):
        """Scan both built-in examples and user data directory for tasks."""
        import shutil
        self._task_map.clear()
        self.task_combo.clear()

        # Scan built-in examples & copy to user data on first run
        ex = resource_path("examples")
        if os.path.isdir(ex):
            for d in sorted(os.listdir(ex)):
                src_fp = os.path.join(ex, d, "task.json")
                if not os.path.exists(src_fp):
                    continue
                # Read display name from _meta.name, fallback to folder name
                display = d
                try:
                    with open(src_fp, encoding="utf-8") as f:
                        data = json.load(f)
                        meta = data.get("_meta", {})
                        if isinstance(meta, dict) and meta.get("name"):
                            display = meta["name"]
                except (json.JSONDecodeError, IOError):
                    pass
                # Ensure a copy exists in user data directory
                user_task_dir = data_dir(f"tasks/{d}")
                user_fp = os.path.join(user_task_dir, "task.json")
                if not os.path.exists(user_fp):
                    # Copy task.json
                    os.makedirs(user_task_dir, exist_ok=True)
                    shutil.copy2(src_fp, user_fp)
                # Always sync templates (user may add new screenshots later)
                src_tpl = os.path.join(ex, d, "templates")
                if os.path.isdir(src_tpl):
                    dst_tpl = os.path.join(user_task_dir, "templates")
                    os.makedirs(dst_tpl, exist_ok=True)
                    for fname in os.listdir(src_tpl):
                        s = os.path.join(src_tpl, fname)
                        d = os.path.join(dst_tpl, fname)
                        if os.path.isfile(s) and (not os.path.exists(d) or
                                                   os.path.getmtime(s) > os.path.getmtime(d)):
                            shutil.copy2(s, d)
                # Register the user data copy as the active path
                self._task_map[display] = user_fp
                self.task_combo.addItem(display)

        # Scan user data directory (timestamp folders, read _meta.name)
        user_dir = data_dir("tasks")
        if os.path.isdir(user_dir):
            for folder in sorted(os.listdir(user_dir)):
                # Skip folders that match built-in example names (already mapped)
                if os.path.isdir(os.path.join(ex, folder)) if os.path.isdir(ex) else False:
                    continue
                fp = os.path.join(user_dir, folder, "task.json")
                if not os.path.exists(fp):
                    continue
                # Read display name from _meta.name, fallback to folder name
                display = folder
                try:
                    with open(fp, encoding="utf-8") as f:
                        data = json.load(f)
                        meta = data.get("_meta", {})
                        if isinstance(meta, dict) and meta.get("name"):
                            display = meta["name"]
                except (json.JSONDecodeError, IOError):
                    pass
                # Deduplicate: append suffix if display name already taken
                key = display
                suffix = 1
                while key in self._task_map:
                    suffix += 1
                    key = f"{display} ({suffix})"
                self._task_map[key] = fp
                self.task_combo.addItem(key)

        # Auto-select first item
        if self.task_combo.count() > 0:
            self.task_combo.setCurrentIndex(0)

        # Scan for Behavior Tree task files (*.bt.json)
        for scan_dir, prefix in [(ex, ""), (data_dir("tasks"), "")] if os.path.isdir(ex) else [(data_dir("tasks"), "")]:
            if not os.path.isdir(scan_dir):
                continue
            for d in sorted(os.listdir(scan_dir)):
                # Check task.bt.json in each task folder or directly
                bt_file = os.path.join(scan_dir, d)
                if os.path.isdir(bt_file):
                    bt_file = os.path.join(bt_file, "task.bt.json")
                elif not d.endswith(".bt.json"):
                    continue
                if not os.path.exists(bt_file):
                    continue
                # Read display name
                try:
                    with open(bt_file, encoding="utf-8") as f:
                        bt_data = json.load(f)
                    bt_meta = bt_data.get("_meta", {})
                    bt_display = bt_meta.get("name", os.path.splitext(
                        os.path.basename(d))[0]) if isinstance(bt_meta, dict) else d
                except (json.JSONDecodeError, IOError):
                    continue
                # Add BT suffix
                bt_key = f"{bt_display} [BT]"
                if bt_key not in self._task_map:
                    self._task_map[bt_key] = bt_file
                    self.task_combo.addItem(bt_key)

        # Refresh tasks page list (MAA-style checklist)
        if hasattr(self, 'task_list'):
            self.task_list.clear()
            for name in self._task_map:
                self._add_task_checklist_item(name)
            if self.task_list.count() > 0:
                self.task_list.setCurrentRow(0)

        # Refresh flow page task selector
        if hasattr(self, 'flow_task_combo'):
            current = self.flow_task_combo.currentText()
            self.flow_task_combo.blockSignals(True)
            self.flow_task_combo.clear()
            self.flow_task_combo.addItem("")  # empty = no selection
            for name in self._task_map:
                self.flow_task_combo.addItem(name)
            idx = self.flow_task_combo.findText(current)
            if idx >= 0:
                self.flow_task_combo.setCurrentIndex(idx)
            self.flow_task_combo.blockSignals(False)

        # Refresh editor task list
        if hasattr(self, 'ed_task_list'):
            self.ed_task_list.clear()
            for name in self._task_map:
                self.ed_task_list.addItem(name)

    def _on_task_changed(self):
        path = self._task_map.get(self.task_combo.currentText())
        if not path:
            return
        tpl = os.path.join(os.path.dirname(path), "templates")
        if os.path.isdir(tpl):
            self.tpl_combo.setCurrentText(tpl)

    def _select_region(self):
        self.showMinimized()
        d = RegionSelector()
        if d.exec() and d.region:
            self._region = d.region
            x, y, w, h = self._region
            self.region_lbl.setText(f"{x},{y}  {w}x{h}")
            self.region_lbl.setStyleSheet(f"""
                color: {T.GREEN};
                font-size: 12px;
                font-weight: 600;
                padding: 5px 14px;
                min-height: 32px;
                max-height: 32px;
                background: {T.GREEN_BG};
                border-radius: {T.R_SM}px;
                border: 1px solid {T.GREEN}22;
            """)
        self.showNormal()

    def _browse_tpl(self):
        d = QFileDialog.getExistingDirectory(self, "选择模板目录")
        if d:
            self.tpl_combo.setCurrentText(d)

    def _start(self):
        """Start running all checked tasks sequentially."""
        checked = self._checked_task_names()
        if not checked:
            self.log_msg("没有勾选任何任务", "WARN")
            return

        self._checked_names = checked
        self._queue_index = 0
        self._loop_count = 0
        self._max_loops = self.run_loop.value()
        self.log_msg(f"准备运行 {len(checked)} 个任务，循环 {self._max_loops} 次", "INFO")
        self._run_next_checked()

    def _run_next_checked(self):
        """Run the next checked task in sequence."""
        if self._queue_index >= len(self._checked_names):
            # All tasks done for this loop iteration
            self._loop_count += 1
            if self._loop_count < self._max_loops:
                self._queue_index = 0
                self.log_msg(f"--- 第 {self._loop_count + 1}/{self._max_loops} 轮 ---", "INFO")
            else:
                self._finish_run()
                return

        if self._queue_index >= len(self._checked_names):
            self._finish_run()
            return

        name = self._checked_names[self._queue_index]
        path = self._task_map.get(name)
        if not path or not os.path.exists(path):
            self.log_msg(f"任务文件不存在: {name}", "ERROR")
            self._queue_index += 1
            self._run_next_checked()
            return

        self._running = True
        self.run_btn.setText("\u25A0  停止")
        self._update_run_btn_style()
        self.progress.show()
        self.state_lbl.setStyleSheet(f"color:{T.ACCENT2};font-size:11px;padding:0 4px;")
        self.state_lbl.setText(f"运行中 [{self._queue_index + 1}/{len(self._checked_names)}]")

        self.log_msg(f"[{self._queue_index + 1}/{len(self._checked_names)}] {name}", "INFO")

        self.worker = TaskWorker(
            path, self.tpl_combo.currentText() or None,
            not self.popup_cb.isChecked(), self._region,
            self.fast_toggle.isChecked()
        )
        self.worker.log.connect(self.log_msg)
        self.worker.finished.connect(self._done)
        self.showMinimized()
        self.worker.start()

    def _finish_run(self):
        """All checked tasks completed across all loops."""
        self.showNormal()
        self._reset()
        self.log_msg("所有任务执行完成", "SUCCESS")

    def _on_step(self, desc):
        self.status_lbl.setText(f" {desc}")

    def _stop(self):
        if self.worker:
            self.worker.stop()
        self.showNormal()
        self._reset()
        self.log_msg("已停止", "WARN")

    def _done(self, stats):
        self.showNormal()
        msg = f"完成: {stats['steps']}步 {stats['popups_handled']}弹窗 {stats['errors']}错误"
        self.log_msg(msg, "SUCCESS" if stats['errors'] == 0 else "WARN")
        self.status_lbl.setText(f" 完成 — {stats['steps']}步骤")
        # 错误通知
        if stats['errors'] > 0:
            self._tray.showMessage(
                "SmartRPA - 任务有错误",
                f"{stats['errors']}个错误，共{stats['steps']}步",
                QSystemTrayIcon.MessageIcon.Warning, 5000
            )
        elif stats['steps'] > 0:
            self._tray.showMessage(
                "SmartRPA - 任务完成",
                f"{stats['steps']}步 全部成功",
                QSystemTrayIcon.MessageIcon.Information, 3000
            )

        # Continue to next checked task
        self._queue_index += 1
        self._run_next_checked()

    def _reset(self):
        self._running = False
        self.run_btn.setText("\u25B6  开始运行")
        self._update_run_btn_style()
        self.progress.hide()
        self.state_lbl.setStyleSheet(f"color:{T.TEXT3};font-size:11px;padding:0 4px;")
        self.state_lbl.setText("就绪")
        self.state_lbl.setStyleSheet(f"color:{T.TEXT3};font-size:11px;padding:0 4px;")

    def _copy_log(self):
        """Copy log content to clipboard."""
        html = self.log.toHtml()
        import re
        text = re.sub(r'<[^>]+>', '', html)
        text = re.sub(r'\n\s*\n', '\n', text).strip()
        QApplication.clipboard().setText(text)
        self.log_msg("日志已复制到剪贴板", "SUCCESS")


    def _clear_log(self):
        """Clear all log content."""
        self.log.clear()
        self.log_msg("日志已清空", "INFO")

    def log_msg(self, msg, level="INFO"):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        colors = {
            "INFO":    T.BLUE,
            "SUCCESS": T.GREEN,
            "WARN":    T.ORANGE,
            "ERROR":   T.RED,
        }
        c = colors.get(level, T.TEXT)
        self.log.append(
            f'<span style="color:{T.TEXT3}">{ts}</span> '
            f'<span style="color:{c}; font-weight:600;">[{level}]</span> '
            f'<span style="color:{T.LOG_TEXT}">{msg}</span>'
        )


    # ── Recording ──

    def _toggle_record(self):
        if hasattr(self, '_recorder') and self._recorder and self._recorder.isRunning():
            self._recorder.stop()
            self.rec_btn.setText("⏺  录制")
            self.rec_btn.setStyleSheet(f"""QPushButton{{background:{T.RED_BG};color:{T.RED};border:1px solid {T.RED}33;border-radius:{T.R_SM}px;padding:5px 14px;font-weight:600;font-size:12px;}}QPushButton:hover{{border:1px solid {T.RED}66;}}""")
            self.showNormal()
            self.log_msg("录制已停止", "WARN")
            return
        # Load hotkey from settings
        stop_key = self._settings.value("record/hotkey", "Key.f6")
        self._recorder = ActionRecorder(self, stop_key)
        self._recorder.log.connect(self.log_msg)
        self._recorder.finished.connect(self._on_record_finished)
        self._recorder.start()
        self.showMinimized()
        self.rec_btn.setText("⏹  停止")
        self.rec_btn.setStyleSheet(f"""QPushButton{{background:{T.RED};color:white;border:1px solid {T.RED}88;border-radius:{T.R_SM}px;padding:5px 14px;font-weight:600;font-size:12px;}}QPushButton:hover{{background:#e06060;}}""")
        self.log_msg(f"开始录制 — 按 {stop_key.replace('Key.','')} 停止", "INFO")

    def _config_hotkey(self):
        """Let user configure the recording stop hotkey by pressing a key."""
        self.log_msg("请按下一个按键作为停止录制快捷键（5秒内）...", "INFO")
        import threading
        from pynput import keyboard
        result = [None]

        def on_key(key):
            result[0] = str(key)
            return False  # stop listener

        listener = keyboard.Listener(on_press=on_key)
        listener.start()
        listener.join(timeout=5.0)
        listener.stop()

        if result[0]:
            key_str = result[0]
            self._settings.setValue("record/hotkey", key_str)
            self.hk_label.setText(f"停止: {key_str.replace('Key.','')}")
            self.log_msg(f"停止快捷键已设为: {key_str.replace('Key.','')}", "SUCCESS")
        else:
            self.log_msg("未检测到按键，设置取消", "WARN")

    # ── Global Hotkey ──

    def _start_global_hotkey(self):
        """Start background global hotkey listener."""
        import threading
        from pynput import keyboard as kb

        def on_activate():
            from PySide6.QtCore import QMetaObject, Qt
            QMetaObject.invokeMethod(self, "_on_global_hotkey", Qt.ConnectionType.QueuedConnection)

        hotkey_str = self._settings.value("global_hotkey", "<ctrl>+<shift>+r")
        # Auto-fix bare F-keys from older settings (F10 -> <f10>)
        import re
        hotkey_str = re.sub(r'\b([Ff]\d+)\b', r'<\1>', hotkey_str)
        try:
            self._ghk_listener = kb.GlobalHotKeys({hotkey_str: on_activate})
            self._ghk_listener.daemon = True
            self._ghk_listener.start()
        except Exception as e:
            self.log_msg(f"全局快捷键启动失败: {e}", "WARN")

    def _stop_global_hotkey(self):
        if hasattr(self, '_ghk_listener') and self._ghk_listener:
            self._ghk_listener.stop()
            self._ghk_listener = None

    @Slot()
    def _on_global_hotkey(self):
        """Global hotkey pressed: show window, stop or start task."""
        if self.isHidden() or self.isMinimized():
            self.showNormal()
            self.activateWindow()
        elif self._running:
            self.log_msg("全局快捷键: 停止", "INFO")
            self._stop()
        else:
            self.log_msg("全局快捷键: 开始运行", "INFO")
            self._start()

    def _config_global_hotkey(self):
        """Let user configure global hotkey by pressing a key combo."""
        self.log_msg("请按下新的全局快捷键（如 Ctrl+Shift+R），5秒内...", "INFO")
        import threading
        from pynput import keyboard

        result = [None]
        def on_release(key):
            result[0] = str(key)
            return False

        listener = keyboard.Listener(on_release=on_release)
        listener.start()
        listener.join(timeout=5.0)
        listener.stop()

        if result[0]:
            key_str = result[0]
            # Map pynput key names to keyboard module format
            key_map = {
                "Key.ctrl_l": "<ctrl>", "Key.ctrl_r": "<ctrl>",
                "Key.shift_l": "<shift>", "Key.shift_r": "<shift>",
                "Key.alt_l": "<alt>", "Key.alt_r": "<alt>",
                "Key.cmd": "<cmd>",
            }
            parts = key_str.split("+")
            mapped = []
            for p in parts:
                p = p.strip()
                if p in key_map:
                    mapped.append(key_map[p])
                elif p.startswith("Key."):
                    kn = p.replace("Key.", "")  # f10, up, space etc
                    mapped.append(f"<{kn.lower()}>")  # pynput needs <f10> format
                else:
                    mapped.append(p.lower())  # single letter keys
            hotkey_str = "+".join(mapped)
            self._settings.setValue("global_hotkey", hotkey_str)
            self.ghk_label.setText(f"运行任务: {hotkey_str.replace('<','').replace('>','').upper()}")
            # Restart listener with new hotkey
            self._stop_global_hotkey()
            self._start_global_hotkey()
            self.log_msg(f"全局快捷键已设为: {hotkey_str}", "SUCCESS")
        else:
            self.log_msg("未检测到按键，设置取消", "WARN")

    def _on_record_finished(self, task_path):
        self.rec_btn.setText("⏺  录制")
        self.rec_btn.setStyleSheet(f"""QPushButton{{background:{T.RED_BG};color:{T.RED};border:1px solid {T.RED}33;border-radius:{T.R_SM}px;padding:5px 14px;font-weight:600;font-size:12px;}}QPushButton:hover{{border:1px solid {T.RED}66;}}""")
        self.showNormal()
        self.log_msg(f"录制完成，打开任务编辑器查看", "SUCCESS")
        self._scan()
        # Switch to editor page
        self._switch_page(1)

    # ── Export / Import ──

    def _export_task(self):
        """Export selected task as a zip file."""
        current = self.task_combo.currentText()
        path = self._task_map.get(current)
        if not path:
            self.log_msg("请先选择一个任务", "WARN")
            return
        import zipfile
        task_dir = os.path.dirname(path)
        default_name = f"{current.replace(' ', '_')}.zip"
        save_path, _ = QFileDialog.getSaveFileName(
            self, "导出任务", default_name, "ZIP 文件 (*.zip)"
        )
        if not save_path:
            return
        try:
            with zipfile.ZipFile(save_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(task_dir):
                    for fn in files:
                        fp = os.path.join(root, fn)
                        arcname = os.path.relpath(fp, task_dir)
                        zf.write(fp, arcname)
            self.log_msg(f"已导出: {save_path}", "SUCCESS")
        except Exception as e:
            self.log_msg(f"导出失败: {e}", "ERROR")

    def _import_task(self):
        """Import a task from a zip file."""
        zip_path, _ = QFileDialog.getOpenFileName(
            self, "导入任务", "", "ZIP 文件 (*.zip)"
        )
        if not zip_path:
            return
        import zipfile, tempfile, shutil
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                # Generate unique folder name
                now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:21]
                target = data_dir(f"tasks/{now}")
                zf.extractall(target)
            self.log_msg(f"已导入: {zip_path}", "SUCCESS")
            self._scan()
        except Exception as e:
            self.log_msg(f"导入失败: {e}", "ERROR")

    # ── Step editing enhancements ──

    def _ed_edit_step(self):
        """Edit the currently selected step's parameters."""
        row = self.ed_list.currentRow()
        if row < 0 or row >= len(self._ed):
            self.log_msg("请先选中一个步骤", "WARN")
            return
        s = list(self._ed[row])
        a = s[5]
        if a == "click":
            new_tpl, ok = QInputDialog.getText(self, "修改模板", "模板名:", text=s[0])
            if ok and new_tpl.strip():
                s[0] = new_tpl.strip()
                self._ed[row] = tuple(s)
                self._ed_refresh()
        elif a == "press":
            new_k, ok = QInputDialog.getText(self, "修改按键", "按键名:", text=s[0])
            if ok and new_k.strip():
                s[0] = new_k.strip()
                self._ed[row] = tuple(s)
                self._ed_refresh()
        elif a == "wait_until":
            new_tpl, ok = QInputDialog.getText(self, "修改模板", "模板名:", text=s[0])
            if ok and new_tpl.strip():
                s[0] = new_tpl.strip()
                self._ed[row] = tuple(s)
                self._ed_refresh()

    def _ed_copy_step(self):
        """Copy the selected step."""
        row = self.ed_list.currentRow()
        if row < 0 or row >= len(self._ed):
            self.log_msg("请先选中一个步骤", "WARN")
            return
        self._ed.insert(row + 1, self._ed[row])
        self._ed_refresh()

# ═══════════════════════════════════════════════
#  Entry Point
# ═══════════════════════════════════════════════

def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei", 10))  # ← 自定义全局后备字体（影响所有控件默认字号）
    app.setStyle("Fusion")
    app.setStyleSheet(build_base_qss())
    SmartRPAGUI().show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
