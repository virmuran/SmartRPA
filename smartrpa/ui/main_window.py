"""Main Window — QMainWindow with sidebar navigation, 4 tabs, system tray.

New architecture: sidebar + QStackedWidget, dependency-injected pages,
theme support, global hotkey, system tray. All page content is injected
via set_*_page() methods so there is zero dependency on page implementations.
"""
import sys
import os
import re

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QStackedWidget, QSystemTrayIcon, QMenu, QStatusBar,
    QProgressBar, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QTimer, QSettings, Slot, QSize, QRect
from PySide6.QtGui import (
    QFont, QPainter, QPen, QColor, QIcon, QPixmap, QDesktopServices,
)
from PySide6.QtCore import QUrl

from smartrpa import __version__
from smartrpa.ui.theme import (
    T, build_base_qss, resource_path, data_dir,
)


# ═══════════════════════════════════════════════
#  SidebarButton — Left sidebar navigation item
# ═══════════════════════════════════════════════

class SidebarButton(QWidget):
    """Left sidebar navigation — icon + text aligned horizontally."""

    clicked = Signal()

    def __init__(self, icon: str, label: str, parent=None):
        """Initialize sidebar button.

        Args:
            icon: Emoji or text icon string.
            label: Display text.
            parent: Parent widget.
        """
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

    def set_active(self, active: bool) -> None:
        """Toggle the active (selected) visual state."""
        self._active = active
        self._update_style()

    def _update_style(self) -> None:
        """Re-apply the active/inactive stylesheet."""
        if self._active:
            self.setStyleSheet(f"""
                SidebarButton {{background:{T.ACCENT_DIM};border:none;
                    border-left:3px solid {T.ACCENT};border-radius:0 4px 4px 0;}}
                QLabel {{color:{T.TEXT};font-weight:600;}}
            """)
        else:
            self.setStyleSheet(f"""
                SidebarButton {{background:transparent;border:none;
                    border-left:3px solid transparent;border-radius:0 4px 4px 0;}}
                QLabel {{color:{T.TEXT2};font-weight:500;}}
                SidebarButton:hover {{background:{T.CARD_HOVER};}}
                SidebarButton:hover QLabel {{color:{T.TEXT};}}
            """)

    def mousePressEvent(self, event) -> None:
        """Emit clicked signal on mouse press."""
        self.clicked.emit()
        super().mousePressEvent(event)


# ═══════════════════════════════════════════════
#  ThemeSwitch — Light/Dark toggle pill
# ═══════════════════════════════════════════════

class ThemeSwitch(QWidget):
    """A light/dark segmented control — horizontal pill with '浅色' / '深色' labels."""

    toggled = Signal(str)  # emits 'light' or 'dark'

    def __init__(self, initial: str = "light", parent=None):
        """Initialize theme switch.

        Args:
            initial: Starting mode ('light' or 'dark').
            parent: Parent widget.
        """
        super().__init__(parent)
        self._is_dark = (initial == "dark")
        self.setFixedSize(100, 32)
        self.setCursor(Qt.PointingHandCursor)
        self._update_style()

    def mousePressEvent(self, e) -> None:
        """Toggle dark/light on click."""
        self._is_dark = not self._is_dark
        self._update_style()
        self.toggled.emit("dark" if self._is_dark else "light")

    def set_mode(self, mode: str) -> None:
        """Programmatically set the theme mode."""
        self._is_dark = (mode == "dark")
        self._update_style()

    def _update_style(self) -> None:
        """Trigger repaint to reflect current mode."""
        self.update()

    def paintEvent(self, ev) -> None:
        """Custom paint: pill-shaped toggle with sliding indicator."""
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
        active_rect = QRect(2, 2, half - 2, h - 4) if not self._is_dark else QRect(half, 2, half - 2, h - 4)

        p.setBrush(QColor(T.CARD))
        p.drawRoundedRect(active_rect, r - 2, r - 2)

        # Text
        p.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Medium))
        for i, (txt, is_active) in enumerate(
            [("浅色", not self._is_dark), ("深色", self._is_dark)]
        ):
            tx = i * half
            p.setPen(QColor(T.TEXT) if is_active else QColor(T.TEXT3))
            p.drawText(QRect(tx, 0, half, h), Qt.AlignCenter, txt)

        p.end()


# ═══════════════════════════════════════════════
#  MainWindow
# ═══════════════════════════════════════════════

