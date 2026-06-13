"""SmartRPA GUI — 视觉驱动的智能桌面自动化程序 (2026 Design)"""
#
# ═══════════════════════════════════════════════════════════════
#  字体/字号 快速定位指南
# ═══════════════════════════════════════════════════════════════
#  搜索关键词        | 位置                      | 修改什么
#  ─────────────────┼──────────────────────────┼──────────────────
#  自定义字体族       | build_base_qss()          | 全局字体 (line ~118)
#  btn_primary       | btn_primary()              | 主按钮 13px/600w
#  btn_danger        | btn_danger()               | 危险按钮 13px/600w
#  btn_ghost         | btn_ghost()                | 幽灵按钮 12px/500w
#  标签/标题          | status_pill / section_header | 状态标签/分区标题
#  page_title函数    | page_title()               | 页面内大标题 24px/700w
#  section_title     | section_title()             | 配置字段标签
#  section_desc      | section_desc()              | 描述文字
#  NavButton         | NavButton._update_style()   | 顶部Tab导航 13px
#  logo字体           | _build() 顶部导航           | Logo 15px/800w
#  状态文字           | state_lbl                  | ●就绪 / ●运行中
#  版本号             | _build() 顶部导航            | v0.1.0 11px
#  运行/停止按钮      | _update_run_btn_style()     | 全宽切换按钮 14px
#  步骤项             | _steps 字典 setStyleSheet   | 步骤列表 13px
#  日志区字体         | self.log.setFont()          | 等宽日志字体 10px
#  编辑器代码字体     | self.ed_list.setFont()      | 步骤编辑列表 10px
#  关于页大标题       | _about_content()            | 品牌名 48px
#  关于页副标题       | _about_content()            | 描述 15px
#  全局 QFont         | 文件末尾 app.setFont()      | 全局后备字体 10px
# ═══════════════════════════════════════════════════════════════
#
import sys, os, json, datetime
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
    Created automatically if it doesn't exist."""
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
from PySide6.QtCore import Qt, QThread, Signal, QRect, QTimer, QSettings
from PySide6.QtGui import QFont, QPainter, QPen, QColor, QLinearGradient, QIcon, QPixmap

from smartrpa import Controller, Vision, TaskEngine, PopupHandler, __version__
from callback_2048 import callback_2048


# ═══════════════════════════════════════════════
#  2026 Design System — Theme Tokens
# ═══════════════════════════════════════════════

class Theme:
    """Dual-theme design tokens — call Theme.apply('light'|'dark') to switch."""

    # Shared (invariant across themes)
    SP_XS   = 4
    SP_SM   = 8
    SP_MD   = 12
    SP_LG   = 16
    SP_XL   = 24
    SP_2XL  = 32
    SP_3XL  = 48
    R_SM    = 8
    R_MD    = 12
    R_LG    = 16
    R_XL    = 20
    ACCENT     = "#7c6ff7"
    ACCENT2    = "#a78bfa"
    GREEN      = "#34d399"
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
    def GREEN_BG(self):    return "#ecfdf5" if self.mode == "light" else "#0d2d22"
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
    """Primary action button — gradient accent style"""  # ← 自定义主按钮字体 (13px/600w)
    b = QPushButton(text)
    b.setStyleSheet(f"""
        QPushButton {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {T.ACCENT}, stop:1 #60a5fa);
            color: white;
            border: none;
            border-radius: {T.R_SM}px;
            font-weight: 600;
            padding: 7px 20px;
            font-size: 13px;
        }}
        QPushButton:hover {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {T.ACCENT2}, stop:1 #93c5fd);
        }}
        QPushButton:pressed {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #6c5ce7, stop:1 #4b8bdb);
        }}
        QPushButton:disabled {{
            background: {T.LINE};
            color: {T.TEXT3};
        }}
    """)
    return b


