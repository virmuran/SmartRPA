"""MAA-Style Linear Task Editor — step-by-step with ROI-constrained templates.

Each step: action type + template image + ROI box + threshold.
Steps convert to behavior tree JSON on save.
"""
import os
import json
import datetime
from collections import Counter
from copy import deepcopy
from typing import List, Optional

from PySide6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QSplitter, QTabWidget,
    QPushButton, QLabel, QComboBox, QSpinBox, QDoubleSpinBox,
    QListWidget, QListWidgetItem, QMessageBox, QApplication,
    QFileDialog, QLineEdit,
)
from PySide6.QtCore import Qt, QRect, Signal, QPoint
from PySide6.QtGui import QPainter, QPen, QColor, QPixmap, QFont, QBrush

from smartrpa.ui.theme import T, data_dir, btn_primary, btn_ghost, section_title
from smartrpa.business.task_manager import TaskManager


# ═══════════════════════════════════════════════
#  Step Data
# ═══════════════════════════════════════════════

ACTION_TYPES = [
    ("click",    "点击",    ["template", "roi", "threshold"]),
    ("press",    "按键",    ["key"]),
    ("type",     "输入",    ["text"]),
    ("wait",     "等待",    ["seconds"]),
    ("hotkey",   "组合键",  ["keys"]),
    ("wait_until","等到出现",["template", "roi", "threshold", "timeout"]),
    ("find",     "检测",    ["template", "roi", "threshold"]),
]

ACTION_PARAMS_META = {a[0]: a[2] for a in ACTION_TYPES}
ACTION_LABELS = {a[0]: a[1] for a in ACTION_TYPES}


class StepData:
    """A single MAA-style step."""
    def __init__(self):
        self.action = "click"
        self.template = ""
        self.roi: List[int] = []      # relative [x, y, w, h]
        self.threshold = 0.8
        self.seconds = 1.0
        self.timeout = 30
        self.key = ""
        self.text = ""
        self.keys: List[str] = []
        self.window_title = ""         # target window title for ROI anchoring

    def to_dict(self) -> dict:
        d = {"action": self.action}
        params = {}
        for field in ACTION_PARAMS_META.get(self.action, []):
            val = getattr(self, field, None)
            if val is not None and val != "" and val != []:
                params[field] = val
        if self.window_title:
            params["window"] = self.window_title
        if params:
            d["params"] = params
        desc = self._desc()
        d["desc"] = desc
        return d

    def _desc(self) -> str:
        if self.action == "click":
            return f"点击 {self.template}.png" if self.template else "点击(坐标)"
        elif self.action == "press":
            return f"按键 {self.key}" if self.key else "按键(未设)"
        elif self.action == "type":
            return f"输入 {self.text}" if self.text else "输入(未设)"
        elif self.action == "wait":
            return f"等待 {self.seconds}s"
        elif self.action == "hotkey":
            return f"组合键 {','.join(self.keys)}" if self.keys else "组合键(未设)"
        elif self.action == "wait_until":
            return f"等到 {self.template}.png"
        elif self.action == "find":
            return f"检测 {self.template}.png"
        return self.action

    @property
    def needs_template(self) -> bool:
        return "template" in ACTION_PARAMS_META.get(self.action, [])


# ═══════════════════════════════════════════════
#  ROI Region Selector Overlay
# ═══════════════════════════════════════════════

