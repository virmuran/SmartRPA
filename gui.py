"""SmartRPA GUI - MAA风格界面 (PySide6)"""
import sys, os, json, glob, time as _time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QCheckBox, QComboBox, QFileDialog,
    QTextEdit, QProgressBar, QStackedWidget, QTabBar,
    QFrame, QSplitter, QScrollArea, QSizePolicy, QDialog,
    QRubberBand, QInputDialog, QSpinBox
)
from PySide6.QtCore import Qt, QThread, Signal, QRect, QPoint
from PySide6.QtGui import QFont, QPainter, QPen, QPixmap

from smartrpa import Controller, Vision, TaskEngine, PopupHandler
from callback_2048 import callback_2048


# ── Colors (Light theme) ──

C_BG      = "#f5f5f5"
C_DARK    = "#ffffff"
C_CARD    = "#ffffff"
C_ACCENT  = "#1976D2"
C_ACCENT2 = "#1565C0"
C_TEXT    = "#212121"
C_TEXT2   = "#757575"
C_SUCCESS = "#388E3C"
C_WARN    = "#F57C00"
C_ERROR   = "#D32F2F"
C_BORDER  = "#e0e0e0"
C_START   = "#43A047"

STYLE = f"""
* {{ font-family:"Microsoft YaHei",sans-serif; font-size:13px; }}
QMainWindow {{ background:{C_BG}; }}
QTabBar::tab {{ 
    background:{C_DARK}; color:{C_TEXT2}; border:none; padding:10px 22px; 
    font-size:13px; min-width:80px;
}}
QTabBar::tab:selected {{ color:{C_TEXT}; border-bottom:3px solid {C_ACCENT}; background:transparent; }}
QTabBar::tab:hover:!selected {{ color:{C_TEXT}; }}
QLabel {{ color:{C_TEXT}; background:transparent; }}
QCheckBox {{ color:{C_TEXT}; spacing:8px; background:transparent; }}
QCheckBox::indicator {{ width:18px; height:18px; border:2px solid {C_BORDER}; border-radius:3px; background:{C_DARK}; }}
QCheckBox::indicator:checked {{ background:{C_ACCENT}; border-color:{C_ACCENT}; }}
QComboBox {{ background:{C_DARK}; color:{C_TEXT}; border:1px solid {C_BORDER}; border-radius:4px; padding:6px 10px; min-height:26px; }}
QComboBox:drop-down {{ border:none; width:20px; }}
QComboBox QAbstractItemView {{ background:{C_DARK}; color:{C_TEXT}; selection-background-color:{C_ACCENT}; border:1px solid {C_BORDER}; }}
QPushButton {{ background:{C_DARK}; color:{C_TEXT}; border:1px solid {C_BORDER}; border-radius:4px; padding:6px 14px; min-height:28px; }}
QPushButton:hover {{ background:#eeeeee; border-color:{C_ACCENT}; }}
QPushButton:pressed {{ background:#e0e0e0; }}
QScrollArea {{ border:none; background:transparent; }}
QScrollBar:vertical {{ background:{C_BG}; width:8px; border:none; }}
QScrollBar::handle:vertical {{ background:{C_BORDER}; border-radius:4px; min-height:30px; }}
QScrollBar::handle:vertical:hover {{ background:{C_ACCENT2}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
QProgressBar {{ background:{C_BG}; border:1px solid {C_BORDER}; border-radius:3px; height:6px; text-align:center; }}
QProgressBar::chunk {{ background:{C_ACCENT}; border-radius:3px; }}
QTextEdit {{ background:{C_DARK}; color:{C_TEXT}; border:1px solid {C_BORDER}; border-radius:4px; padding:8px; font-size:12px; }}
QSplitter::handle {{ background:{C_BORDER}; width:1px; }}
"""


