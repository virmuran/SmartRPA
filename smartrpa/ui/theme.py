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
    """Dual-theme design tokens — call Theme.apply('light'|'dark'|'native') to switch."""

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
        self.mode = "native"

    # ── Theme-dependent properties ──

    @property
    def BG(self):
        return "#f0f0f0"  # Windows classic light gray

    @property
    def SURFACE(self):
        return "#f0f0f0"  # same as BG, no distinction

    @property
    def CARD(self):
        return "#ffffff"

    @property
    def CARD_HOVER(self):
        return "#e8f0fe"

    @property
    def LOG_BG(self):
        return "#ffffff"

    @property
    def LOG_TEXT(self):
        return "#333333"

    @property
    def ACCENT_DIM(self):
        return "#e8f0fe"

    @property
    def GREEN_BG(self):
        return "transparent"

    @property
    def ORANGE_BG(self):
        return "transparent"

    @property
    def RED_BG(self):
        return "transparent"

    @property
    def BLUE_BG(self):
        return "transparent"

    # ── Text colors ──
    TEXT_LIGHT  = "#000000"
    TEXT2_LIGHT = "#555555"
    TEXT3_LIGHT = "#888888"
    TEXT_DARK   = "#e8eaf0"
    TEXT2_DARK  = "#b0b4c0"
    TEXT3_DARK  = "#8c90a0"

    @property
    def TEXT(self):
        return self.TEXT_LIGHT if self.mode != "dark" else self.TEXT_DARK

    @property
    def TEXT2(self):
        return self.TEXT2_LIGHT if self.mode != "dark" else self.TEXT2_DARK

    @property
    def TEXT3(self):
        return self.TEXT3_LIGHT if self.mode != "dark" else self.TEXT3_DARK

    @property
    def LINE(self):
        return "#d0d0d0"

    @property
    def LINE_LIGHT(self):
        return "#c0c0c0"

    @property
    def DANGER_BORDER(self):
        return "#fca5a5"

    @property
    def DANGER_HOVER_BG(self):
        return "#fee2e2"

    def apply(self, mode: str) -> None:
        """Switch theme mode ('light'|'dark'|'native'). 'light' is alias for native."""
        self.mode = mode if mode in ("dark", "native") else "native"


# Global theme instance (default light)
T = Theme()


# ═══════════════════════════════════════════════
#  Global QSS Builder
# ═══════════════════════════════════════════════

def build_base_qss() -> str:
    """Minimal QSS — let native Windows style do the heavy lifting."""
    return f"""
* {{
    font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
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
    spacing: 8px;
}}

QSplitter::handle {{
    background: {T.LINE};
    width: 1px;
}}"""


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