class ROISelector(QDialog):
    """Full-screen overlay for selecting a screen region."""

    regionSelected = Signal(int, int, int, int)  # x, y, w, h

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setWindowState(Qt.WindowFullScreen)
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)

        screen = QApplication.primaryScreen()
        self._screenshot = screen.grabWindow(0)
        self.setFixedSize(self._screenshot.size())

        self._start = QPoint()
        self._end = QPoint()
        self._drawing = False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._screenshot)

        # Semi-transparent overlay
        overlay = QColor(0, 0, 0, 120)
        painter.setBrush(QBrush(overlay))
        painter.setPen(Qt.NoPen)
        painter.drawRect(self.rect())

        if self._drawing:
            rect = QRect(self._start, self._end).normalized()
            # Clear the selected area
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.drawRect(rect)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            # Border
            painter.setPen(QPen(QColor("#7c6ff7"), 2, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect)
            # Size label
            painter.setPen(QPen(QColor("white")))
            painter.setFont(QFont("Microsoft YaHei", 11))
            painter.drawText(rect.adjusted(4, 4, -4, -4), Qt.AlignLeft | Qt.AlignTop,
                           f"{rect.width()} x {rect.height()}")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._start = event.pos()
            self._end = event.pos()
            self._drawing = True
        elif event.button() == Qt.RightButton:
            self.close()

    def mouseMoveEvent(self, event):
        if self._drawing:
            self._end = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._drawing:
            self._drawing = False
            rect = QRect(self._start, self._end).normalized()
            if rect.width() > 5 and rect.height() > 5:
                self.regionSelected.emit(rect.x(), rect.y(), rect.width(), rect.height())
            self.close()


# ═══════════════════════════════════════════════
#  MAA Editor Dialog
# ═══════════════════════════════════════════════

class MAAEditor(QWidget):
    """MAA-style linear step editor widget — embeddable in tabs."""

    taskSaved = Signal(str)  # file_path

    def __init__(self, parent=None, tpl_dir: str = ""):
        super().__init__(parent)
        self._tpl_dir = tpl_dir
        self._steps: List[StepData] = []
        self._current_step_idx = -1
        self._task_mgr = TaskManager()
        self._selected_window = ""

        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(T.SP_XL, T.SP_XL, T.SP_XL, T.SP_XL)
        root.setSpacing(T.SP_LG)

        # Title
        hdr = QHBoxLayout()
        hdr.addWidget(section_title("MAA 模式 — 步骤编辑器"))
        hdr.addStretch()
        root.addLayout(hdr)

        # Main splitter: left steps | right editor
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet(f"QSplitter::handle{{background:{T.LINE};width:1px;}}")

        # Left: step list
        left = QWidget()
        left_ly = QVBoxLayout(left)
        left_ly.setContentsMargins(0, 0, 0, 0)
        left_ly.setSpacing(T.SP_SM)

        self._step_list = QListWidget()
        self._step_list.setStyleSheet(f"""
            QListWidget {{
                background: {T.CARD}; color: {T.TEXT};
                border: 1px solid {T.LINE}; border-radius: {T.R_SM}px;
                padding: 6px; font-size: 12px; outline: none;
            }}
            QListWidget::item {{ padding: 6px 10px; border-radius: 3px; }}
            QListWidget::item:selected {{ background: {T.ACCENT_DIM}; }}
        """)
        self._step_list.currentRowChanged.connect(self._on_step_selected)
        left_ly.addWidget(self._step_list, 1)

        # Step action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(T.SP_SM)

        add_btn = btn_ghost("+ 添加")
        add_btn.clicked.connect(self._add_step)
        btn_row.addWidget(add_btn)

        up_btn = btn_ghost("↑ 上移")
        up_btn.clicked.connect(self._move_up)
        btn_row.addWidget(up_btn)

        down_btn = btn_ghost("↓ 下移")
        down_btn.clicked.connect(self._move_down)
        btn_row.addWidget(down_btn)

        del_btn = btn_ghost("✕ 删除")
        del_btn.clicked.connect(self._delete_step)
        btn_row.addWidget(del_btn)

        btn_row.addStretch()
        left_ly.addLayout(btn_row)
        splitter.addWidget(left)

        # Right: step editor
        right = QWidget()
        right_ly = QVBoxLayout(right)
        right_ly.setContentsMargins(T.SP_LG, 0, 0, 0)
        right_ly.setSpacing(T.SP_MD)

        # Action type selector
        act_row = QHBoxLayout()
        act_row.addWidget(QLabel("动作:"))
        self._action_combo = QComboBox()
        for a_id, a_label, _ in ACTION_TYPES:
            self._action_combo.addItem(a_label, a_id)
        self._action_combo.currentIndexChanged.connect(self._on_action_changed)
        act_row.addWidget(self._action_combo, 1)
        right_ly.addLayout(act_row)

        # Window picker
        win_row = QHBoxLayout()
        win_row.addWidget(QLabel("窗口:"))
        self._window_combo = QComboBox()
        self._window_combo.setEditable(True)
        self._window_combo.setPlaceholderText("选择或输入目标窗口标题...")
        self._window_combo.currentTextChanged.connect(self._on_window_changed)
        win_row.addWidget(self._window_combo, 1)

        refresh_win_btn = btn_ghost("刷新")
        refresh_win_btn.setToolTip("重新扫描当前打开的窗口")
        refresh_win_btn.clicked.connect(self._refresh_windows)
        win_row.addWidget(refresh_win_btn)
        right_ly.addLayout(win_row)

        # Template (for click/find/wait_until)
        self._tpl_row = QHBoxLayout()
        self._tpl_row.addWidget(QLabel("模板:"))
        self._tpl_inp = QLabel("(未选择)")
        self._tpl_inp.setStyleSheet(
            f"color:{T.TEXT3};border:1px solid {T.LINE};border-radius:{T.R_SM}px;"
            f"padding:6px 10px;min-height:28px;max-height:28px;background:{T.CARD};")
        self._tpl_row.addWidget(self._tpl_inp, 1)

        cap_btn = btn_ghost("截图")
        cap_btn.setToolTip("框选屏幕区域，截取为模板图片")
        cap_btn.clicked.connect(self._capture_template_only)
        self._tpl_row.addWidget(cap_btn)

        pick_btn = btn_ghost("选文件")
        pick_btn.clicked.connect(self._pick_template)
        self._tpl_row.addWidget(pick_btn)
        right_ly.addLayout(self._tpl_row)

        # ROI display
        self._roi_row = QHBoxLayout()
        self._roi_row.addWidget(QLabel("ROI:"))
        self._roi_lbl = QLabel("(未设置)")
        self._roi_lbl.setStyleSheet(
            f"color:{T.TEXT3};border:1px solid {T.LINE};border-radius:{T.R_SM}px;"
            f"padding:6px 10px;min-height:28px;max-height:28px;background:{T.CARD};")
        self._roi_row.addWidget(self._roi_lbl, 1)

        roi_btn = btn_ghost("框选ROI")
        roi_btn.setToolTip("框选屏幕上的目标搜索区域，自动记录为窗口相对坐标")
        roi_btn.clicked.connect(self._select_roi_only)
        self._roi_row.addWidget(roi_btn)
        right_ly.addLayout(self._roi_row)

        # Threshold
        thresh_row = QHBoxLayout()
        thresh_row.addWidget(QLabel("阈值:"))
        self._threshold_spin = QDoubleSpinBox()
        self._threshold_spin.setRange(0.3, 1.0)
        self._threshold_spin.setSingleStep(0.05)
        self._threshold_spin.setValue(0.8)
        thresh_row.addWidget(self._threshold_spin, 1)
        right_ly.addLayout(thresh_row)

        # Key / Text / Seconds fields (dynamic)
        self._param_row = QHBoxLayout()
        right_ly.addLayout(self._param_row)

        # Save button
        self._save_step_btn = btn_primary("保存步骤")
        self._save_step_btn.clicked.connect(self._save_step)
        right_ly.addWidget(self._save_step_btn)

        right_ly.addStretch()
        splitter.addWidget(right)
        splitter.setSizes([350, 550])

        root.addWidget(splitter, 1)

        # Bottom: save task + run
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(T.SP_MD)
        bottom_row.addStretch()

        save_btn = btn_primary("保存任务文件")
        save_btn.clicked.connect(self._save_task)
        bottom_row.addWidget(save_btn)

        root.addLayout(bottom_row)

        self._refresh_param_fields()
        self._refresh_windows()

    # ── Window management ──

    def _refresh_windows(self):
        """Scan all open windows and populate the combo box."""
        try:
            import win32gui
            windows = []
            def enum_cb(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if title and title not in ("", "Program Manager"):
                        windows.append(title)
            win32gui.EnumWindows(enum_cb, None)

            current = self._window_combo.currentText()
            self._window_combo.blockSignals(True)
            self._window_combo.clear()
            for w in sorted(set(windows)):
                self._window_combo.addItem(w)
            if current and self._window_combo.findText(current) >= 0:
                self._window_combo.setCurrentText(current)
            self._window_combo.blockSignals(False)
        except (ImportError, Exception):
            pass

    def _on_window_changed(self, title):
        """Save selected window title to current step."""
        if self._current_step_idx >= 0:
            self._steps[self._current_step_idx].window_title = title
        # Also store globally for the task
        self._selected_window = title

    def _minimize_before_action(self):
        """Minimize SmartRPA before opening overlay windows."""
        for w in QApplication.topLevelWidgets():
            if w.isVisible() and w != self:
                w.showMinimized()
        self.showMinimized()
        QApplication.processEvents()
        import time; time.sleep(0.3)

    # ── Step list management ──

    def _add_step(self):
        step = StepData()
        self._steps.append(step)
        self._refresh_list()
        self._step_list.setCurrentRow(len(self._steps) - 1)

    def _move_up(self):
        idx = self._step_list.currentRow()
        if idx > 0:
            self._steps[idx], self._steps[idx - 1] = self._steps[idx - 1], self._steps[idx]
            self._refresh_list()
            self._step_list.setCurrentRow(idx - 1)

    def _move_down(self):
        idx = self._step_list.currentRow()
        if 0 <= idx < len(self._steps) - 1:
            self._steps[idx], self._steps[idx + 1] = self._steps[idx + 1], self._steps[idx]
            self._refresh_list()
            self._step_list.setCurrentRow(idx + 1)

    def _delete_step(self):
        idx = self._step_list.currentRow()
        if 0 <= idx < len(self._steps):
            del self._steps[idx]
            self._refresh_list()
            if self._steps:
                self._step_list.setCurrentRow(min(idx, len(self._steps) - 1))
            else:
                self._clear_editor()

    def _refresh_list(self):
        self._step_list.blockSignals(True)
        self._step_list.clear()
        for i, s in enumerate(self._steps):
            item = QListWidgetItem(f"{i + 1}. [{ACTION_LABELS.get(s.action, s.action)}] {s._desc()}")
            self._step_list.addItem(item)
        self._step_list.blockSignals(False)

    def _on_step_selected(self, idx):
        if 0 <= idx < len(self._steps):
            self._current_step_idx = idx
            self._load_step(self._steps[idx])

    def _load_step(self, step: StepData):
        # Action
        act_idx = self._action_combo.findData(step.action)
        if act_idx >= 0:
            self._action_combo.blockSignals(True)
            self._action_combo.setCurrentIndex(act_idx)
            self._action_combo.blockSignals(False)

        # Window
        if step.window_title:
            idx = self._window_combo.findText(step.window_title)
            if idx >= 0:
                self._window_combo.setCurrentIndex(idx)
            else:
                self._window_combo.setEditText(step.window_title)

        # Template
        self._tpl_inp.setText(step.template if step.template else "(未选择)")

        # ROI
        if step.roi and len(step.roi) == 4:
            self._roi_lbl.setText(f"[{step.roi[0]}, {step.roi[1]}] {step.roi[2]}x{step.roi[3]}")
        else:
            self._roi_lbl.setText("(未设置)")

        # Threshold
        self._threshold_spin.setValue(step.threshold)

        # Param fields
        self._refresh_param_fields()
        self._load_param_fields(step)

    def _clear_editor(self):
        self._current_step_idx = -1
        self._tpl_inp.setText("(未选择)")
        self._roi_lbl.setText("(未设置)")
        self._threshold_spin.setValue(0.8)

    def _on_action_changed(self, _idx):
        if 0 <= self._current_step_idx < len(self._steps):
            action = self._action_combo.currentData()
            self._steps[self._current_step_idx].action = action
            self._refresh_param_fields()
            self._refresh_list()

    def _save_step(self):
        if self._current_step_idx < 0 or self._current_step_idx >= len(self._steps):
            return
        step = self._steps[self._current_step_idx]
        step.action = self._action_combo.currentData()
        step.template = self._tpl_inp.text() if self._tpl_inp.text() != "(未选择)" else ""
        step.threshold = self._threshold_spin.value()

        # Collect from dynamic param fields
        self._collect_param_fields(step)

        self._refresh_list()
        QMessageBox.information(self, "已保存", f"步骤 {self._current_step_idx + 1} 已保存")

    # ── Dynamic param fields ──

    def _refresh_param_fields(self):
        while self._param_row.count():
            item = self._param_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if self._current_step_idx < 0:
            return

        action = self._action_combo.currentData()
        params = ACTION_PARAMS_META.get(action, [])

        for p in params:
            if p in ("template", "roi", "threshold"):
                continue  # handled by dedicated rows

            if p == "seconds":
                lbl = QLabel("秒数:")
                self._param_row.addWidget(lbl)
                spin = QDoubleSpinBox()
                spin.setRange(0.1, 300)
                spin.setValue(1.0)
                spin.valueChanged.connect(lambda v, f=p: self._set_step_attr(f, v))
                self._param_row.addWidget(spin, 1)
            elif p == "timeout":
                lbl = QLabel("超时(s):")
                self._param_row.addWidget(lbl)
                spin = QSpinBox()
                spin.setRange(1, 600)
                spin.setValue(30)
                spin.valueChanged.connect(lambda v, f=p: self._set_step_attr(f, v))
                self._param_row.addWidget(spin, 1)
            elif p in ("key", "text"):
                lbl = QLabel(p + ":")
                self._param_row.addWidget(lbl)
                inp = QLineEdit()
                inp.textChanged.connect(lambda v, f=p: self._set_step_attr(f, v))
                self._param_row.addWidget(inp, 1)
            elif p == "keys":
                lbl = QLabel("键位:")
                self._param_row.addWidget(lbl)
                inp = QLineEdit()
                inp.setPlaceholderText("逗号分隔, 如 ctrl,c")
                inp.textChanged.connect(lambda v, f=p: self._set_step_attr(f, v))
                self._param_row.addWidget(inp, 1)

        self._param_row.addStretch()

    def _set_step_attr(self, field: str, value):
        if 0 <= self._current_step_idx < len(self._steps):
            if field == "keys" and isinstance(value, str):
                value = [k.strip() for k in value.split(",") if k.strip()]
            setattr(self._steps[self._current_step_idx], field, value)

    def _load_param_fields(self, step: StepData):
        """Load existing step values into dynamic param fields."""
        for i in range(self._param_row.count()):
            w = self._param_row.itemAt(i).widget()
            if w is None:
                continue
            action = step.action
            params = ACTION_PARAMS_META.get(action, [])
            for p in params:
                if p in ("template", "roi", "threshold"):
                    continue
                val = getattr(step, p, None)
                if val is not None:
                    if isinstance(w, QDoubleSpinBox) and isinstance(val, (int, float)):
                        w.setValue(float(val))
                    elif isinstance(w, QSpinBox) and isinstance(val, int):
                        w.setValue(val)
                    elif hasattr(w, 'setText'):
                        if p == "keys" and isinstance(val, list):
                            w.setText(",".join(val))
                        else:
                            w.setText(str(val))

    def _collect_param_fields(self, step: StepData):
        """Collect values from dynamic fields into the step."""
        action = step.action
        params = [p for p in ACTION_PARAMS_META.get(action, [])
                  if p not in ("template", "roi", "threshold")]
        for i in range(self._param_row.count()):
            w = self._param_row.itemAt(i).widget()
            if w is None:
                continue
            for p in params:
                if isinstance(w, QDoubleSpinBox):
                    step.seconds = w.value()
                elif isinstance(w, QSpinBox):
                    step.timeout = w.value()
                elif hasattr(w, 'text') and p in ("key", "text"):
                    setattr(step, p, w.text())
                elif hasattr(w, 'text') and p == "keys":
                    step.keys = [k.strip() for k in w.text().split(",") if k.strip()]

    def _show_tpl_fields(self, visible: bool):
        for i in range(self._tpl_row.count()):
            w = self._tpl_row.itemAt(i).widget()
            if w:
                w.setVisible(visible)

    def _show_roi_fields(self, visible: bool):
        for i in range(self._roi_row.count()):
            w = self._roi_row.itemAt(i).widget()
            if w:
                w.setVisible(visible)

    # ── ROI / Template capture ──

    def _capture_template_only(self):
        """Capture a screen region and save ONLY as template (no ROI)."""
        if self._current_step_idx < 0:
            self._add_step()
            self._step_list.setCurrentRow(len(self._steps) - 1)
            self._current_step_idx = len(self._steps) - 1

        self._minimize_before_action()
        selector = ROISelector(self)
        selector.regionSelected.connect(lambda x, y, w, h: self._capture_template(x, y, w, h))
        selector.exec()

    def _select_roi_only(self):
        if self._current_step_idx < 0:
            return
        self._minimize_before_action()
        selector = ROISelector(self)
        selector.regionSelected.connect(self._on_roi_only)
        selector.exec()

    def _on_roi_only(self, x, y, w, h):
        if self._current_step_idx < 0:
            return
        step = self._steps[self._current_step_idx]
        step.window_title = self._window_combo.currentText()

        # Look up the chosen window's position (not just foreground)
        wx, wy = self._get_foreground_window_pos(step.window_title)
        if wx is not None:
            step.roi = [x - wx, y - wy, w, h]
            self._roi_lbl.setText(f"相对[{step.roi[0]}, {step.roi[1]}] {w}x{h}  ({step.window_title or '窗口'})")
        else:
            step.roi = [x, y, w, h]
            self._roi_lbl.setText(f"绝对[{x}, {y}] {w}x{h}  (窗口未找到)")

    def _get_foreground_window_pos(self, title: str = ""):
        """Get the top-left position of a window by title (or foreground if no title given).
        Returns (x, y) or (None, None)."""
        try:
            import win32gui
            if title:
                result = []
                def find_by_title(hwnd, _):
                    if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd) == title:
                        rect = win32gui.GetWindowRect(hwnd)
                        result.append((rect[0], rect[1]))
                win32gui.EnumWindows(find_by_title, None)
                if result:
                    return result[0]
            # Fallback to foreground
            hwnd = win32gui.GetForegroundWindow()
            rect = win32gui.GetWindowRect(hwnd)
            return rect[0], rect[1]
        except (ImportError, Exception):
            return None, None

    def _capture_template(self, x, y, w, h):
        """Capture the ROI region and save as a template image."""
        import mss
        import cv2
        import numpy as np

        # Ensure template dir exists
        if not self._tpl_dir:
            self._tpl_dir = data_dir("templates")
        os.makedirs(self._tpl_dir, exist_ok=True)

        # Generate unique template name
        import uuid
        tpl_name = f"maa_{uuid.uuid4().hex[:8]}"
        dest = os.path.join(self._tpl_dir, f"{tpl_name}.png")

        try:
            with mss.mss() as sct:
                region = {"left": x, "top": y, "width": w, "height": h}
                img = sct.grab(region)
                cv2.imwrite(dest, cv2.cvtColor(np.array(img), cv2.COLOR_BGRA2BGR))

            if self._current_step_idx >= 0:
                step = self._steps[self._current_step_idx]
                step.template = tpl_name
                self._tpl_inp.setText(tpl_name)
        except Exception as e:
            QMessageBox.warning(self, "截图失败", str(e))

    def _pick_template(self):
        """Pick template from existing file."""
        path, _ = QFileDialog.getOpenFileName(self, "选择模板图片", "", "PNG (*.png)")
        if not path:
            return

        import shutil
        basename = os.path.basename(path)
        name_no_ext = os.path.splitext(basename)[0]

        if self._tpl_dir:
            os.makedirs(self._tpl_dir, exist_ok=True)
            dest = os.path.join(self._tpl_dir, basename)
            if path != dest:
                shutil.copy2(path, dest)
            self._tpl_inp.setText(name_no_ext)
            if self._current_step_idx >= 0:
                self._steps[self._current_step_idx].template = name_no_ext
        else:
            self._tpl_inp.setText(name_no_ext)

    # ── Save Task ──

    def _save_task(self):
        """Convert steps to behavior tree JSON and save."""
        if not self._steps:
            QMessageBox.warning(self, "无步骤", "请先添加步骤")
            return

        # Ensure all steps are saved
        if self._current_step_idx >= 0:
            self._save_step()

        # Build behavior tree
        now = datetime.datetime.now()
        task_name = f"MAA_{now.strftime('%m月%d日_%H%M')}"

        nodes = {}
        for i, step in enumerate(self._steps):
            sid = f"Step{i + 1}"
            d = step.to_dict()
            # Ensure params dict for flat format compatibility
            if "params" in d:
                d.update(d.pop("params"))
            d.setdefault("action", step.action)
            d.setdefault("desc", step._desc())
            nodes[sid] = d
            if i > 0:
                nodes[f"Step{i}"]["next"] = [sid]

        # Wrap in BT format
        root = {"type": "sequence", "name": task_name, "children": []}
        for i, step in enumerate(self._steps):
            sid = f"Step{i + 1}"
            child = step.to_dict()
            child["name"] = step._desc()
            child["type"] = step.action
            root["children"].append(child)

        # Detect target window (use most common window title from steps with ROI)
        window = ""
        from collections import Counter
        window_titles = [s.window_title for s in self._steps if s.window_title]
        if window_titles:
            window = Counter(window_titles).most_common(1)[0][0]

        task_data = {
            "_meta": {
                "name": task_name,
                "window": window,
                "created": now.isoformat(),
                "modified": now.isoformat(),
            },
            "root": root,
        }

        # Save to user data
        task_dir = data_dir(f"tasks/{now.strftime('%Y%m%d_%H%M%S')}")
        os.makedirs(task_dir, exist_ok=True)

        # Save task.json
        task_path = os.path.join(task_dir, "task.json")
        with open(task_path, "w", encoding="utf-8") as f:
            json.dump(task_data, f, ensure_ascii=False, indent=2)

        # Copy templates to task dir
        if self._tpl_dir and os.path.isdir(self._tpl_dir):
            tpl_dest = os.path.join(task_dir, "templates")
            os.makedirs(tpl_dest, exist_ok=True)
            import shutil
            for fname in os.listdir(self._tpl_dir):
                if fname.endswith(".png"):
                    src = os.path.join(self._tpl_dir, fname)
                    dst = os.path.join(tpl_dest, fname)
                    if os.path.isfile(src) and not os.path.exists(dst):
                        shutil.copy2(src, dst)

        QMessageBox.information(self, "保存成功", f"任务已保存:\n{task_path}")
        self.taskSaved.emit(task_path)
