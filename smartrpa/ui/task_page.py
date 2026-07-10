"""Task Page — MAA-style task checklist, recording, running, config, log.

Full implementation of the main task management dashboard.
"""
import os
import re
import sys
import datetime
from typing import List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QCheckBox, QComboBox, QFileDialog,
    QTextEdit, QProgressBar, QSpinBox, QScrollArea,
    QListWidget, QListWidgetItem, QStackedWidget, QSizePolicy,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal, QTimer, QSettings, QSize, QUrl
from PySide6.QtGui import QFont, QIcon, QDesktopServices

from smartrpa.ui.theme import (
    T, data_dir, resource_path,
    btn_primary, btn_danger, btn_ghost,
    section_header, section_title, page_title, page_subtitle,
    sep, status_pill,
)
from smartrpa.business.task_manager import TaskManager
from smartrpa.ui.recorder import ActionRecorder
from smartrpa.ui.worker import TaskWorker


# ═══════════════════════════════════════════════
#  TaskPage
# ═══════════════════════════════════════════════

class TaskPage(QWidget):
    """Main task dashboard — checklist, record, run, config, log."""

    def __init__(self, parent=None):
        """Initialize the full task page."""
        super().__init__(parent)
        self._main_window = None
        self._task_mgr = TaskManager()

        # State
        self._running = False
        self._queue_index = 0
        self._loop_count = 0
        self._checked_names: List[str] = []
        self._max_loops = 1
        self._region = None
        self._worker = None
        self._recorder = None
        self._config_collapsed = False
        self._tpl_dirs = {}   # name → tpl_dir (cached from task manager)

        self._settings = QSettings("SmartRPA", "SmartRPA")

        self._build()
        self._scan()

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
        """Construct the complete task page layout."""
        self.setStyleSheet(f"background: {T.BG};")
        root = QVBoxLayout(self)
        root.setContentsMargins(T.SP_LG, T.SP_LG, T.SP_LG, T.SP_LG)
        root.setSpacing(T.SP_LG)

        # ── Header row: title + record/run buttons ──
        hdr = QHBoxLayout()
        hdr.setSpacing(T.SP_MD)
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_col.addWidget(page_title("自动化任务"))
        title_col.addWidget(page_subtitle("选择并运行您的自动化任务"))
        hdr.addLayout(title_col, 1)

        # Record button
        self.rec_btn = QPushButton("\u23FA  开始录制")
        self.rec_btn.setCursor(Qt.PointingHandCursor)
        self.rec_btn.setMinimumHeight(36)
        self.rec_btn.setMaximumHeight(36)
        self.rec_btn.setFixedWidth(140)
        self.rec_btn.clicked.connect(self._toggle_record)
        self._update_rec_btn_style(False)
        hdr.addWidget(self.rec_btn)

        # Run button
        self.run_btn = QPushButton("\u25B6  开始运行")
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.setMinimumHeight(36)
        self.run_btn.setMaximumHeight(36)
        self.run_btn.setFixedWidth(140)
        self.run_btn.clicked.connect(self._toggle_run)
        self._update_run_btn_style()
        hdr.addWidget(self.run_btn)

        root.addLayout(hdr)

        # ── Main splitter: left (list+config) | right (log) ──
        h_split = QSplitter(Qt.Horizontal)
        h_split.setHandleWidth(1)
        h_split.setStyleSheet(f"QSplitter::handle{{background:{T.LINE};}}")

        # ═══ LEFT: task list + config card ═══
        left_w = QWidget()
        left_w.setStyleSheet(f"background:{T.BG};")
        left_ly = QVBoxLayout(left_w)
        left_ly.setContentsMargins(0, 0, 0, 0)
        left_ly.setSpacing(T.SP_LG)

        # ── A. Task Checklist Card ──
        self._checklist_card = QWidget()
        self._checklist_card.setStyleSheet(
            f"background:{T.CARD};border:none;border-radius:{T.R_LG}px;"
        )
        cl_ly = QVBoxLayout(self._checklist_card)
        cl_ly.setContentsMargins(T.SP_LG, T.SP_LG, T.SP_LG, T.SP_LG)
        cl_ly.setSpacing(T.SP_MD)

        ch_hdr = QHBoxLayout()
        ch_hdr.addWidget(section_title("任务"))
        ch_hdr.addStretch()
        cl_ly.addLayout(ch_hdr)

        # Task list
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
        self.task_list.currentRowChanged.connect(self._on_task_selected)
        cl_ly.addWidget(self.task_list, 1)

        # Empty state label (shown when no tasks)
        self._empty_lbl = QLabel("点击下方录制按钮创建你的第一个任务")
        self._empty_lbl.setAlignment(Qt.AlignCenter)
        self._empty_lbl.setStyleSheet(
            f"color:{T.TEXT3};font-size:13px;padding:24px;background:transparent;"
        )
        cl_ly.addWidget(self._empty_lbl)
        self._empty_lbl.hide()

        # Hidden combo for task selection tracking (kept for compatibility)
        self.task_combo = QComboBox()
        self.task_combo.hide()
        cl_ly.addWidget(self.task_combo)

        # Bulk action buttons
        bulk_row = QHBoxLayout()
        bulk_row.setSpacing(T.SP_SM)
        sel_all_btn = btn_ghost("全选")
        sel_all_btn.clicked.connect(self._select_all_tasks)
        bulk_row.addWidget(sel_all_btn)
        inv_btn = btn_ghost("反选")
        inv_btn.clicked.connect(self._invert_task_selection)
        bulk_row.addWidget(inv_btn)
        clear_btn = btn_ghost("清空")
        clear_btn.clicked.connect(self._clear_task_checks)
        bulk_row.addWidget(clear_btn)
        bulk_row.addStretch()
        cl_ly.addLayout(bulk_row)

        left_ly.addWidget(self._checklist_card, 1)

        # ── D. Config Card (collapsible) ──
        self._cfg_card = QWidget()
        self._cfg_card.setStyleSheet(
            f"background:{T.CARD};border:none;border-radius:{T.R_LG}px;"
        )
        cfg_ly = QVBoxLayout(self._cfg_card)
        cfg_ly.setContentsMargins(T.SP_XL, T.SP_XL, T.SP_XL, T.SP_XL)
        cfg_ly.setSpacing(T.SP_LG)

        # Config header (clickable to collapse)
        cfg_hdr_row = QHBoxLayout()
        cfg_hdr_row.setSpacing(T.SP_SM)
        self._cfg_toggle_btn = QPushButton("\u25BC  配置")
        self._cfg_toggle_btn.setCursor(Qt.PointingHandCursor)
        self._cfg_toggle_btn.setFlat(True)
        self._cfg_toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {T.TEXT}; font-weight: 700; font-size: 13px;
                text-align: left; padding: 0;
            }}
            QPushButton:hover {{ color: {T.ACCENT}; }}
        """)
        self._cfg_toggle_btn.clicked.connect(self._toggle_config)
        cfg_hdr_row.addWidget(self._cfg_toggle_btn)
        cfg_hdr_row.addStretch()
        cfg_ly.addLayout(cfg_hdr_row)

        # Collapsible config body
        self._cfg_body = QWidget()
        cbl = QVBoxLayout(self._cfg_body)
        cbl.setContentsMargins(0, 0, 0, 0)
        cbl.setSpacing(T.SP_LG)

        # Template path row
        cbl.addWidget(section_title("模板路径"))
        tpl_row = QHBoxLayout()
        tpl_row.setSpacing(T.SP_SM)
        self.tpl_combo = QComboBox()
        self.tpl_combo.setEditable(True)
        self.tpl_combo.setStyleSheet(f"""
            QComboBox {{
                background: {T.CARD}; color: {T.TEXT};
                border: 1px solid {T.LINE}; border-radius: {T.R_SM}px;
                padding: 5px 14px; min-height: 26px; max-height: 26px;
                font-weight: 600; font-size: 12px;
            }}
            QComboBox::drop-down {{ border: none; width: 24px; }}
            QComboBox:hover {{ background: {T.SURFACE}; border: 1px solid {T.LINE_LIGHT}; }}
        """)
        tpl_row.addWidget(self.tpl_combo, 1)
        browse_btn = btn_ghost("浏览")
        browse_btn.setFixedWidth(64)
        browse_btn.clicked.connect(self._browse_tpl)
        tpl_row.addWidget(browse_btn)
        cbl.addLayout(tpl_row)

        # Compact row: region + repeat + fast
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
        self.run_loop.setStyleSheet(f"""
            QSpinBox {{
                background: {T.CARD}; color: {T.TEXT};
                border: 1px solid {T.LINE}; border-radius: {T.R_SM}px;
                padding: 5px 14px; min-height: 26px; max-height: 26px;
                font-weight: 600; font-size: 12px;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                border: none; width: 20px; background: transparent;
            }}
            QSpinBox:hover {{ border: 1px solid {T.LINE_LIGHT}; }}
        """)
        compact_row.addWidget(self.run_loop)
        loop_label = QLabel("次")
        loop_label.setStyleSheet(f"font-size:13px;font-weight:500;color:{T.TEXT2};")
        compact_row.addWidget(loop_label)
        compact_row.addSpacing(T.SP_MD)

        self.fast_toggle = QPushButton("\u26A1 极速")
        self.fast_toggle.setCheckable(True)
        self.fast_toggle.setCursor(Qt.PointingHandCursor)
        self.fast_toggle.setMinimumHeight(26)
        self.fast_toggle.setMaximumHeight(26)
        self.fast_toggle.toggled.connect(self._on_speed_toggle)
        self._update_speed_btn_style(False)
        compact_row.addWidget(self.fast_toggle)
        compact_row.addStretch()
        cbl.addLayout(compact_row)

        # Popup checkbox
        self.popup_cb = QCheckBox("自动处理弹窗")
        self.popup_cb.setChecked(True)
        cbl.addWidget(self.popup_cb)

        cfg_ly.addWidget(self._cfg_body)
        left_ly.addWidget(self._cfg_card)

        h_split.addWidget(left_w)

        # ═══ RIGHT: Log Panel ═══
        self._log_card = QWidget()
        self._log_card.setStyleSheet(
            f"background:{T.CARD};border:none;border-radius:{T.R_LG}px;"
        )
        rl = QVBoxLayout(self._log_card)
        rl.setContentsMargins(T.SP_LG, T.SP_XL, T.SP_LG, T.SP_LG)
        rl.setSpacing(T.SP_MD)

        log_hdr = QHBoxLayout()
        log_hdr.setSpacing(T.SP_SM)
        log_hdr.addWidget(section_header("日志"))
        log_hdr.addStretch()
        copy_btn = btn_ghost("复制")
        copy_btn.setToolTip("复制日志到剪贴板")
        copy_btn.clicked.connect(self._copy_log)
        log_hdr.addWidget(copy_btn)
        rl.addLayout(log_hdr)

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
        rl.addWidget(self.log, 1)

        clr_log_row = QHBoxLayout()
        clr_log_row.setSpacing(T.SP_SM)
        clr_log_btn = btn_ghost("清空日志")
        clr_log_btn.clicked.connect(self._clear_log)
        clr_log_row.addWidget(clr_log_btn)
        clr_log_row.addStretch()
        rl.addLayout(clr_log_row)

        h_split.addWidget(self._log_card)
        h_split.setSizes([460, 560])
        root.addWidget(h_split, 1)

    # ═══════════════════════════════════════════════
    #  Task Scanning & Checklist
    # ═══════════════════════════════════════════════

    def _scan(self) -> None:
        """Scan tasks and refresh the checklist."""
        names = self._task_mgr.scan_tasks()
        self._tpl_dirs.clear()

        self.task_combo.blockSignals(True)
        self.task_combo.clear()
        self.task_list.clear()

        for name in names:
            self._add_task_checklist_item(name)
            # Cache template dir for each task
            tpl_dir = self._task_mgr.get_task_templates_dir(name)
            if tpl_dir:
                self._tpl_dirs[name] = tpl_dir
            self.task_combo.addItem(name)

        self.task_combo.blockSignals(False)

        # Update empty state
        if self.task_list.count() == 0:
            self._empty_lbl.show()
        else:
            self._empty_lbl.hide()
            self.task_list.setCurrentRow(0)

    def _add_task_checklist_item(self, name: str, checked: bool = True) -> None:
        """Add a MAA-style checklist row: checkbox + name + settings gear.

        Args:
            name: Display name of the task.
            checked: Initial check state (default True).
        """
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
        cb.stateChanged.connect(
            lambda state, it=item: it.setData(Qt.UserRole + 1, state == Qt.Checked)
        )
        row_ly.addWidget(cb)

        lbl = QLabel(name)
        lbl.setStyleSheet(f"font-size:12px; color:{T.TEXT};")
        lbl.setWordWrap(False)
        row_ly.addWidget(lbl, 1)

        gear = QPushButton("\u2699")
        gear.setFixedSize(24, 24)
        gear.setCursor(Qt.PointingHandCursor)
        gear.setToolTip("配置此任务")
        gear.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {T.TEXT2}; font-size: 12px; border-radius: 4px;
            }}
            QPushButton:hover {{ background: {T.SURFACE}; color: {T.ACCENT}; }}
        """)
        gear.clicked.connect(lambda checked, n=name: self._configure_task(n))
        row_ly.addWidget(gear)

        self.task_list.setItemWidget(item, row_w)
        item.setData(Qt.UserRole + 1, checked)

    # ── Checklist Actions ──

    def _checked_task_names(self) -> List[str]:
        """Return list of currently checked task display names."""
        names = []
        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            if item.data(Qt.UserRole + 1):
                names.append(item.data(Qt.UserRole))
        return names

    def _select_all_tasks(self) -> None:
        """Check all tasks."""
        self._set_all_tasks_checked(True)

    def _clear_task_checks(self) -> None:
        """Uncheck all tasks."""
        self._set_all_tasks_checked(False)

    def _invert_task_selection(self) -> None:
        """Invert check state of all tasks."""
        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            widget = self.task_list.itemWidget(item)
            if widget:
                cb = widget.layout().itemAt(0).widget()
                cb.setChecked(not cb.isChecked())

    def _set_all_tasks_checked(self, checked: bool) -> None:
        """Set all task checkboxes to the given state."""
        for i in range(self.task_list.count()):
            item = self.task_list.item(i)
            widget = self.task_list.itemWidget(item)
            if widget:
                cb = widget.layout().itemAt(0).widget()
                cb.setChecked(checked)

    def _on_task_selected(self, idx: int) -> None:
        """Clicking a task row selects it for configuration."""
        if idx < 0:
            return
        item = self.task_list.item(idx)
        if not item:
            return
        task_name = item.data(Qt.UserRole)
        combo_idx = self.task_combo.findText(task_name)
        if combo_idx >= 0:
            self.task_combo.setCurrentIndex(combo_idx)
        # Update tpl_combo with the task's templates dir
        tpl_dir = self._tpl_dirs.get(task_name)
        if tpl_dir and os.path.isdir(tpl_dir):
            self.tpl_combo.setCurrentText(tpl_dir)

    def _configure_task(self, name: str) -> None:
        """Select a task in the combo so the global config applies to it."""
        combo_idx = self.task_combo.findText(name)
        if combo_idx >= 0:
            self.task_combo.setCurrentIndex(combo_idx)
        for i in range(self.task_list.count()):
            if self.task_list.item(i).data(Qt.UserRole) == name:
                self.task_list.setCurrentRow(i)
                break
        self.log_msg(f"已选择任务进行配置: {name}", "INFO")

    # ═══════════════════════════════════════════════
    #  Config Panel
    # ═══════════════════════════════════════════════

    def _toggle_config(self) -> None:
        """Collapse/expand the config panel."""
        self._config_collapsed = not self._config_collapsed
        self._cfg_body.setVisible(not self._config_collapsed)
        arrow = "\u25B6" if self._config_collapsed else "\u25BC"
        self._cfg_toggle_btn.setText(f"{arrow}  配置")

    def _browse_tpl(self) -> None:
        """Browse for a template directory."""
        d = QFileDialog.getExistingDirectory(self, "选择模板目录")
        if d:
            self.tpl_combo.setCurrentText(d)
            self.log_msg(f"模板路径: {d}", "INFO")

    def _select_region(self) -> None:
        """Select a screen region for the task to operate within."""
        self.log_msg("请框选操作区域（ESC 取消）...", "INFO")
        if self._main_window:
            self._main_window.showMinimized()
        else:
            self.window().showMinimized()

        # Use the RegionSelector from gui.py (import here to avoid circular import)
        try:
            from gui import RegionSelector
        except ImportError:
            self.log_msg("无法加载区域选择器", "ERROR")
            if self._main_window:
                self._main_window.showNormal()
            return

        d = RegionSelector()
        if d.exec() and d.region:
            self._region = d.region
            x, y, w, h = self._region
            self.region_lbl.setText(f"{x},{y}  {w}x{h}")
            self.region_lbl.setStyleSheet(f"""
                color: {T.GREEN};
                font-size: 12px; font-weight: 600;
                padding: 5px 14px; min-height: 32px; max-height: 32px;
                background: {T.GREEN_BG};
                border-radius: {T.R_SM}px;
                border: 1px solid {T.GREEN}22;
            """)
            self.log_msg(f"操作区域: {x},{y} {w}x{h}", "SUCCESS")

        if self._main_window:
            self._main_window.showNormal()
        else:
            self.window().showNormal()

    def _on_speed_toggle(self, checked: bool) -> None:
        """Update fast mode button style."""
        self._update_speed_btn_style(checked)

    # ═══════════════════════════════════════════════
    #  Recording
    # ═══════════════════════════════════════════════

    def _toggle_record(self) -> None:
        """Start or stop mouse/keyboard recording."""
        if hasattr(self, '_recorder') and self._recorder and self._recorder.isRunning():
            self._recorder.stop()
            self.rec_btn.setText("\u23FA  开始录制")
            self._update_rec_btn_style(False)
            if self._main_window:
                self._main_window.showNormal()
            self.log_msg("录制已停止", "WARN")
            return

        stop_key = self._settings.value("record/hotkey", "Key.f6")
        self._recorder = ActionRecorder(self, stop_key)
        self._recorder.log.connect(self.log_msg)
        self._recorder.finished.connect(self._on_record_finished)
        self._recorder.start()

        if self._main_window:
            self._main_window.showMinimized()
        else:
            self.window().showMinimized()

        self.rec_btn.setText("\u23F9  停止录制")
        self._update_rec_btn_style(True)
        self.log_msg(
            f"开始录制 — 按 {stop_key.replace('Key.', '')} 停止", "INFO"
        )

    def _on_record_finished(self, task_path: str) -> None:
        """Handle completion of recording."""
        self.rec_btn.setText("\u23FA  开始录制")
        self._update_rec_btn_style(False)
        if self._main_window:
            self._main_window.showNormal()
        self.log_msg("录制完成，新任务已加入清单", "SUCCESS")
        self._scan()

    # ═══════════════════════════════════════════════
    #  Running
    # ═══════════════════════════════════════════════

    def _toggle_run(self) -> None:
        """Start or stop task execution."""
        if self._running:
            self._stop()
        else:
            self._start()

    def _start(self) -> None:
        """Start running all checked tasks sequentially."""
        checked = self._checked_task_names()
        if not checked:
            self.log_msg("没有勾选任何任务", "WARN")
            return

        self._checked_names = checked
        self._queue_index = 0
        self._loop_count = 0
        self._max_loops = self.run_loop.value()

        self.log_msg(
            f"准备运行 {len(checked)} 个任务，循环 {self._max_loops} 次", "INFO"
        )
        self._set_running_state(True)
        self._run_next_checked()

    def _run_next_checked(self) -> None:
        """Run the next checked task in sequence."""
        if self._queue_index >= len(self._checked_names):
            self._loop_count += 1
            if self._loop_count < self._max_loops:
                self._queue_index = 0
                self.log_msg(
                    f"--- 第 {self._loop_count + 1}/{self._max_loops} 轮 ---", "INFO"
                )
            else:
                self._finish_run()
                return

        if self._queue_index >= len(self._checked_names):
            self._finish_run()
            return

        name = self._checked_names[self._queue_index]
        path = self._task_mgr.get_task_path(name)
        if not path or not os.path.exists(path):
            self.log_msg(f"任务文件不存在: {name}", "ERROR")
            self._queue_index += 1
            self._run_next_checked()
            return

        self.log_msg(
            f"[{self._queue_index + 1}/{len(self._checked_names)}] {name}", "INFO"
        )

        if self._main_window:
            self._main_window.set_status_text(
                f"运行中 [{self._queue_index + 1}/{len(self._checked_names)}]"
            )

        self._worker = TaskWorker(
            path,
            self.tpl_combo.currentText() or None,
            not self.popup_cb.isChecked(),
            self._region,
            self.fast_toggle.isChecked(),
        )
        self._worker.log.connect(self.log_msg)
        self._worker.finished.connect(self._done)

        if self._main_window:
            self._main_window.showMinimized()
        else:
            self.window().showMinimized()

        self._worker.start()

    def _done(self, stats: dict) -> None:
        """Handle completion of one task in the queue."""
        if self._main_window:
            self._main_window.showNormal()

        msg = (
            f"完成: {stats['steps']}步 {stats['popups_handled']}弹窗 "
            f"{stats['errors']}错误"
        )
        self.log_msg(msg, "SUCCESS" if stats['errors'] == 0 else "WARN")

        self._queue_index += 1
        self._run_next_checked()

    def _finish_run(self) -> None:
        """All checked tasks completed across all loops."""
        if self._main_window:
            self._main_window.showNormal()
        self._set_running_state(False)
        self.log_msg("所有任务执行完成", "SUCCESS")

    def _stop(self) -> None:
        """Stop the currently running task."""
        if self._worker:
            self._worker.stop()
        if self._main_window:
            self._main_window.showNormal()
        self._set_running_state(False)
        self.log_msg("已停止", "WARN")

    def _set_running_state(self, running: bool) -> None:
        """Update running state, button text, and main window indicator.

        Args:
            running: True for running, False for stopped/idle.
        """
        self._running = running
        if running:
            self.run_btn.setText("\u25A0  停止")
        else:
            self.run_btn.setText("\u25B6  开始运行")
        self._update_run_btn_style()

        if self._main_window:
            self._main_window.set_running(running)

    # ═══════════════════════════════════════════════
    #  Logging
    # ═══════════════════════════════════════════════

    def log_msg(self, msg: str, level: str = "INFO") -> None:
        """Append a colored log message.

        Args:
            msg: The log message text.
            level: One of INFO, SUCCESS, WARN, ERROR.
        """
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

    def _copy_log(self) -> None:
        """Copy log content to clipboard."""
        html = self.log.toHtml()
        text = re.sub(r'<[^>]+>', '', html)
        text = re.sub(r'\n\s*\n', '\n', text).strip()
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)
        self.log_msg("日志已复制到剪贴板", "SUCCESS")

    def _clear_log(self) -> None:
        """Clear all log content."""
        self.log.clear()
        self.log_msg("日志已清空", "INFO")

    # ═══════════════════════════════════════════════
    #  Style Helpers
    # ═══════════════════════════════════════════════

    def _update_run_btn_style(self) -> None:
        """Update the run/stop button style based on running state."""
        if self._running:
            self.run_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {T.RED_BG};
                    color: {T.RED};
                    border: 1px solid {T.DANGER_BORDER};
                    border-radius: {T.R_SM}px;
                    font-weight: 600; font-size: 12px;
                    padding: 5px 0; min-height: 26px; max-height: 26px;
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
                    color: white; border: none;
                    border-radius: {T.R_SM}px;
                    font-weight: 600; font-size: 12px;
                    padding: 5px 0; min-height: 26px; max-height: 26px;
                }}
                QPushButton:hover {{ background: {T.ACCENT2}; }}
            """)

    def _update_rec_btn_style(self, recording: bool) -> None:
        """Update the record button style based on recording state."""
        if recording:
            self.rec_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {T.RED};
                    color: white;
                    border: 1px solid {T.RED}88;
                    border-radius: {T.R_SM}px;
                    padding: 5px 0; font-weight: 600; font-size: 12px;
                    min-height: 26px; max-height: 26px;
                }}
                QPushButton:hover {{ background: #e06060; }}
            """)
        else:
            self.rec_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {T.RED_BG};
                    color: {T.RED};
                    border: 1px solid {T.RED}33;
                    border-radius: {T.R_SM}px;
                    padding: 5px 0; font-weight: 600; font-size: 12px;
                    min-height: 26px; max-height: 26px;
                }}
                QPushButton:hover {{ border: 1px solid {T.RED}66; }}
            """)

    def _update_speed_btn_style(self, fast: bool) -> None:
        """Update the fast mode toggle button style."""
        if fast:
            self.fast_toggle.setStyleSheet(f"""
                QPushButton {{
                    background: {T.SURFACE};
                    color: {T.TEXT};
                    border: 1px solid {T.LINE_LIGHT};
                    border-radius: {T.R_SM}px;
                    padding: 4px 10px; font-weight: 700; font-size: 12px;
                    min-height: 26px; max-height: 26px;
                }}
                QPushButton:hover {{ border: 1px solid {T.TEXT2}; }}
            """)
        else:
            self.fast_toggle.setStyleSheet(f"""
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

    # ═══════════════════════════════════════════════
    #  Theme Refresh
    # ═══════════════════════════════════════════════

    def refresh_theme(self) -> None:
        """Refresh all inline styles after a theme change."""
        self.setStyleSheet(f"background: {T.BG};")
        self._checklist_card.setStyleSheet(
            f"background:{T.CARD};border:none;border-radius:{T.R_LG}px;"
        )
        self._cfg_card.setStyleSheet(
            f"background:{T.CARD};border:none;border-radius:{T.R_LG}px;"
        )
        self._log_card.setStyleSheet(
            f"background:{T.CARD};border:none;border-radius:{T.R_LG}px;"
        )
        self._cfg_toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {T.TEXT}; font-weight: 700; font-size: 13px;
                text-align: left; padding: 0;
            }}
            QPushButton:hover {{ color: {T.ACCENT}; }}
        """)
        self._update_run_btn_style()
        self._update_rec_btn_style(False)
        self._update_speed_btn_style(self.fast_toggle.isChecked())
        self._empty_lbl.setStyleSheet(
            f"color:{T.TEXT3};font-size:13px;padding:24px;background:transparent;"
        )
