"""Settings Page — global app preferences: record, run, appearance, about.

Full implementation with QSettings persistence and theme integration.
"""
import os
import re

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QScrollArea, QFileDialog,
)
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QFont, QDesktopServices
from PySide6.QtCore import QUrl

from smartrpa import __version__
from smartrpa.ui.theme import (
    T, btn_ghost, section_header, section_title, page_title, page_subtitle,
    data_dir,
)


class SettingsPage(QWidget):
    """Page for application settings and preferences."""

    def __init__(self, parent=None):
        """Initialize the settings page."""
        super().__init__(parent)
        self._main_window = None
        self._settings = QSettings("SmartRPA", "SmartRPA")
        self._build()
        self._load_settings()

    # ── Public: dependency injection ──

    def set_main_window(self, mw) -> None:
        """Store reference to the main window for callbacks.

        Args:
            mw: The MainWindow instance that hosts this page.
        """
        self._main_window = mw
        if mw and hasattr(mw, 'theme_changed'):
            mw.theme_changed.connect(lambda _: self.refresh_theme())

    # ═══════════════════════════════════════════════
    #  Build UI
    # ═══════════════════════════════════════════════

    def _build(self) -> None:
        """Construct the settings page with scrollable card layout."""
        self.setStyleSheet(f"background: {T.BG};")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(T.SP_LG, T.SP_LG, T.SP_LG, T.SP_LG)
        outer.setSpacing(T.SP_LG)

        outer.addWidget(page_title("设置"))
        outer.addWidget(page_subtitle("配置应用参数与偏好"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        ly = QVBoxLayout(inner)
        ly.setContentsMargins(0, 0, T.SP_SM, 0)
        ly.setSpacing(T.SP_LG)
        scroll.setWidget(inner)

        # ═══ Card: 录制设置 ═══
        self._card_record = self._build_record_card()
        ly.addWidget(self._card_record)

        # ═══ Card: 运行设置 ═══
        self._card_run = self._build_run_card()
        ly.addWidget(self._card_run)

        # ═══ Card: 外观设置 ═══
        self._card_appearance = self._build_appearance_card()
        ly.addWidget(self._card_appearance)

        # ═══ Card: 关于 ═══
        self._card_about = self._build_about_card()
        ly.addWidget(self._card_about)

        ly.addStretch(1)
        outer.addWidget(scroll, 1)

    # ── Card: 录制设置 ──

    def _build_record_card(self) -> QWidget:
        """Build the recording settings card."""
        card = QWidget()
        card.setObjectName("_card_record")
        card.setStyleSheet(
            f"#_card_record{{background:{T.CARD};border:none;border-radius:{T.R_LG}px;}}"
        )
        ly = QVBoxLayout(card)
        ly.setContentsMargins(T.SP_XL, T.SP_LG, T.SP_XL, T.SP_LG)
        ly.setSpacing(T.SP_MD)

        ly.addWidget(section_header("录制设置"))

        # Stop hotkey
        hk_row = QHBoxLayout()
        hk_row.setSpacing(T.SP_SM)
        default_hk = self._settings.value("record/hotkey", "Key.f6")
        self.hk_label = QLabel(
            f"停止快捷键: {default_hk.replace('Key.', '').upper()}"
        )
        self.hk_label.setStyleSheet(f"font-size:13px;color:{T.TEXT2};")
        hk_row.addWidget(self.hk_label, 1)
        hk_btn = btn_ghost("重新设置")
        hk_btn.setCursor(Qt.PointingHandCursor)
        hk_btn.clicked.connect(self._config_record_hotkey)
        hk_row.addWidget(hk_btn)
        ly.addLayout(hk_row)

        # Template save dir
        tpl_row = QHBoxLayout()
        tpl_row.setSpacing(T.SP_SM)
        self.tpl_dir_label = QLabel(
            f"模板目录: {data_dir('tasks')}"
        )
        self.tpl_dir_label.setStyleSheet(f"font-size:13px;color:{T.TEXT2};")
        tpl_row.addWidget(self.tpl_dir_label, 1)
        tpl_btn = btn_ghost("浏览")
        tpl_btn.setCursor(Qt.PointingHandCursor)
        tpl_btn.clicked.connect(self._browse_tpl_dir)
        tpl_row.addWidget(tpl_btn)
        ly.addLayout(tpl_row)

        return card

    # ── Card: 运行设置 ──

    def _build_run_card(self) -> QWidget:
        """Build the running settings card."""
        card = QWidget()
        card.setObjectName("_card_run")
        card.setStyleSheet(
            f"#_card_run{{background:{T.CARD};border:none;border-radius:{T.R_LG}px;}}"
        )
        ly = QVBoxLayout(card)
        ly.setContentsMargins(T.SP_XL, T.SP_LG, T.SP_XL, T.SP_LG)
        ly.setSpacing(T.SP_MD)

        ly.addWidget(section_header("运行设置"))

        # Global hotkey
        ghk_row = QHBoxLayout()
        ghk_row.setSpacing(T.SP_SM)
        default_ghk = self._settings.value("global_hotkey", "<ctrl>+<shift>+r")
        self.ghk_label = QLabel(
            f"全局热键: {default_ghk.replace('<', '').replace('>', '').upper()}"
        )
        self.ghk_label.setStyleSheet(f"font-size:13px;color:{T.TEXT2};")
        ghk_row.addWidget(self.ghk_label, 1)
        ghk_btn = btn_ghost("设置")
        ghk_btn.setCursor(Qt.PointingHandCursor)
        ghk_btn.clicked.connect(self._config_global_hotkey)
        ghk_row.addWidget(ghk_btn)
        ly.addLayout(ghk_row)

        # Popup detection
        self.popup_cb = QCheckBox("自动处理弹窗")
        self.popup_cb.setChecked(True)
        self.popup_cb.stateChanged.connect(self._save_settings)
        ly.addWidget(self.popup_cb)

        # Default speed mode
        speed_row = QHBoxLayout()
        speed_row.setSpacing(T.SP_SM)
        speed_lbl = QLabel("默认速度模式:")
        speed_lbl.setStyleSheet(f"font-size:13px;color:{T.TEXT2};")
        speed_row.addWidget(speed_lbl)

        self.speed_normal_btn = QPushButton("正常")
        self.speed_normal_btn.setCheckable(True)
        self.speed_normal_btn.setCursor(Qt.PointingHandCursor)
        self.speed_fast_btn = QPushButton("⚡ 极速")
        self.speed_fast_btn.setCheckable(True)
        self.speed_fast_btn.setCursor(Qt.PointingHandCursor)

        self.speed_normal_btn.clicked.connect(
            lambda: self._set_speed_mode("normal")
        )
        self.speed_fast_btn.clicked.connect(
            lambda: self._set_speed_mode("fast")
        )

        self._update_speed_btn_styles("normal")
        speed_row.addWidget(self.speed_normal_btn)
        speed_row.addWidget(self.speed_fast_btn)
        speed_row.addStretch()
        ly.addLayout(speed_row)

        return card

    # ── Card: 外观设置 ──

    def _build_appearance_card(self) -> QWidget:
        """Build the appearance/theme card."""
        card = QWidget()
        card.setObjectName("_card_appearance")
        card.setStyleSheet(
            f"#_card_appearance{{background:{T.CARD};border:none;border-radius:{T.R_LG}px;}}"
        )
        ly = QVBoxLayout(card)
        ly.setContentsMargins(T.SP_XL, T.SP_LG, T.SP_XL, T.SP_LG)
        ly.setSpacing(T.SP_MD)

        ly.addWidget(section_header("外观设置"))

        theme_row = QHBoxLayout()
        theme_row.setSpacing(T.SP_SM)
        theme_lbl = QLabel("主题模式:")
        theme_lbl.setStyleSheet(f"font-size:13px;color:{T.TEXT2};")
        theme_row.addWidget(theme_lbl)

        self.theme_light_btn = QPushButton("☀ 浅色")
        self.theme_light_btn.setCheckable(True)
        self.theme_light_btn.setCursor(Qt.PointingHandCursor)
        self.theme_light_btn.clicked.connect(lambda: self._set_theme("light"))

        self.theme_dark_btn = QPushButton("🌙 深色")
        self.theme_dark_btn.setCheckable(True)
        self.theme_dark_btn.setCursor(Qt.PointingHandCursor)
        self.theme_dark_btn.clicked.connect(lambda: self._set_theme("dark"))

        theme_row.addWidget(self.theme_light_btn)
        theme_row.addWidget(self.theme_dark_btn)
        theme_row.addStretch()
        ly.addLayout(theme_row)

        # Set initial toggle state
        self._update_theme_btn_styles(T.mode)

        return card

    # ── Card: 关于 ──

    def _build_about_card(self) -> QWidget:
        """Build the about card."""
        card = QWidget()
        card.setObjectName("_card_about")
        card.setStyleSheet(
            f"#_card_about{{background:{T.CARD};border:none;border-radius:{T.R_LG}px;}}"
        )
        ly = QVBoxLayout(card)
        ly.setContentsMargins(T.SP_XL, T.SP_LG, T.SP_XL, T.SP_LG)
        ly.setSpacing(T.SP_MD)

        ly.addWidget(section_header("关于"))

        # Version
        ver_row = QHBoxLayout()
        ver_row.setSpacing(T.SP_SM)
        ver_lbl = QLabel(f"版本 {__version__}")
        ver_lbl.setStyleSheet(f"font-size:13px;color:{T.TEXT2};font-weight:600;")
        ver_row.addWidget(ver_lbl)
        ver_row.addStretch()
        ly.addLayout(ver_row)

        # GitHub link
        gh_row = QHBoxLayout()
        gh_row.setSpacing(T.SP_SM)
        gh_lbl = QLabel("SmartRPA — 视觉驱动的智能桌面自动化程序")
        gh_lbl.setStyleSheet(f"font-size:12px;color:{T.TEXT3};")
        gh_row.addWidget(gh_lbl)
        gh_row.addStretch()

        # Open GitHub button
        gh_btn = btn_ghost("GitHub")
        gh_btn.setCursor(Qt.PointingHandCursor)
        gh_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl("https://github.com")
            )
        )
        gh_row.addWidget(gh_btn)

        gh_btn2 = btn_ghost("检查更新")
        gh_btn2.setCursor(Qt.PointingHandCursor)
        gh_btn2.clicked.connect(self._check_update)
        gh_row.addWidget(gh_btn2)

        ly.addLayout(gh_row)

        return card

    # ═══════════════════════════════════════════════
    #  Settings Load / Save
    # ═══════════════════════════════════════════════

    def _load_settings(self) -> None:
        """Load all settings from QSettings into the UI."""
        # Stop hotkey
        hk = self._settings.value("record/hotkey", "Key.f6")
        self.hk_label.setText(f"停止快捷键: {hk.replace('Key.', '').upper()}")

        # Global hotkey
        ghk = self._settings.value("global_hotkey", "<ctrl>+<shift>+r")
        self.ghk_label.setText(
            f"全局热键: {ghk.replace('<', '').replace('>', '').upper()}"
        )

        # Popup detection
        popup = self._settings.value("run/popup", True)
        if isinstance(popup, str):
            popup = popup.lower() == "true"
        self.popup_cb.setChecked(popup)

        # Speed mode
        speed = self._settings.value("run/speed", "normal")
        self._update_speed_btn_styles(speed)

        # Theme
        theme = self._settings.value("theme", "light")
        self._update_theme_btn_styles(theme)

    def _save_settings(self) -> None:
        """Persist current UI state to QSettings."""
        self._settings.setValue("run/popup", self.popup_cb.isChecked())

    # ═══════════════════════════════════════════════
    #  Hotkey Configuration
    # ═══════════════════════════════════════════════

    def _config_record_hotkey(self) -> None:
        """Let user configure the recording stop hotkey by pressing a key."""
        try:
            from pynput import keyboard
        except ImportError:
            return

        import threading
        result = [None]

        def on_key(key):
            result[0] = str(key)
            return False

        listener = keyboard.Listener(on_press=on_key)
        listener.start()
        listener.join(timeout=5.0)
        listener.stop()

        if result[0]:
            key_str = result[0]
            self._settings.setValue("record/hotkey", key_str)
            self.hk_label.setText(
                f"停止快捷键: {key_str.replace('Key.', '').upper()}"
            )

    def _config_global_hotkey(self) -> None:
        """Let user configure global hotkey by pressing a key combo."""
        try:
            from pynput import keyboard
        except ImportError:
            return

        import threading
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
                    kn = p.replace("Key.", "")
                    mapped.append(f"<{kn.lower()}>")
                else:
                    mapped.append(p.lower())
            hotkey_str = "+".join(mapped)

            self._settings.setValue("global_hotkey", hotkey_str)
            self.ghk_label.setText(
                f"全局热键: {hotkey_str.replace('<', '').replace('>', '').upper()}"
            )

            # Restart global hotkey in main window
            if self._main_window and hasattr(self._main_window, '_stop_global_hotkey'):
                self._main_window._stop_global_hotkey()
                self._main_window._start_global_hotkey()

    # ═══════════════════════════════════════════════
    #  Misc Actions
    # ═══════════════════════════════════════════════

    def _browse_tpl_dir(self) -> None:
        """Browse for a template directory."""
        d = QFileDialog.getExistingDirectory(self, "选择模板保存目录")
        if d:
            self.tpl_dir_label.setText(f"模板目录: {d}")

    def _set_speed_mode(self, mode: str) -> None:
        """Set default speed mode and update UI.

        Args:
            mode: 'normal' or 'fast'.
        """
        self._settings.setValue("run/speed", mode)
        self._update_speed_btn_styles(mode)

    def _set_theme(self, mode: str) -> None:
        """Apply and persist the theme mode.

        Args:
            mode: 'light' or 'dark'.
        """
        self._settings.setValue("theme", mode)
        if self._main_window and hasattr(self._main_window, '_on_theme_toggle'):
            self._main_window._on_theme_toggle(mode)

    def _check_update(self) -> None:
        """Placeholder for version check."""
        pass  # Will be implemented in a future phase

    # ═══════════════════════════════════════════════
    #  Style Helpers
    # ═══════════════════════════════════════════════

    def _update_speed_btn_styles(self, mode: str) -> None:
        """Update speed toggle button styles.

        Args:
            mode: 'normal' or 'fast'.
        """
        is_normal = (mode == "normal")

        if is_normal:
            self.speed_normal_btn.setChecked(True)
            self.speed_fast_btn.setChecked(False)
            self.speed_normal_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {T.SURFACE};
                    color: {T.TEXT};
                    border: 1px solid {T.LINE_LIGHT};
                    border-radius: {T.R_SM}px;
                    padding: 4px 10px; font-weight: 700; font-size: 12px;
                    min-height: 26px; max-height: 26px;
                }}
            """)
            self.speed_fast_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {T.CARD};
                    color: {T.TEXT2};
                    border: 1px solid {T.LINE};
                    border-radius: {T.R_SM}px;
                    padding: 4px 10px; font-weight: 600; font-size: 12px;
                    min-height: 26px; max-height: 26px;
                }}
                QPushButton:hover {{ border: 1px solid {T.LINE_LIGHT}; }}
            """)
        else:
            self.speed_normal_btn.setChecked(False)
            self.speed_fast_btn.setChecked(True)
            self.speed_normal_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {T.CARD};
                    color: {T.TEXT2};
                    border: 1px solid {T.LINE};
                    border-radius: {T.R_SM}px;
                    padding: 4px 10px; font-weight: 600; font-size: 12px;
                    min-height: 26px; max-height: 26px;
                }}
                QPushButton:hover {{ border: 1px solid {T.LINE_LIGHT}; }}
            """)
            self.speed_fast_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {T.SURFACE};
                    color: {T.TEXT};
                    border: 1px solid {T.LINE_LIGHT};
                    border-radius: {T.R_SM}px;
                    padding: 4px 10px; font-weight: 700; font-size: 12px;
                    min-height: 26px; max-height: 26px;
                }}
            """)

    def _update_theme_btn_styles(self, mode: str) -> None:
        """Update theme toggle button styles.

        Args:
            mode: 'light' or 'dark'.
        """
        is_light = (mode == "light")

        if is_light:
            self.theme_light_btn.setChecked(True)
            self.theme_dark_btn.setChecked(False)
            self.theme_light_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {T.SURFACE};
                    color: {T.TEXT};
                    border: 1px solid {T.LINE_LIGHT};
                    border-radius: {T.R_SM}px;
                    padding: 4px 10px; font-weight: 700; font-size: 12px;
                    min-height: 26px; max-height: 26px;
                }}
            """)
            self.theme_dark_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {T.CARD};
                    color: {T.TEXT2};
                    border: 1px solid {T.LINE};
                    border-radius: {T.R_SM}px;
                    padding: 4px 10px; font-weight: 600; font-size: 12px;
                    min-height: 26px; max-height: 26px;
                }}
                QPushButton:hover {{ border: 1px solid {T.LINE_LIGHT}; }}
            """)
        else:
            self.theme_light_btn.setChecked(False)
            self.theme_dark_btn.setChecked(True)
            self.theme_light_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {T.CARD};
                    color: {T.TEXT2};
                    border: 1px solid {T.LINE};
                    border-radius: {T.R_SM}px;
                    padding: 4px 10px; font-weight: 600; font-size: 12px;
                    min-height: 26px; max-height: 26px;
                }}
                QPushButton:hover {{ border: 1px solid {T.LINE_LIGHT}; }}
            """)
            self.theme_dark_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {T.SURFACE};
                    color: {T.TEXT};
                    border: 1px solid {T.LINE_LIGHT};
                    border-radius: {T.R_SM}px;
                    padding: 4px 10px; font-weight: 700; font-size: 12px;
                    min-height: 26px; max-height: 26px;
                }}
            """)

    # ═══════════════════════════════════════════════
    #  Theme Refresh
    # ═══════════════════════════════════════════════

    def refresh_theme(self) -> None:
        """Refresh inline styles after a theme change."""
        self.setStyleSheet(f"background: {T.BG};")
        self._update_theme_btn_styles(T.mode)
        self._update_speed_btn_styles(
            self._settings.value("run/speed", "normal")
        )
        self.hk_label.setStyleSheet(f"font-size:13px;color:{T.TEXT2};")
        self.ghk_label.setStyleSheet(f"font-size:13px;color:{T.TEXT2};")
        self.tpl_dir_label.setStyleSheet(f"font-size:13px;color:{T.TEXT2};")