class MainWindow(QMainWindow):
    """Main application window with sidebar + 4 tabs + system tray."""

    #: Emitted when the theme is changed (mode: 'light' or 'dark')
    theme_changed = Signal(str)

    def __init__(self):
        """Initialize the main window with sidebar, stacked pages, and tray."""
        super().__init__()
        self._running = False
        self._nav_btns = []
        self._nav_idx = 0
        self._settings = QSettings("SmartRPA", "SmartRPA")

        # Restore theme preference
        saved = self._settings.value("theme", "light")
        T.apply(saved)

        self._build()
        self.setWindowTitle("SmartRPA")
        self.setWindowIcon(QIcon(resource_path("SmartRPA.ico")))
        self.resize(1160, 760)
        self.setMinimumSize(940, 600)

        # Start global hotkey listener
        self._start_global_hotkey()

    # ── Public: dependency injection for pages ──

    def set_task_page(self, page: QWidget) -> None:
        """Inject the task page widget into the stack at index 0.

        Args:
            page: A QWidget implementing the task page.
        """
        old = self.content_stack.widget(0)
        self.content_stack.removeWidget(old)
        if old:
            old.deleteLater()
        self.content_stack.insertWidget(0, page)

    def set_history_page(self, page: QWidget) -> None:
        """Inject the history page widget into the stack at index 1.

        Args:
            page: A QWidget implementing the history page.
        """
        old = self.content_stack.widget(1)
        self.content_stack.removeWidget(old)
        if old:
            old.deleteLater()
        self.content_stack.insertWidget(1, page)

    def set_settings_page(self, page: QWidget) -> None:
        """Inject the settings page widget into the stack at index 2.

        Args:
            page: A QWidget implementing the settings page.
        """
        old = self.content_stack.widget(2)
        self.content_stack.removeWidget(old)
        if old:
            old.deleteLater()
        self.content_stack.insertWidget(2, page)

    def set_advanced_page(self, page: QWidget) -> None:
        """Inject the advanced page widget into the stack at index 3.

        Args:
            page: A QWidget implementing the advanced page.
        """
        old = self.content_stack.widget(3)
        self.content_stack.removeWidget(old)
        if old:
            old.deleteLater()
        self.content_stack.insertWidget(3, page)

    # ── Close / Tray ──

    def closeEvent(self, event) -> None:
        """Override close: minimize to tray if schedule is active."""
        if hasattr(self, '_sched_cb') and self._sched_cb.isChecked():
            self.hide()
            self._tray.showMessage(
                "SmartRPA",
                "定时已启用，程序继续在后台运行",
                QSystemTrayIcon.MessageIcon.Information, 2000,
            )
            event.ignore()
        else:
            event.accept()
        self._stop_global_hotkey()

    # ── Internal: build UI ──

    def _build(self) -> None:
        """Construct the full main window UI."""
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

        # Logo
        logo_w = QWidget()
        logo_w.setStyleSheet("background: transparent;")
        logo_ly = QHBoxLayout(logo_w)
        logo_ly.setContentsMargins(16, 16, 16, 12)
        self._logo_label = QLabel("SmartRPA")
        self._logo_label.setStyleSheet(
            f"font-size:16px;font-weight:700;color:{T.TEXT};letter-spacing:-0.3px;"
        )
        logo_ly.addWidget(self._logo_label)
        logo_ly.addStretch()
        sb_ly.addWidget(logo_w)

        # Separator
        sep_line = QWidget()
        sep_line.setFixedHeight(1)
        sep_line.setStyleSheet(f"background: {T.LINE};")
        sb_ly.addWidget(sep_line)
        sb_ly.addSpacing(8)

        # Navigation buttons
        self.nav_btns = []
        nav_items = [
            ("📋", "自动化任务"),
            ("📜", "历史记录"),
            ("📊", "流程编辑"),
            ("🎯", "步骤编辑"),
            ("⚙", "系统设置"),
        ]
        for icon, label in nav_items:
            btn = SidebarButton(icon, label)
            btn.clicked.connect(
                lambda idx=len(self.nav_btns): self._switch_page(idx)
            )
            sb_ly.addWidget(btn)
            self.nav_btns.append(btn)
        self.nav_btns[0].set_active(True)
        sb_ly.addStretch(1)

        # Bottom: status + theme + version
        bottom_w = QWidget()
        bottom_w.setStyleSheet("background: transparent;")
        bot_ly = QVBoxLayout(bottom_w)
        bot_ly.setContentsMargins(12, 8, 12, 12)
        bot_ly.setSpacing(6)

        self.state_lbl = QLabel("就绪")
        self.state_lbl.setStyleSheet(
            f"color:{T.TEXT3};font-size:11px;padding:0 4px;"
        )
        bot_ly.addWidget(self.state_lbl)

        self.theme_switch = ThemeSwitch(T.mode)
        self.theme_switch.toggled.connect(self._on_theme_toggle)
        bot_ly.addWidget(self.theme_switch)

        self._ver_label = QLabel(f"v{__version__}")
        self._ver_label.setStyleSheet(
            f"color:{T.TEXT3};font-size:10px;padding:0 4px;"
        )
        bot_ly.addWidget(self._ver_label)
        sb_ly.addWidget(bottom_w)

        self.sidebar = sidebar
        root.addWidget(sidebar)

        # ═══ RIGHT: Content Area ═══
        self.right_widget = QWidget()
        self.right_widget.setStyleSheet(f"background: {T.BG};")
        right_ly = QVBoxLayout(self.right_widget)
        right_ly.setContentsMargins(0, 0, 0, 0)
        right_ly.setSpacing(0)

        # Thin progress bar at top of content area
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setMaximumHeight(2)
        self.progress.hide()
        right_ly.addWidget(self.progress)

        # Content Stack — create default pages via dependency injection
        self.content_stack = QStackedWidget()

        # Lazy-import page classes to avoid circular deps at module level
        from smartrpa.ui.task_page import TaskPage
        from smartrpa.ui.history_page import HistoryPage
        from smartrpa.ui.settings_page import SettingsPage

        task_page = TaskPage()
        task_page.set_main_window(self)
        self.content_stack.addWidget(task_page)

        history_page = HistoryPage()
        history_page.set_main_window(self)
        self.content_stack.addWidget(history_page)

        # Flow editor page (index 2)
        flow_page = self._build_flow_page()
        self.content_stack.addWidget(flow_page)

        # MAA editor page (index 3)
        maa_page = self._build_maa_page()
        self.content_stack.addWidget(maa_page)

        settings_page = SettingsPage()
        settings_page.set_main_window(self)
        self.content_stack.addWidget(settings_page)

        right_ly.addWidget(self.content_stack, 1)

        # Status Bar
        self.status = QStatusBar()
        self.status_lbl = QLabel(" SmartRPA 就绪")
        self.status_lbl.setStyleSheet(f"color:{T.TEXT3};")
        self.status.addWidget(self.status_lbl, 1)
        self.version_lbl = QLabel(f"v{__version__}")
        self.version_lbl.setStyleSheet(
            f"color:{T.TEXT3}; font-size:11px; padding:0 8px;"
        )
        self.version_lbl.setCursor(Qt.PointingHandCursor)
        self.status.addPermanentWidget(self.version_lbl)
        self.setStatusBar(self.status)

        root.addWidget(self.right_widget, 1)

        # ── System Tray ──
        self._tray = QSystemTrayIcon(self)
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "SmartRPA.ico")
        self._tray.setIcon(QIcon(icon_path))
        self._tray.setToolTip("SmartRPA")
        tray_menu = QMenu()
        show_action = tray_menu.addAction("显示窗口")
        show_action.triggered.connect(self.showNormal)
        quit_action = tray_menu.addAction("退出")
        quit_action.triggered.connect(QApplication.quit)
        self._tray.setContextMenu(tray_menu)
        self._tray.activated.connect(
            lambda reason: self.showNormal()
            if reason == QSystemTrayIcon.DoubleClick else None
        )
        self._tray.show()

    # ── Page Switching ──

    def _switch_page(self, idx: int) -> None:
        """Switch the content stack to the given page index."""
        self._nav_idx = idx
        self.content_stack.setCurrentIndex(idx)
        for i, btn in enumerate(self.nav_btns):
            btn.set_active(i == idx)

    # ── Theme Toggle ──

    def _on_theme_toggle(self, mode: str) -> None:
        """Handle theme switch from the sidebar toggle."""
        T.apply(mode)
        self._settings.setValue("theme", mode)
        self.theme_switch.set_mode(mode)
        QApplication.instance().setStyleSheet(build_base_qss())
        self._refresh_all_styles()
        self.theme_changed.emit(mode)

    def _build_flow_page(self) -> QWidget:
        """Build the flow editor page for the sidebar."""
        from smartrpa.ui.flow_editor import FlowEditor
        container = QWidget()
        ly = QVBoxLayout(container)
        ly.setContentsMargins(0, 0, 0, 0)
        ed = FlowEditor()
        ly.addWidget(ed, 1)
        return container

    def _build_maa_page(self) -> QWidget:
        """Build the MAA editor page for the sidebar."""
        from smartrpa.ui.maa_editor import MAAEditor
        from smartrpa.ui.theme import data_dir
        container = QWidget()
        container.setStyleSheet(f"background: {T.BG};")
        ly = QVBoxLayout(container)
        ly.setContentsMargins(0, 0, 0, 0)
        ed = MAAEditor(container, tpl_dir=data_dir("templates"))
        ly.addWidget(ed, 1)
        return container

    def _refresh_all_styles(self) -> None:
        """Refresh all inline styles after theme switch."""
        self.sidebar.setStyleSheet(f"background: {T.BG};")
        self.right_widget.setStyleSheet(f"background: {T.BG};")

        if hasattr(self, '_logo_label'):
            self._logo_label.setStyleSheet(
                f"font-size:16px;font-weight:700;color:{T.TEXT};letter-spacing:-0.3px;"
            )

        if hasattr(self, '_ver_label'):
            self._ver_label.setStyleSheet(
                f"color:{T.TEXT3};font-size:10px;padding:0 4px;"
            )

        if self._running:
            self.state_lbl.setStyleSheet(
                f"color:{T.ACCENT2};font-size:11px;padding:0 4px;"
            )
        else:
            self.state_lbl.setStyleSheet(
                f"color:{T.TEXT3};font-size:11px;padding:0 4px;"
            )

        self.status_lbl.setStyleSheet(f"color:{T.TEXT3};")
        if hasattr(self, 'version_lbl'):
            self.version_lbl.setStyleSheet(
                f"color:{T.TEXT3}; font-size:11px; padding:0 8px;"
            )

        for btn in self.nav_btns:
            btn._update_style()
        self.theme_switch._update_style()

        # Re-style content stack pages
        for i in range(self.content_stack.count()):
            w = self.content_stack.widget(i)
            w.setStyleSheet(f"background: {T.BG};")

    # ── Global Hotkey ──

    def _start_global_hotkey(self) -> None:
        """Start background global hotkey listener."""
        import threading
        from pynput import keyboard as kb

        def on_activate():
            from PySide6.QtCore import QMetaObject
            QMetaObject.invokeMethod(
                self, "_on_global_hotkey", Qt.ConnectionType.QueuedConnection
            )

        hotkey_str = self._settings.value("global_hotkey", "<ctrl>+<shift>+r")
        # Auto-fix bare F-keys from older settings (F10 -> <f10>)
        hotkey_str = re.sub(r'\b([Ff]\d+)\b', r'<\1>', hotkey_str)
        try:
            self._ghk_listener = kb.GlobalHotKeys({hotkey_str: on_activate})
            self._ghk_listener.daemon = True
            self._ghk_listener.start()
        except Exception:
            pass  # Silently fail — user can configure later

    def _stop_global_hotkey(self) -> None:
        """Stop the global hotkey listener."""
        if hasattr(self, '_ghk_listener') and self._ghk_listener:
            self._ghk_listener.stop()
            self._ghk_listener = None

    @Slot()
    def _on_global_hotkey(self) -> None:
        """Global hotkey pressed: show/focus window."""
        if self.isHidden() or self.isMinimized():
            self.showNormal()
            self.activateWindow()

    # ── Public helpers ──

    def set_running(self, running: bool) -> None:
        """Update the running state indicator.

        Args:
            running: True if a task is currently executing.
        """
        self._running = running
        if running:
            self.state_lbl.setStyleSheet(
                f"color:{T.ACCENT2};font-size:11px;padding:0 4px;"
            )
            self.progress.show()
        else:
            self.state_lbl.setStyleSheet(
                f"color:{T.TEXT3};font-size:11px;padding:0 4px;"
            )
            self.state_lbl.setText("就绪")
            self.progress.hide()

    def set_status_text(self, text: str) -> None:
        """Set the status bar text.

        Args:
            text: Status message to display.
        """
        self.state_lbl.setText(text)
        self.status_lbl.setText(f" {text}")

    def get_settings(self) -> QSettings:
        """Return the application QSettings instance."""
        return self._settings