def btn_danger(text):
    """Danger button — same size as primary"""  # ← 自定义停止按钮字体 (13px/600w)
    b = QPushButton(text)
    b.setStyleSheet(f"""
        QPushButton {{
            background: {T.RED_BG};
            color: {T.RED};
            border: 1px solid {T.DANGER_BORDER};
            border-radius: {T.R_SM}px;
            font-weight: 600;
            padding: 7px 20px;
            font-size: 13px;
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
            padding: 5px 14px;
            min-height: 32px;
            max-height: 32px;
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
        color = T.GREEN
    if bg is None:
        bg = T.GREEN_BG
    l = QLabel(text)
    l.setStyleSheet(f"""
        color: {color};
        font-size: 12px;
        font-weight: 600;
        padding: 5px 14px;
        min-height: 32px;
        max-height: 32px;
        background: {bg};
        border-radius: {T.R_SM}px;
        border: 1px solid {color}22;
    """)
    return l


# ═══════════════════════════════════════════════
#  Task Worker (unchanged)
# ═══════════════════════════════════════════════

class TaskWorker(QThread):
    log = Signal(str, str); finished = Signal(dict); step = Signal(str)

    def __init__(self, task_file, tpl_dir=None, no_popup=False, region=None):
        super().__init__()
        self.task_file = task_file
        self.tpl_dir = tpl_dir
        self.no_popup = no_popup
        self.region = region
        self._active = True

    def run(self):
        try:
            v = Vision()
            if self.tpl_dir:
                v.set_template_dir(self.tpl_dir)
            c = Controller()
            p = PopupHandler(v, c)
            p.enabled = not self.no_popup
            p.register_builtin_strategies()
            engine = TaskEngine(c, v, p)
            engine.region = self.region
            engine._user_log = lambda m, l: self.log.emit(m, l)
            if self.region:
                callback_2048._palette = None
                engine.on("play_2048", callback_2048)
            engine.load(self.task_file)
            entry = list(engine._tasks.keys())[0]
            self.log.emit(f"任务: {os.path.basename(self.task_file)}", "INFO")
            orig = engine._execute_step
            cnt = [0]

            def hook(ss, t):
                if not self._active:
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

class NavButton(QPushButton):
    """Navigation button — ChemCal-style tab appearance"""
    def __init__(self, label, parent=None):
        super().__init__(label, parent)
        self._active = False
        self.setCursor(Qt.PointingHandCursor)
        self._update_style()

    def set_active(self, active):
        self._active = active
        self._update_style()

    def _update_style(self):
        if self._active:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {T.CARD};
                    color: {T.TEXT};
                    border: 1px solid {T.LINE};
                    border-bottom: none;
                    border-top-left-radius: 8px;
                    border-top-right-radius: 8px;
                    padding: 0 20px;
                    margin-right: 2px;
                    font-weight: 600;  /* ← 自定义导航标签字号 (选中的 Tab) */
                    font-size: 13px;  /* ← 自定义导航标签字号 */
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {T.SURFACE};
                    color: {T.TEXT2};
                    border: 1px solid {T.LINE};
                    border-bottom: 1px solid {T.LINE};
                    border-top-left-radius: 8px;
                    border-top-right-radius: 8px;
                    padding: 0 20px;
                    margin-right: 2px;
                    font-weight: 500;  /* ← 自定义导航标签字号 (未选中的 Tab) */
                    font-size: 13px;  /* ← 自定义导航标签字号 */
                }}
                QPushButton:hover {{
                    background: {T.CARD_HOVER};
                    color: {T.TEXT};
                }}
            """)


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

    def _build(self):
        cw = QWidget()
        self.setCentralWidget(cw)
        root = QVBoxLayout(cw)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ═══ TOP: Navigation Bar ═══
        top_nav = QWidget()
        top_nav.setFixedHeight(44)
        top_nav.setStyleSheet(f"background: {T.SURFACE};")
        tn_ly = QHBoxLayout(top_nav)
        tn_ly.setContentsMargins(T.SP_LG, 0, T.SP_LG, 0)
        tn_ly.setSpacing(0)

        # Logo
        self._logo_label = QLabel("SmartRPA")
        self._logo_label.setStyleSheet(f"""
            font-size: 15px;  /* ← 自定义 Logo 字号 */
            font-weight: 800;  /* ← 自定义 Logo 字重 */
            color: {T.TEXT};
            letter-spacing: -0.3px;
            padding: 0 12px 0 4px;
        """)
        tn_ly.addWidget(self._logo_label)

        # Nav buttons
        self.nav_btns = []
        nav_items = [
            "自动化任务",
            "任务编辑器",
            "关于",
        ]
        for label in nav_items:
            btn = NavButton(label)
            btn.clicked.connect(lambda checked, idx=len(self.nav_btns): self._switch_page(idx))
            btn.setFixedHeight(44)
            tn_ly.addWidget(btn)
            self.nav_btns.append(btn)
        self.nav_btns[0].set_active(True)

        tn_ly.addStretch(1)

        # Right-side items with spacing
        right_container = QWidget()
        right_container.setStyleSheet("background: transparent;")
        rc_ly = QHBoxLayout(right_container)
        rc_ly.setContentsMargins(0, 0, 0, 0)
        rc_ly.setSpacing(6)

        # Status indicator
        self.pulse_dot = PulseDot()
        rc_ly.addWidget(self.pulse_dot)

        self.state_lbl = QLabel("就绪")
        self.state_lbl.setStyleSheet(f"color:{T.TEXT2}; font-size:12px; font-weight:500; padding: 0 8px 0 4px;")  # ← 自定义状态文字字号（就绪）
        rc_ly.addWidget(self.state_lbl)

        # Theme toggle
        self.theme_switch = ThemeSwitch(T.mode)
        self.theme_switch.toggled.connect(self._on_theme_toggle)
        rc_ly.addWidget(self.theme_switch)

        # Version
        self._ver_label = QLabel(f"v{__version__}")
        self._ver_label.setStyleSheet(f"""
            font-size: 11px;
            color: {T.TEXT3};
            padding: 0 4px 0 8px;
        """)
        rc_ly.addWidget(self._ver_label)

        tn_ly.addWidget(right_container)

        self.top_nav = top_nav
        root.addWidget(top_nav)

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
        self._editor_page = self._editor_content()
        self._about_page = self._about_content()
        self.content_stack.addWidget(self._tasks_page)
        self.content_stack.addWidget(self._editor_page)
        self.content_stack.addWidget(self._about_page)
        right_ly.addWidget(self.content_stack, 1)

        # ── Status Bar ──
        self.status = QStatusBar()
        self.status_lbl = QLabel(" 选择任务后点击「开始运行」")
        self.status_lbl.setStyleSheet(f"color:{T.TEXT3};")
        self.status.addWidget(self.status_lbl, 1)
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
        self.top_nav.setStyleSheet(f"background: {T.SURFACE};")

        self.right_widget.setStyleSheet(f"background: {T.BG};")

        # Logo
        if hasattr(self, '_logo_label'):
            self._logo_label.setStyleSheet(f"""
                font-size: 15px;
                font-weight: 800;
                color: {T.TEXT};
                letter-spacing: -0.3px;
                padding: 0 12px 0 4px;
            """)

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

        # Pulse dot base color
        if not self._running:
            self.pulse_dot.set_color(T.TEXT3)

        # Bottom status bar
        self.status_lbl.setStyleSheet(f"color:{T.TEXT3};")

        # Nav buttons
        for i, btn in enumerate(self.nav_btns):
            btn._update_style()

        # Theme switch
        self.theme_switch._update_style()

        # Refresh content pages
        self._refresh_tasks_styles()
        self._refresh_editor_styles()
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
                        background: {T.GREEN_BG};
                        color: {T.GREEN};
                        border: 1px solid {T.GREEN}22;
                        border-radius: {T.R_SM}px;
                        padding: 5px 14px;
                        min-height: 32px;
                        max-height: 32px;
                        font-weight: 600;
                        font-size: 12px;
                    }}
                    QComboBox::drop-down {{
                        border: none;
                        width: 24px;
                    }}
                    QComboBox::drop-down:on {{
                        background: {T.GREEN_BG};
                    }}
                    QComboBox:hover {{
                        background: {T.GREEN_BG};
                        border: 1px solid {T.GREEN}44;
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
            padding: 5px 14px;
            min-height: 32px;
            max-height: 32px;
            background: {T.GREEN_BG};
            border-radius: {T.R_SM}px;
            border: 1px solid {T.GREEN}22;
        """)

    def _refresh_editor_styles(self):
        """Refresh the editor page inline styles."""
        self._editor_page.setStyleSheet(f"background:{T.BG};")

        # Editor name combo
        if hasattr(self, 'ed_name'):
            self.ed_name.setStyleSheet(f"""QComboBox{{background:{T.GREEN_BG};color:{T.GREEN};border:1px solid {T.GREEN}22;border-radius:{T.R_SM}px;padding:5px 14px;min-height:32px;max-height:32px;font-weight:600;font-size:12px;}}QComboBox::drop-down{{border:none;width:24px;}}QComboBox:hover{{background:{T.GREEN_BG};border:1px solid {T.GREEN}44;}}""")

        # Editor steps list
        if hasattr(self, 'ed_list'):
            self.ed_list.setStyleSheet(f"""QListWidget{{background:{T.SURFACE};color:{T.TEXT};border:1px solid {T.LINE};border-radius:{T.R_MD}px;padding:8px;font-size:12px;outline:none;}}QListWidget::item{{padding:6px 10px;border-radius:4px;}}QListWidget::item:selected{{background:{T.ACCENT_DIM};color:{T.TEXT};}}QListWidget::item:hover{{background:{T.CARD_HOVER};}}""")

        # Editor loop spinbox
        if hasattr(self, 'ed_loop'):
            self.ed_loop.setStyleSheet(f"QSpinBox{{background:{T.GREEN_BG};color:{T.GREEN};border:1px solid {T.GREEN}22;border-radius:{T.R_SM}px;padding:5px 14px;min-height:32px;max-height:32px;font-weight:600;font-size:12px;}}QSpinBox::up-button,QSpinBox::down-button{{border:none;width:20px;background:transparent;}}QSpinBox:hover{{border:1px solid {T.GREEN}44;}}")

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
        if enabled:
            self._update_sched_next()
        else:
            self.sched_next.setText("")

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
            self.log_msg("定时触发: 自动开始运行", "INFO")
            self._start()

    # ══════════════════════════════════════
    #  PAGE: 自动化任务 (3-column Bento)
    # ══════════════════════════════════════

    def _tasks_content(self):
        page = QWidget()
        page.setStyleSheet(f"background:{T.BG};")
        ly = QVBoxLayout(page)
        ly.setContentsMargins(T.SP_LG, T.SP_LG, T.SP_LG, T.SP_LG)
        ly.setSpacing(T.SP_LG)

        split = QSplitter(Qt.Horizontal)
        split.setHandleWidth(1)
        split.setStyleSheet(f"QSplitter::handle{{background:{T.LINE};}}")

        # ── LEFT: Config Panel ──
        self._config_card = QWidget()
        self._config_card.setStyleSheet(f"""
            background: {T.CARD};
            border: none;
            border-radius: {T.R_LG}px;
        """)
        Cl = QVBoxLayout(self._config_card)
        Cl.setContentsMargins(T.SP_XL, T.SP_XL, T.SP_XL, T.SP_XL)
        Cl.setSpacing(T.SP_LG)

        # Task selection
        Cl.addWidget(section_title("任务"))
        tb = QHBoxLayout()
        tb.setSpacing(T.SP_SM)
        self.task_combo = QComboBox()
        self.task_combo.setStyleSheet(f"""
            QComboBox {{
                background: {T.GREEN_BG};
                color: {T.GREEN};
                border: 1px solid {T.GREEN}22;
                border-radius: {T.R_SM}px;
                padding: 5px 14px;
                min-height: 32px;
                max-height: 32px;
                font-weight: 600;
                font-size: 12px;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox::drop-down:on {{
                background: {T.GREEN_BG};
            }}
            QComboBox:hover {{
                background: {T.GREEN_BG};
                border: 1px solid {T.GREEN}44;
            }}
        """)
        self.task_combo.currentIndexChanged.connect(self._on_task_changed)
        tb.addWidget(self.task_combo, 1)
        opt_btn = QPushButton("选项")
        opt_btn.setCursor(Qt.PointingHandCursor)
        opt_btn.setFixedWidth(64)
        opt_btn.setStyleSheet(f"""
            QPushButton {{
                background: {T.GREEN_BG}; color: {T.GREEN};
                border: 1px solid {T.GREEN}22; border-radius: {T.R_SM}px;
                padding: 5px 10px; min-height: 32px; max-height: 32px;
                font-weight: 600; font-size: 11px;
            }}
            QPushButton:hover {{ background: {T.GREEN_BG}; border: 1px solid {T.GREEN}44; }}
            QPushButton::menu-indicator {{ image: none; width: 0; }}
        """)
        opt_menu = QMenu(opt_btn)
        opt_menu.setStyleSheet(f"""
            QMenu {{ background: {T.CARD}; color: {T.TEXT}; border: 1px solid {T.LINE}; border-radius: {T.R_SM}px; padding: 4px; }}
            QMenu::item {{ padding: 6px 20px; border-radius: 4px; }}
            QMenu::item:selected {{ background: {T.ACCENT_DIM}; }}
        """)
        rename_action = opt_menu.addAction("重命名")
        rename_action.triggered.connect(self._ed_rename)
        delete_action = opt_menu.addAction("删除")
        delete_action.triggered.connect(self._ed_delete_task)
        opt_btn.setMenu(opt_menu)
        tb.addWidget(opt_btn)
        Cl.addLayout(tb)

        # Template path
        Cl.addWidget(section_title("模板路径"))
        tpb = QHBoxLayout()
        tpb.setSpacing(T.SP_SM)
        self.tpl_combo = QComboBox()
        self.tpl_combo.setEditable(True)
        self.tpl_combo.setStyleSheet(f"""
            QComboBox {{
                background: {T.GREEN_BG};
                color: {T.GREEN};
                border: 1px solid {T.GREEN}22;
                border-radius: {T.R_SM}px;
                padding: 5px 14px;
                min-height: 32px;
                max-height: 32px;
                font-weight: 600;
                font-size: 12px;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox:hover {{
                background: {T.GREEN_BG};
                border: 1px solid {T.GREEN}44;
            }}
        """)
        tpb.addWidget(self.tpl_combo, 1)
        browse_btn = btn_ghost("浏览")
        browse_btn.setFixedWidth(64)
        browse_btn.clicked.connect(self._browse_tpl)
        tpb.addWidget(browse_btn)
        Cl.addLayout(tpb)

        # Region
        Cl.addWidget(section_title("操作区域"))
        rb = QHBoxLayout()
        rb.setSpacing(T.SP_SM)
        self.region_lbl = status_pill("全屏")
        rb.addWidget(self.region_lbl, 1)
        region_btn = btn_ghost("框选")
        region_btn.setFixedWidth(64)
        region_btn.clicked.connect(self._select_region)
        rb.addWidget(region_btn)
        Cl.addLayout(rb)

        # Options
        Cl.addWidget(section_title("选项"))
        self.popup_cb = QCheckBox("自动处理弹窗")
        self.popup_cb.setChecked(True)
        Cl.addWidget(self.popup_cb)

        # ── Schedule ──
        Cl.addWidget(section_title("定时"))
        sch_row = QHBoxLayout()
        sch_row.setSpacing(T.SP_SM)
        self.sched_cb = QCheckBox("启用")
        self.sched_cb.toggled.connect(self._on_sched_toggle)
        sch_row.addWidget(self.sched_cb)
        self.sched_combo = QComboBox()
        self.sched_combo.addItems(["每天", "每小时"])
        self.sched_combo.setStyleSheet(f"""
            QComboBox {{
                background: {T.GREEN_BG}; color: {T.GREEN};
                border: 1px solid {T.GREEN}22; border-radius: {T.R_SM}px;
                padding: 3px 10px; min-height: 28px; max-height: 28px;
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
                background: {T.GREEN_BG}; color: {T.GREEN};
                border: 1px solid {T.GREEN}22; border-radius: {T.R_SM}px;
                padding: 3px 10px; min-height: 28px; max-height: 28px;
                font-weight: 600; font-size: 11px;
            }}
        """)
        sch_row.addWidget(self.sched_time)
        sch_row.addStretch()
        Cl.addLayout(sch_row)
        self.sched_next = QLabel("")
        self.sched_next.setStyleSheet(f"font-size:11px; color:{T.TEXT3};")
        Cl.addWidget(self.sched_next)

        Cl.addStretch(1)

        # Run / Stop toggle at bottom of config panel
        self.run_btn = QPushButton("\u25B6  开始运行")
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.setMinimumHeight(40)
        self.run_btn.clicked.connect(self._toggle_run)
        Cl.addWidget(self.run_btn)
        self._update_run_btn_style()

        split.addWidget(self._config_card)

        # ── RIGHT: Log Panel ──
        self._log_card = QWidget()
        self._log_card.setStyleSheet(f"""
            background: {T.CARD};
            border: none;
            border-radius: {T.R_LG}px;
        """)
        Rl = QVBoxLayout(self._log_card)
        Rl.setContentsMargins(T.SP_LG, T.SP_XL, T.SP_LG, T.SP_LG)
        Rl.setSpacing(T.SP_MD)

        Rl.addWidget(section_header("日志"))
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
        self.log.setFont(QFont("Cascadia Code,Consolas,monospace", 10))  # ← 自定义日志等宽字体
        self.log.document().setMaximumBlockCount(2000)
        Rl.addWidget(self.log, 1)
        split.addWidget(self._log_card)

        split.setSizes([300, 540])
        ly.addWidget(split, 1)

        return page

    def _update_run_btn_style(self):
        """Update the run/stop button style based on running state."""
        if self._running:
            self.run_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {T.RED_BG};
                    color: {T.RED};
                    border: 1px solid {T.DANGER_BORDER};
                    border-radius: {T.R_LG}px;
                    font-weight: 600;  /* ← 自定义停止状态按钮字号 */
                    font-size: 14px;  /* ← 自定义停止状态按钮字号 */
                    padding: 10px 0;
                }}
                QPushButton:hover {{
                    background: {T.DANGER_HOVER_BG};
                    border-color: {T.RED};
                }}
            """)
        else:
            self.run_btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 {T.ACCENT}, stop:1 #60a5fa);
                    color: white;
                    border: none;
                    border-radius: {T.R_LG}px;
                    font-weight: 600;  /* ← 自定义运行状态按钮字号 */
                    font-size: 14px;  /* ← 自定义运行状态按钮字号 */
                    padding: 10px 0;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 {T.ACCENT2}, stop:1 #93c5fd);
                }}
                QPushButton:disabled {{
                    background: {T.LINE};
                    color: {T.TEXT3};
                }}
            """)

    def _toggle_run(self):
        """Toggle between start and stop."""
        if self._running:
            self._stop()
        else:
            self._start()

    # ══════════════════════════════════════
    #  PAGE: 任务编辑器
    # ══════════════════════════════════════

    def _editor_content(self):
        w = QWidget()
        w.setStyleSheet(f"background:{T.BG};")
        ly = QVBoxLayout(w)
        ly.setContentsMargins(T.SP_LG, T.SP_LG, T.SP_LG, T.SP_LG)
        ly.setSpacing(0)

        split = QSplitter(Qt.Horizontal)
        split.setHandleWidth(1)
        split.setStyleSheet(f"QSplitter::handle{{background:{T.LINE};}}")

        # ═══ LEFT: sidebar ═══
        left_panel = QWidget()
        left_panel.setStyleSheet(f"background:{T.CARD}; border:none; border-radius:{T.R_LG}px;")
        left_ly = QVBoxLayout(left_panel)
        left_ly.setContentsMargins(T.SP_LG, T.SP_LG, T.SP_LG, T.SP_LG)
        left_ly.setSpacing(T.SP_MD)

        left_ly.addWidget(section_title("任务名称"))
        self.ed_name = QComboBox()
        self.ed_name.setEditable(True)
        self.ed_name.setStyleSheet(f"""QComboBox{{background:{T.GREEN_BG};color:{T.GREEN};border:1px solid {T.GREEN}22;border-radius:{T.R_SM}px;padding:5px 14px;min-height:32px;max-height:32px;font-weight:600;font-size:12px;}}QComboBox::drop-down{{border:none;width:24px;}}QComboBox:hover{{background:{T.GREEN_BG};border:1px solid {T.GREEN}44;}}""")
        left_ly.addWidget(self.ed_name)

        left_ly.addWidget(section_title("操作"))
        for pair in [("+ 点击","click","+ 按键","press"), ("+ 等待","wait","+ 等到","wait_until")]:
            hr = QHBoxLayout(); hr.setSpacing(T.SP_SM)
            for t, a in [(pair[0],pair[1]), (pair[2],pair[3])]:
                b = btn_ghost(t); b.setCursor(Qt.PointingHandCursor)
                b.clicked.connect(lambda checked, act=a: self._ed_add(act))
                hr.addWidget(b)
            hr.addStretch(); left_ly.addLayout(hr)

        left_ly.addWidget(section_title("预览"))
        self._ed_preview = QLabel("选择步骤查看预览")
        self._ed_preview.setMinimumHeight(160)
        self._ed_preview.setAlignment(Qt.AlignCenter)
        self._ed_preview.setStyleSheet(f"background:{T.SURFACE};color:{T.TEXT3};border:1px solid {T.LINE};border-radius:{T.R_SM}px;font-size:11px;")
        left_ly.addWidget(self._ed_preview)

        loop_row = QHBoxLayout(); loop_row.setSpacing(T.SP_SM)
        loop_label = QLabel("循环")
        loop_label.setStyleSheet(f"font-size:13px;font-weight:700;color:{T.TEXT};")
        loop_row.addWidget(loop_label)
        self.ed_loop = QSpinBox(); self.ed_loop.setRange(1,9999); self.ed_loop.setValue(1); self.ed_loop.setFixedWidth(80)
        self.ed_loop.setStyleSheet(f"QSpinBox{{background:{T.GREEN_BG};color:{T.GREEN};border:1px solid {T.GREEN}22;border-radius:{T.R_SM}px;padding:5px 14px;min-height:32px;max-height:32px;font-weight:600;font-size:12px;}}QSpinBox::up-button,QSpinBox::down-button{{border:none;width:20px;background:transparent;}}QSpinBox:hover{{border:1px solid {T.GREEN}44;}}")
        loop_row.addWidget(self.ed_loop)
        times_label = QLabel("次")
        times_label.setStyleSheet(f"font-size:13px;font-weight:500;color:{T.TEXT2};")
        loop_row.addWidget(times_label); loop_row.addStretch(); left_ly.addLayout(loop_row)

        del_row = QHBoxLayout(); del_row.setSpacing(T.SP_SM)
        del_btn = btn_ghost("删"); del_btn.setToolTip("删除选中步骤")
        del_btn.clicked.connect(self._ed_del); del_row.addWidget(del_btn)
        clr_btn = btn_ghost("清空"); clr_btn.clicked.connect(self._ed_clr); del_row.addWidget(clr_btn)
        del_row.addStretch(); left_ly.addLayout(del_row)

        left_ly.addStretch(1)
        save = btn_primary("保存任务")
        save.setMinimumHeight(40)
        save.clicked.connect(self._ed_save)
        left_ly.addWidget(save)

        split.addWidget(left_panel)

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
        right_ly.addWidget(self.ed_list, 1)

        split.addWidget(right_panel)
        split.setSizes([280, 520])
        ly.addWidget(split, 1)
        return w

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
        name = self.ed_name.currentText().strip()
        if not name:
            self.log_msg("请先输入任务名称", "WARN")
            return
        if action == "press":
            k, ok = QInputDialog.getText(self, "按键", "按键名:")
            if ok and k.strip():
                self._ed.append((k.strip(), 0, 0, 0, 0, "press"))
                self._ed_refresh()
            return
        if action == "wait":
            s, ok = QInputDialog.getDouble(self, "等待", "秒:", 2.0, 0.1, 60, 1)
            if ok:
                self._ed.append((f"{s:.1f}秒", 0, 0, 0, 0, "wait"))
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
        cm = {"click": "点", "press": "按键", "wait": "等待", "wait_until": "等到"}
        for i, s in enumerate(self._ed):
            n, _, _, _, _, a = s
            c = cm.get(a, a)
            if a == "wait":
                text = f"  [{i+1}] 等待 {n}"
            elif a == "press":
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
        if hasattr(self, '_ed_task_dir') and self._ed_task_dir and os.path.isdir(self._ed_task_dir):
            d = self._ed_task_dir
        else:
            now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:21]
            d = data_dir(f"tasks/{now}")
        os.makedirs(d, exist_ok=True)

        # Store meta info (display name, timestamps)
        tasks, loop = {}, self.ed_loop.value()
        tasks["_meta"] = {
            "name": name,
            "created": now,
            "modified": datetime.datetime.now().isoformat()
        }
        for i, s in enumerate(self._ed):
            tpl, x, y, w, h, a = s
            sid = f"Step{i+1}"
            e = {"desc": f"步骤{i+1}"}
            if a == "wait":
                e["action"] = "wait"
                e["params"] = {"seconds": float(tpl.replace("秒", ""))}
            elif a == "press":
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
        if loop > 1 and "Step1" in tasks:
            tasks["Step1"]["maxTimes"] = loop
        with open(os.path.join(d, "task.json"), "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
        self.log_msg(f"已保存: {d}/task.json", "SUCCESS")
        self._ed_task_dir = None  # reset for next editing session
        self._scan()

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
        self._task_map.clear()
        self.task_combo.clear()

        # Scan built-in examples (read-only, bundled with exe)
        ex = resource_path("examples")
        if os.path.isdir(ex):
            for d in sorted(os.listdir(ex)):
                fp = os.path.join(ex, d, "task.json")
                if os.path.exists(fp):
                    self._task_map[d] = fp
                    self.task_combo.addItem(d)

        # Scan user data directory (timestamp folders, read _meta.name)
        user_dir = data_dir("tasks")
        if os.path.isdir(user_dir):
            for folder in sorted(os.listdir(user_dir)):
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
        path = self._task_map.get(self.task_combo.currentText())
        if not path or not os.path.exists(path):
            self.log_msg("未选择有效任务", "ERROR")
            return
        self._running = True
        self.run_btn.setText("\u25A0  停止")
        self._update_run_btn_style()
        self.progress.show()

        self.pulse_dot.set_color(T.ACCENT)
        self.pulse_dot.start_pulse()
        self.state_lbl.setText("运行中")
        self.state_lbl.setStyleSheet(f"color:{T.ACCENT2}; font-size:12px; font-weight:600; padding: 0 8px 0 4px;")  # ← 自定义运行中文字字号

        self.worker = TaskWorker(
            path, self.tpl_combo.currentText() or None,
            not self.popup_cb.isChecked(), self._region
        )
        self.worker.log.connect(self.log_msg)
        self.worker.finished.connect(self._done)
        self.showMinimized()
        self.worker.start()

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
        self._reset()
        self.log_msg(
            f"完成: {stats['steps']}步 {stats['popups_handled']}弹窗 {stats['errors']}错误",
            "SUCCESS"
        )
        self.status_lbl.setText(f" 完成 — {stats['steps']}步骤")

    def _reset(self):
        self._running = False
        self.run_btn.setText("\u25B6  开始运行")
        self._update_run_btn_style()
        self.progress.hide()
        self.pulse_dot.stop_pulse()
        self.pulse_dot.set_color(T.TEXT3)
        self.state_lbl.setText("就绪")
        self.state_lbl.setStyleSheet(f"color:{T.TEXT2}; font-size:12px; font-weight:500; padding: 0 8px 0 4px;")  # ← 自定义状态文字字号（就绪）

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