class TaskWorker(QThread):
    log = Signal(str, str)
    finished = Signal(dict)
    task_changed = Signal(str)

    def __init__(self, task_file, tpl_dir=None, no_popup=False, region=None):
        super().__init__()
        self.task_file = task_file
        self.tpl_dir = tpl_dir
        self.no_popup = no_popup
        self.region = region
        self._active = True

    def run(self):
        try:
            vision = Vision()
            if self.tpl_dir: vision.set_template_dir(self.tpl_dir)
            ctrl = Controller()
            popup = PopupHandler(vision, ctrl)
            popup.enabled = not self.no_popup
            engine = TaskEngine(ctrl, vision, popup)
            engine.region = self.region
            engine._user_log = lambda msg, level: self.log.emit(msg, level)
            if self.region:
                callback_2048._palette = None
                engine.on("play_2048", callback_2048)
            engine.load(self.task_file)
            entry = list(engine._tasks.keys())[0]
            self.log.emit(f"任务: {os.path.basename(self.task_file)}", "INFO")
            self.log.emit(f"入口: {entry}", "INFO")

            orig = engine._execute_step
            cnt = [0]
            def hook(ss, t):
                if not self._active: return False
                cnt[0] += 1
                self.task_changed.emit(t.get("desc", ""))
                return orig(ss, t)
            engine._execute_step = hook
            engine.run(entry)
            s = engine._stats
            self.log.emit(f"完成: {s['steps']}步, {s['popups_handled']}弹窗, {s['errors']}错误", "SUCCESS")
            self.finished.emit(s)
        except Exception as e:
            import traceback
            self.log.emit(f"错误: {e}", "ERROR")
            self.log.emit(traceback.format_exc(), "ERROR")

    def stop(self): self._active = False


class RegionSelector(QDialog):
    """全屏遮罩拖拽选区域"""
    def __init__(self):
        super().__init__()
        self.region = None
        self.start = self.end = None
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setWindowState(Qt.WindowFullScreen)
        self.setCursor(Qt.CrossCursor)
        screen = QApplication.primaryScreen()
        self.bg = screen.grabWindow(0)
        self.setGeometry(screen.geometry())

    def paintEvent(self, e):
        p = QPainter(self)
        p.drawPixmap(0, 0, self.bg)
        p.fillRect(self.rect(), QColor(0,0,0,130))
        if self.start and self.end:
            r = QRect(self.start, self.end).normalized()
            p.drawPixmap(r, self.bg, r)
            p.setPen(QPen(QColor(C_ACCENT), 2))
            p.drawRect(r)
            p.setPen(QColor("white"))
            p.drawText(r.left()+4, r.top()+16, f"{r.width()} x {r.height()}")

    def mousePressEvent(self, e): self.start = self.end = e.pos(); self.update()
    def mouseMoveEvent(self, e): self.end = e.pos(); self.update()
    def mouseReleaseEvent(self, e):
        self.end = e.pos()
        r = QRect(self.start, self.end).normalized()
        if r.width()>20 and r.height()>20:
            self.region = (r.x(), r.y(), r.width(), r.height())
            self.accept()
        else:
            self.reject()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape: self.reject()


class SmartRPAGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = None
        self._running = False
        self._task_map = {}
        self._checkboxes = {}
        self._region = (0, 0, QApplication.primaryScreen().size().width(),
                        QApplication.primaryScreen().size().height())
        self._editor_steps = []
        self._build()
        self._scan()
        self.setWindowTitle("SmartRPA")
        self.resize(980, 700)

    # ── BUILD ──

    def _build(self):
        cw = QWidget()
        self.setCentralWidget(cw)
        root = QVBoxLayout(cw)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top bar: tabs + task selector ──
        bar = QWidget()
        bar.setStyleSheet(f"background:{C_DARK};")
        bar_h = QHBoxLayout(bar)
        bar_h.setContentsMargins(0, 0, 8, 0)
        bar_h.setSpacing(0)

        self.tab_btns = {}
        self.tab_stack = QStackedWidget()
        for name, label in [("Tasks","自动化任务"), ("Editor","任务编辑器"), ("Settings","设置"), ("About","关于")]:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setStyleSheet(f"""
                QPushButton {{ background:transparent; color:{C_TEXT2}; border:none; 
                    border-bottom:3px solid transparent; padding:12px 22px; font-size:13px; }}
                QPushButton:checked {{ color:{C_ACCENT}; border-bottom:3px solid {C_ACCENT}; }}
                QPushButton:hover:!checked {{ color:{C_TEXT}; }}
            """)
            btn.clicked.connect(lambda _, n=name: self._switch_tab(n))
            bar_h.addWidget(btn)
            self.tab_btns[name] = btn
        bar_h.addStretch()
        root.addWidget(bar)

        # ── Tab pages ──
        self.tab_stack.addWidget(self._page_tasks())
        self.tab_stack.addWidget(self._page_editor())
        self.tab_stack.addWidget(self._page_settings())
        self.tab_stack.addWidget(self._page_about())
        root.addWidget(self.tab_stack, 1)
        self._switch_tab("Tasks")

    def _switch_tab(self, name):
        for tn, btn in self.tab_btns.items():
            btn.setChecked(tn == name)
        pages = {"Tasks":0, "Editor":1, "Settings":2, "About":3}
        self.tab_stack.setCurrentIndex(pages.get(name, 0))

    # ── PAGE: Tasks (3-column) ──

    def _section(self, title):
        """Return a styled section label"""
        lbl = QLabel(title)
        lbl.setStyleSheet(f"color:{C_TEXT2}; font-size:11px; font-weight:bold; padding:4px 0;")
        return lbl

    def _page_tasks(self):
        page = QWidget()
        page.setStyleSheet(f"background:{C_BG};")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        split = QSplitter(Qt.Horizontal)
        split.setHandleWidth(1)

        # ── COL 1: Step checklist ──
        left = QWidget()
        left.setStyleSheet(f"background:{C_DARK};")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(14, 14, 14, 10)
        ll.setSpacing(6)

        ll.addWidget(self._section("任务步骤"))
        self.task_list = QWidget()
        self.task_list_layout = QVBoxLayout(self.task_list)
        self.task_list_layout.setSpacing(4)
        self.task_list_layout.setContentsMargins(0, 4, 0, 0)
        self.task_list_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.task_list)
        ll.addWidget(scroll, 1)
        split.addWidget(left)

        # ── COL 2: Config ──
        center = QWidget()
        cl = QVBoxLayout(center)
        cl.setContentsMargins(18, 16, 18, 12)
        cl.setSpacing(10)

        #  选择任务
        cl.addWidget(self._section("选择任务"))
        task_bar = QHBoxLayout()
        self.task_combo = QComboBox()
        self.task_combo.setMinimumWidth(160)
        self.task_combo.currentIndexChanged.connect(self._on_task_changed)
        task_bar.addWidget(self.task_combo, 1)
        scan_btn = QPushButton("扫描")
        scan_btn.clicked.connect(self._scan)
        task_bar.addWidget(scan_btn)
        cl.addLayout(task_bar)

        cl.addWidget(QHLine())

        #  模板目录
        cl.addWidget(self._section("模板目录"))
        tpl_bar = QHBoxLayout()
        self.tpl_combo = QComboBox()
        self.tpl_combo.setEditable(True)
        tpl_bar.addWidget(self.tpl_combo, 1)
        tpl_btn = QPushButton("浏览")
        tpl_btn.setMaximumWidth(50)
        tpl_btn.clicked.connect(self._browse_tpl)
        tpl_bar.addWidget(tpl_btn)
        cl.addLayout(tpl_bar)

        cl.addWidget(QHLine())

        #  操作区域
        cl.addWidget(self._section("操作区域"))
        reg_row = QHBoxLayout()
        self.region_lbl = QLabel("全屏")
        self.region_lbl.setStyleSheet(f"color:{C_SUCCESS}; padding:5px 10px; background:{C_CARD}; border-radius:3px;")
        reg_row.addWidget(self.region_lbl, 1)
        reg_btn = QPushButton("框选区域")
        reg_btn.clicked.connect(self._select_region)
        reg_row.addWidget(reg_btn)
        cl.addLayout(reg_row)

        cl.addWidget(QHLine())

        #  其他选项
        cl.addWidget(self._section("运行选项"))
        self.popup_cb = QCheckBox("自动处理弹窗")
        self.popup_cb.setChecked(True)
        cl.addWidget(self.popup_cb)

        cl.addStretch()
        split.addWidget(center)

        # ── COL 3: Log ──
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(14, 14, 14, 10)
        rl.setSpacing(8)

        rl.addWidget(self._section("运行日志"))
        self.log_widget = QTextEdit()
        self.log_widget.setReadOnly(True)
        self.log_widget.setFont(QFont("Consolas", 10))
        self.log_widget.document().setMaximumBlockCount(2000)
        rl.addWidget(self.log_widget, 1)
        split.addWidget(right)

        split.setSizes([200, 280, 420])
        layout.addWidget(split, 1)

        # ── Bottom bar ──
        bottom = QWidget()
        bottom.setStyleSheet(f"background:{C_DARK};")
        bh = QHBoxLayout(bottom)
        bh.setContentsMargins(16, 10, 16, 10)
        bh.setSpacing(12)

        self.start_btn = QPushButton("Link Start!")
        self.start_btn.setMinimumSize(140, 40)
        self.start_btn.setStyleSheet(f"""
            QPushButton{{background:{C_START}; color:white; border:none; border-radius:4px; 
                         font-size:16px; font-weight:bold;}}
            QPushButton:hover{{background:#2ecc71;}}
            QPushButton:disabled{{background:#2a3a5c; color:#555;}}
        """)
        self.start_btn.clicked.connect(self._start)
        bh.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setMinimumSize(100, 40)
        self.stop_btn.setStyleSheet(f"""
            QPushButton{{background:{C_ERROR}; color:white; border:none; border-radius:4px;
                         font-size:15px; font-weight:bold;}}
            QPushButton:hover{{background:#ef5350;}}
            QPushButton:disabled{{background:#2a3a5c; color:#555;}}
        """)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop)
        bh.addWidget(self.stop_btn)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setMaximumHeight(4)
        self.progress.hide()
        bh.addWidget(self.progress, 1)

        bh.addStretch()

        self.task_hint = QLabel("")
        self.task_hint.setStyleSheet(f"color:{C_ACCENT}; font-size:13px;")
        bh.addWidget(self.task_hint)

        layout.addWidget(bottom)
        return page

    # ── PAGE: Editor ──

    def _page_editor(self):
        w = QWidget()
        ly = QVBoxLayout(w)
        ly.setContentsMargins(24, 20, 24, 16)
        ly.setSpacing(12)

        t = QLabel("任务编辑器")
        t.setStyleSheet("font-size:18px; font-weight:bold; color:{C_TEXT};")
        ly.addWidget(t)
        ly.addWidget(QLabel("无需写代码，点击屏幕即可创建自动化。"))

        nm = QHBoxLayout()
        nm.addWidget(QLabel("任务名称:"))
        self.ed_name = QComboBox()
        self.ed_name.setEditable(True)
        self.ed_name.addItem("")
        nm.addWidget(self.ed_name, 1)
        ly.addLayout(nm)

        self.ed_list = QTextEdit()
        self.ed_list.setReadOnly(True)
        self.ed_list.setMaximumHeight(180)
        self.ed_list.setFont(QFont("Consolas", 10))
        self.ed_list.setStyleSheet(f"background:{C_CARD}; color:{C_TEXT}; border:1px solid {C_BORDER}; border-radius:4px; padding:8px;")
        ly.addWidget(self.ed_list)

        btn_row = QHBoxLayout()
        for label, action in [("+ 点击操作","click"), ("+ 按键操作","press"), ("+ 等待","wait"), ("+ 等待出现","wait_until")]:
            b = QPushButton(label)
            b.clicked.connect(lambda _, a=action: self._ed_add(a))
            btn_row.addWidget(b)
        btn_row.addStretch()
        ly.addLayout(btn_row)

        ctrl = QHBoxLayout()
        ctrl.addWidget(QPushButton("删除最后一步", clicked=self._ed_del))
        ctrl.addWidget(QPushButton("清空全部", clicked=self._ed_clr))
        ctrl.addStretch()

        loop_row = QHBoxLayout()
        loop_row.addWidget(QLabel("重复次数:"))
        self.ed_loop = QSpinBox()
        self.ed_loop.setRange(1, 9999)
        self.ed_loop.setValue(1)
        loop_row.addWidget(self.ed_loop)
        loop_row.addWidget(QLabel("次"))
        loop_row.addStretch()
        ly.addLayout(loop_row)
        ly.addLayout(ctrl)

        save_btn = QPushButton("保存任务")
        save_btn.setMinimumHeight(36)
        save_btn.setStyleSheet(f"background:{C_ACCENT}; color:white; border:none; border-radius:4px; font-size:14px; font-weight:bold;")
        save_btn.clicked.connect(self._ed_save)
        ly.addWidget(save_btn)
        ly.addStretch()
        return w

    # ── Editor logic ──

    def _ed_add(self, action):
        name = self.ed_name.currentText().strip()
        if not name:
            self._log_append("请先输入任务名称", "WARN"); return
        if action == "press":
            k, ok = QInputDialog.getText(self, "按键", "按键名 (up/down/enter/f/space):")
            if ok and k.strip():
                self._editor_steps.append((k.strip(),0,0,0,0,"press"))
                self._ed_refresh()
            return
        if action == "wait":
            s, ok = QInputDialog.getDouble(self, "等待", "秒数:", 2.0, 0.1, 60, 1)
            if ok:
                self._editor_steps.append((f"{s:.1f}秒",0,0,0,0,"wait"))
                self._ed_refresh()
            return
        if action == "wait_until":
            self.setWindowState(Qt.WindowMinimized)
            dlg = RegionSelector()
            if dlg.exec() and dlg.region:
                x,y,w,h = dlg.region
                self._snap_tpl(name, f"wait_{len(self._editor_steps)+1}", x,y,w,h)
                timeout, ok = QInputDialog.getInt(self, "超时", "最大等待秒:", 60, 1, 600, 1)
                if ok:
                    self._editor_steps.append((f"wait_{len(self._editor_steps)+1}",x,y,w,h,"wait_until"))
                    self._ed_refresh()
            self.setWindowState(Qt.WindowNoState)
            return
        self.setWindowState(Qt.WindowMinimized)
        dlg = RegionSelector()
        if dlg.exec() and dlg.region:
            x,y,w,h = dlg.region
            tpl_name = f"step{len(self._editor_steps)+1}"
            self._snap_tpl(name, tpl_name, x,y,w,h)
            self._editor_steps.append((tpl_name,x,y,w,h,"click"))
            self._ed_refresh()
        self.setWindowState(Qt.WindowNoState)

    def _snap_tpl(self, task_name, tpl_name, x, y, w, h):
        import mss, cv2
        d = os.path.join(os.path.dirname(__file__), "examples", task_name, "templates")
        os.makedirs(d, exist_ok=True)
        with mss.mss() as sct:
            img = sct.grab({"left":x,"top":y,"width":w,"height":h})
            cv2.imwrite(os.path.join(d, f"{tpl_name}.png"),
                        cv2.cvtColor(np.array(img), cv2.COLOR_BGRA2BGR))

    def _ed_refresh(self):
        self.ed_list.clear()
        for i, s in enumerate(self._editor_steps):
            name, x, y, w, h, a = s
            cn = {"click":"点击","press":"按键","wait":"等待","wait_until":"等待出现"}.get(a,a)
            if a == "wait":
                self.ed_list.append(f'<span style="color:{C_WARN}">[{i+1}] 等待 {name}</span>')
            elif a == "press":
                self.ed_list.append(f'<span style="color:{C_WARN}">[{i+1}] 按 {name} 键</span>')
            elif a == "wait_until":
                self.ed_list.append(f'<span style="color:{C_WARN}">[{i+1}] {cn}</span>  "{name}"')
            else:
                self.ed_list.append(f'<span style="color:{C_ACCENT}">[{i+1}] {cn}</span>  "{name}" ({x},{y} {w}x{h})')

    def _ed_del(self):
        if self._editor_steps: self._editor_steps.pop(); self._ed_refresh()
    def _ed_clr(self):
        self._editor_steps.clear(); self._ed_refresh()

    def _ed_save(self):
        name = self.ed_name.currentText().strip()
        if not name: self._log_append("请输入任务名称", "WARN"); return
        if not self._editor_steps: self._log_append("请至少添加一个步骤", "WARN"); return
        d = os.path.join(os.path.dirname(__file__), "examples", name)
        os.makedirs(d, exist_ok=True)
        tasks, loop = {}, self.ed_loop.value()
        for i, s in enumerate(self._editor_steps):
            tpl, x, y, w, h, a = s
            sid = f"Step{i+1}"
            e = {"desc": f"步骤{i+1}: {a}"}
            if a == "wait":
                e["action"]="wait"; e["params"]={"seconds": float(tpl.replace("秒",""))}
            elif a == "press":
                e["action"]="press"; e["params"]={"key": tpl}
            elif a == "wait_until":
                e["action"]="wait_until"; e["params"]={"template":tpl,"threshold":0.8,"timeout":60}
            elif a == "click":
                e["action"]="click"; e["params"]={"template":tpl,"threshold":0.8}
            if i < len(self._editor_steps)-1:
                e["next"]=[f"Step{i+2}"]
            elif loop > 1:
                e["next"]=["Step1"]
            tasks[sid] = e
        if loop > 1 and "Step1" in tasks: tasks["Step1"]["maxTimes"] = loop
        with open(os.path.join(d, "task.json"), "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)
        self._log_append(f"已保存: {d}/task.json", "SUCCESS")
        self._scan()

    # ── Settings ──

    def _page_settings(self):
        w = QWidget()
        ly = QVBoxLayout(w)
        ly.setContentsMargins(24, 20, 24, 16)
        ly.setSpacing(16)
        t = QLabel("设置")
        t.setStyleSheet("font-size:18px; font-weight:bold; color:{C_TEXT};")
        ly.addWidget(t)
        ly.addWidget(QLabel("SmartRPA 配置项将在此处显示。"))
        ly.addStretch()
        return w

    def _page_about(self):
        w = QWidget()
        ly = QVBoxLayout(w)
        ly.setContentsMargins(24, 20, 24, 16)
        ly.setSpacing(12)
        t = QLabel("关于 SmartRPA")
        t.setStyleSheet("font-size:18px; font-weight:bold; color:{C_TEXT};")
        ly.addWidget(t)
        ly.addWidget(QLabel("SmartRPA - 视觉驱动的智能桌面自动化"))
        ly.addWidget(QLabel("版本 0.1.0"))
        ly.addWidget(QLabel("技术栈: Python + OpenCV + PySide6 + Tesseract OCR"))
        ly.addWidget(QLabel("灵感来源: MAA (MaaAssistantArknights)"))
        ly.addStretch()
        return w

    # ── Tasks page logic ──

    def _scan(self):
        self._task_map.clear()
        self.task_combo.clear()
        examples = os.path.join(os.path.dirname(__file__), "examples")
        if not os.path.isdir(examples): return
        for d in sorted(os.listdir(examples)):
            fp = os.path.join(examples, d, "task.json")
            if os.path.exists(fp):
                self._task_map[d] = fp
                self.task_combo.addItem(d)

    def _on_task_changed(self):
        path = self._task_map.get(self.task_combo.currentText())
        if not path: return
        # Clear old checkboxes
        for cb in self._checkboxes.values():
            self.task_list_layout.removeWidget(cb); cb.deleteLater()
        self._checkboxes.clear()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for name, task in data.items():
                if name.startswith("_"): continue
                cb = QCheckBox(task.get("desc", name))
                cb.setChecked(True)
                self._checkboxes[name] = cb
                self.task_list_layout.addWidget(cb)
        except Exception as e:
            self.task_combo.setToolTip(f"Error: {e}")
        tpl = os.path.join(os.path.dirname(path), "templates")
        if os.path.isdir(tpl): self.tpl_combo.setCurrentText(tpl)

    def _select_region(self):
        self.showMinimized()
        dlg = RegionSelector()
        if dlg.exec() and dlg.region:
            self._region = dlg.region
            x, y, w, h = self._region
            self.region_lbl.setText(f"{x}, {y}  {w}x{h}")
            self.region_lbl.setStyleSheet(f"color:{C_SUCCESS}; padding:4px 8px; background:{C_CARD}; border-radius:3px;")
        else:
            self.region_lbl.setText("已取消")
        self.showNormal()

    def _browse_tpl(self):
        d = QFileDialog.getExistingDirectory(self, "选择模板目录")
        if d: self.tpl_combo.setCurrentText(d)

    def _start(self):
        path = self._task_map.get(self.task_combo.currentText())
        if not path or not os.path.exists(path):
            self._log_append("未选择有效任务", "ERROR"); return
        self._running = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress.show()
        self.worker = TaskWorker(path, self.tpl_combo.currentText() or None,
                                 not self.popup_cb.isChecked(), self._region)
        self.worker.log.connect(self._log_append)
        self.worker.task_changed.connect(lambda d: self.task_hint.setText(d))
        self.worker.finished.connect(self._done)
        self.showMinimized()
        self.worker.start()

    def _stop(self):
        if self.worker: self.worker.stop()
        self.showNormal()
        self._log_append("已停止", "WARN")

    def _done(self, stats):
        self.showNormal()
        self._reset()
        self._log_append(f"完成: {stats['steps']}步, {stats['popups_handled']}弹窗, {stats['errors']}错误", "SUCCESS")

    def _reset(self):
        self._running = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress.hide()
        self.task_hint.setText("")

    def _log_append(self, msg, level="INFO"):
        cols = {"INFO": C_ACCENT, "SUCCESS": C_SUCCESS, "WARN": C_WARN, "ERROR": C_ERROR}
        c = cols.get(level, C_TEXT)
        self.log_widget.append(f'<span style="color:{c}">[{level[:4]}]</span> {msg}')


class QHLine(QFrame):
    def __init__(self):
        super().__init__()
        self.setFrameShape(QFrame.HLine)
        self.setStyleSheet(f"color:{C_BORDER};")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    w = SmartRPAGUI()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
