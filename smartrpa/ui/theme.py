"""SmartRPA Design System — Theme Tokens, QSS Builder, UI Helpers.

Extracted from gui.py. Zero dependencies on other SmartRPA modules.
"""
import sys
import os

from PySide6.QtWidgets import (
    QPushButton, QLabel, QFrame, QApplication,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


# ═══════════════════════════════════════════════
#  Path Utilities
# ═══════════════════════════════════════════════

def resource_path(relative_path: str) -> str:
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
    <exe_dir>/SmartRPA_data/ if present (seeded by pack.bat).
    """
    if os.name == "nt":
        base = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "SmartRPA")
    else:
        base = os.path.join(os.path.expanduser("~"), ".smartrpa")
    if subdir:
        base = os.path.join(base, subdir)
    os.makedirs(base, exist_ok=True)
    return base


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
    R_SM    = 4
    R_MD    = 6
    R_LG    = 12
    R_XL    = 20
    ACCENT     = "#7c6ff7"
    ACCENT2    = "#a78bfa"
    GREEN      = "#22c55e"
    ORANGE     = "#fbbf24"
    RED        = "#f87171"
    BLUE       = "#60a5fa"

    def __init__(self):
        self.mode = "light"

    # ── Theme-dependent properties ──

    @property
    def BG(self):
        return "#f4f4f8" if self.mode == "light" else "#0c0c12"

    @property
    def SURFACE(self):
        return "#e8e9ee" if self.mode == "light" else "#14141e"

    @property
    def CARD(self):
        return "#ffffff" if self.mode == "light" else "#1c1c28"

    @property
    def CARD_HOVER(self):
        return "#f0f0f5" if self.mode == "light" else "#24243a"

    @property
    def LOG_BG(self):
        return "#f5f5f8" if self.mode == "light" else "#0e0e16"

    @property
    def LOG_TEXT(self):
        return "#4a4a5a" if self.mode == "light" else "#94a1b8"

    @property
    def ACCENT_DIM(self):
        return "#eae6ff" if self.mode == "light" else "#2e2656"

    @property
    def GREEN_BG(self):
        return "#f0fdf4" if self.mode == "light" else "#1a2a1e"

    @property
    def ORANGE_BG(self):
        return "#fffbeb" if self.mode == "light" else "#2d2510"

    @property
    def RED_BG(self):
        return "#fef2f2" if self.mode == "light" else "#2d1418"

    @property
    def BLUE_BG(self):
        return "#eff6ff" if self.mode == "light" else "#1a2540"

    # ── Text colors ──
    TEXT_LIGHT  = "#1d1d1f"
    TEXT2_LIGHT = "#4a4a5a"
    TEXT3_LIGHT = "#7a7a82"
    TEXT_DARK   = "#e8eaf0"
    TEXT2_DARK  = "#b0b4c0"
    TEXT3_DARK  = "#8c90a0"

    @property
    def TEXT(self):
        return self.TEXT_LIGHT if self.mode == "light" else self.TEXT_DARK

    @property
    def TEXT2(self):
        return self.TEXT2_LIGHT if self.mode == "light" else self.TEXT2_DARK

    @property
    def TEXT3(self):
        return self.TEXT3_LIGHT if self.mode == "light" else self.TEXT3_DARK

    @property
    def LINE(self):
        return "#e2e2e8" if self.mode == "light" else "#252536"

    @property
    def LINE_LIGHT(self):
        return "#c8c8d0" if self.mode == "light" else "#32324a"

    @property
    def DANGER_BORDER(self):
        return "#fca5a5" if self.mode == "light" else "#5c2024"

    @property
    def DANGER_HOVER_BG(self):
        return "#fee2e2" if self.mode == "light" else "#3d1a1e"

    def apply(self, mode: str) -> None:
        """Switch theme mode ('light' or 'dark')."""
        self.mode = mode if mode in ("light", "dark") else "light"


# Global theme instance (default light)
T = Theme()


# ═══════════════════════════════════════════════
#  Global QSS Builder
# ═══════════════════════════════════════════════

def build_base_qss() -> str:
    """Re-generate QSS from current theme tokens."""
    return f"""
* {{
    font-family: "Microsoft YaHei", "PingFang SC", "SF Pro Display", sans-serif;
    font-size: 13px;
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

def btn_primary(text: str) -> QPushButton:
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


def btn_danger(text: str) -> QPushButton:
    """Danger button — same size as primary."""
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


def btn_ghost(text: str, icon: str = "") -> QPushButton:
    """Ghost button — subtle, for secondary actions."""
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


def section_header(text: str) -> QLabel:
    """Section header label — uppercase, muted, tracking."""
    l = QLabel(text.upper())
    l.setStyleSheet(f"""
        font-size: 13px;
        font-weight: 700;
        color: {T.TEXT};
        letter-spacing: 2px;
        padding-bottom: 2px;
    """)
    return l


def section_title(text: str) -> QLabel:
    """Section sub-title — medium weight, secondary color."""
    l = QLabel(text)
    l.setStyleSheet(f"font-size:13px; font-weight:700; color:{T.TEXT};")  # ← 自定义分区标题字号
    return l


def page_title(text: str) -> QLabel:
    """Page title — large, bold, primary color."""
    l = QLabel(text)
    l.setStyleSheet(f"font-size:24px; font-weight:700; color:{T.TEXT}; letter-spacing:-0.5px;")
    return l


def page_subtitle(text: str) -> QLabel:
    """Page subtitle — descriptive, secondary color."""
    l = QLabel(text)
    l.setStyleSheet(f"font-size:14px; color:{T.TEXT2}; font-weight:400;")  # ← 自定义描述文字字号
    return l


def sep() -> QFrame:
    """Horizontal separator line."""
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet(f"color:{T.LINE}; max-height:1px; margin:4px 0;")
    return f


def status_pill(text: str, color: str = None, bg: str = None) -> QLabel:
    """Status pill label — rounded, colored."""
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
