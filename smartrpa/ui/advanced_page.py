"""Advanced Page — flow editor, task file browser, export/import.

Full implementation for experienced users: FlowEditor launcher,
NODE_REFERENCE viewer, task file management, export/import.
"""
import os
import shutil
import json
import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFileDialog, QInputDialog, QSplitter, QMessageBox,
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QFont, QDesktopServices

from smartrpa import __version__
from smartrpa.ui.theme import (
    T, resource_path, data_dir,
    page_title, page_subtitle, section_header, section_title,
    btn_primary, btn_ghost, btn_danger, sep,
)


class AdvancedPage(QWidget):
    """Page for advanced features: flow editing, task file management."""

    def __init__(self, parent=None, embedded: bool = False):
        """Initialize the advanced page.

        Args:
            parent: parent widget.
            embedded: if True, hide page title and flatten cards for nesting.
        """
        super().__init__(parent)
        self._main_window = None
        self._embedded = embedded
        self._build()

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
        """Construct the advanced page layout."""
        self.setStyleSheet(f"background: {T.CARD if not self._embedded else 'transparent'};")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0 if self._embedded else T.SP_LG, 0 if self._embedded else T.SP_LG, 0, 0)
        outer.setSpacing(T.SP_LG)

        if not self._embedded:
            outer.addWidget(page_title("高级功能"))
            outer.addWidget(page_subtitle("以下功能面向有经验的用户"))

        if self._embedded:
            # Cards go directly into the layout (no nested scroll area)
            self._add_cards(outer)
            outer.addStretch(1)
        else:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            inner = QWidget()
            inner.setStyleSheet("background:transparent;")
            ly = QVBoxLayout(inner)
            ly.setContentsMargins(0, 0, T.SP_SM, 0)
            ly.setSpacing(T.SP_LG)
            scroll.setWidget(inner)
            self._add_cards(ly)
            ly.addStretch(1)
            outer.addWidget(scroll, 1)

    def _add_cards(self, layout) -> None:
        """Add the advanced tool cards to the given layout."""
        # ═══ Card: 任务文件管理 ═══
        self._card_files = self._build_files_card()
        layout.addWidget(self._card_files)

        # ═══ Card: 导入导出 ═══
        self._card_io = self._build_io_card()
        layout.addWidget(self._card_io)

        # ═══ Card: 工具与参考 ═══
        self._card_ref = self._build_ref_card()
        layout.addWidget(self._card_ref)

    # ── Card: 任务文件管理 ──

    def _build_files_card(self) -> QWidget:
        """Build the task file management card."""
        card = QWidget()
        card.setObjectName("_card_files")
        card.setStyleSheet(
            f"#_card_files{{background:{T.CARD};border:none;border-radius:{T.R_LG}px;}}"
        )
        ly = QVBoxLayout(card)
        ly.setContentsMargins(T.SP_XL, T.SP_LG, T.SP_XL, T.SP_LG)
        ly.setSpacing(T.SP_MD)

        ly.addWidget(section_header("任务文件管理"))
        desc = QLabel("查看和浏览所有已保存的任务文件。")
        desc.setStyleSheet(f"font-size:12px;color:{T.TEXT3};")
        desc.setWordWrap(True)
        ly.addWidget(desc)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(T.SP_SM)

        view_btn = btn_primary("查看任务文件")
        view_btn.setCursor(Qt.PointingHandCursor)
        view_btn.clicked.connect(self._open_task_dir)
        btn_row.addWidget(view_btn)

        btn_row.addStretch()
        ly.addLayout(btn_row)

        return card

    # ── Card: 导入导出 ──

    def _build_io_card(self) -> QWidget:
        """Build the import/export card."""
        card = QWidget()
        card.setObjectName("_card_io")
        card.setStyleSheet(
            f"#_card_io{{background:{T.CARD};border:none;border-radius:{T.R_LG}px;}}"
        )
        ly = QVBoxLayout(card)
        ly.setContentsMargins(T.SP_XL, T.SP_LG, T.SP_XL, T.SP_LG)
        ly.setSpacing(T.SP_MD)

        ly.addWidget(section_header("导入 / 导出"))

        desc = QLabel("导出任务为 ZIP 文件，或从 ZIP 导入任务。")
        desc.setStyleSheet(f"font-size:12px;color:{T.TEXT3};")
        desc.setWordWrap(True)
        ly.addWidget(desc)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(T.SP_SM)

        export_btn = btn_primary("导出任务")
        export_btn.setCursor(Qt.PointingHandCursor)
        export_btn.clicked.connect(self._export_task)
        btn_row.addWidget(export_btn)

        import_btn = btn_ghost("导入任务")
        import_btn.setCursor(Qt.PointingHandCursor)
        import_btn.clicked.connect(self._import_task)
        btn_row.addWidget(import_btn)

        btn_row.addStretch()
        ly.addLayout(btn_row)

        return card

    # ── Card: 工具与参考 ──

    def _build_ref_card(self) -> QWidget:
        """Build the tools and reference card."""
        card = QWidget()
        card.setObjectName("_card_ref")
        card.setStyleSheet(
            f"#_card_ref{{background:{T.CARD};border:none;border-radius:{T.R_LG}px;}}"
        )
        ly = QVBoxLayout(card)
        ly.setContentsMargins(T.SP_XL, T.SP_LG, T.SP_XL, T.SP_LG)
        ly.setSpacing(T.SP_MD)

        ly.addWidget(section_header("工具与参考"))

        desc = QLabel("节点速查表、版本信息等参考资源。")
        desc.setStyleSheet(f"font-size:12px;color:{T.TEXT3};")
        desc.setWordWrap(True)
        ly.addWidget(desc)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(T.SP_SM)

        node_ref_btn = btn_ghost("节点速查表")
        node_ref_btn.setCursor(Qt.PointingHandCursor)
        node_ref_btn.clicked.connect(self._open_node_reference)
        btn_row.addWidget(node_ref_btn)

        ver_label = QLabel(f"v{__version__}")
        ver_label.setStyleSheet(f"color:{T.TEXT3};font-size:12px;padding:0 8px;")
        btn_row.addWidget(ver_label)

        btn_row.addStretch()
        ly.addLayout(btn_row)

        return card

    # ═══════════════════════════════════════════════
    #  Actions
    # ═══════════════════════════════════════════════

    def _open_task_dir(self) -> None:
        """Open the user tasks directory in file explorer."""
        task_dir = data_dir("tasks")
        QDesktopServices.openUrl(QUrl.fromLocalFile(task_dir))

    def _open_node_reference(self) -> None:
        """Open NODE_REFERENCE.md if it exists."""
        ref_path = resource_path("NODE_REFERENCE.md")
        if os.path.exists(ref_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(ref_path))
        else:
            # Fallback: open project root in explorer
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                )
            )

    def _export_task(self) -> None:
        """Export a task folder as ZIP."""
        # Ask which task to export
        task_dir = data_dir("tasks")
        if not os.path.isdir(task_dir):
            QMessageBox.information(self, "提示", "暂无任务可导出。")
            return

        # List task folders (those containing task.json)
        task_folders = []
        for name in sorted(os.listdir(task_dir)):
            full = os.path.join(task_dir, name)
            if os.path.isdir(full) and os.path.exists(
                os.path.join(full, "task.json")
            ):
                task_folders.append(name)

        if not task_folders:
            QMessageBox.information(self, "提示", "暂无任务可导出。")
            return

        # Let user pick a folder
        choice, ok = QInputDialog.getItem(
            self, "选择要导出的任务", "任务:", task_folders, 0, False,
        )
        if not ok or not choice:
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self, "导出任务", f"{choice}.zip", "ZIP 文件 (*.zip)",
        )
        if not save_path:
            return

        import zipfile
        try:
            src_dir = os.path.join(task_dir, choice)
            with zipfile.ZipFile(save_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(src_dir):
                    for fn in files:
                        fp = os.path.join(root, fn)
                        arcname = os.path.relpath(fp, src_dir)
                        zf.write(fp, arcname)
            QMessageBox.information(
                self, "导出成功",
                f"任务已导出到:\n{save_path}",
            )
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def _import_task(self) -> None:
        """Import a task from a ZIP file."""
        zip_path, _ = QFileDialog.getOpenFileName(
            self, "导入任务", "", "ZIP 文件 (*.zip)",
        )
        if not zip_path:
            return

        import zipfile
        try:
            now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:21]
            target = data_dir(f"tasks/{now}")
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(target)
            QMessageBox.information(
                self, "导入成功",
                f"任务已导入到:\n{target}",
            )
        except Exception as e:
            QMessageBox.critical(self, "导入失败", str(e))

    # ═══════════════════════════════════════════════
    #  Theme Refresh
    # ═══════════════════════════════════════════════

    def refresh_theme(self) -> None:
        """Refresh all inline styles after a theme change."""
        self.setStyleSheet(f"background: {T.BG};")
        for obj_name in [
            "_card_flow", "_card_files", "_card_io", "_card_ref",
        ]:
            card = self.findChild(QWidget, obj_name)
            if card:
                card.setStyleSheet(
                    f"#{obj_name}{{background:{T.CARD};border:none;"
                    f"border-radius:{T.R_LG}px;}}"
                )
