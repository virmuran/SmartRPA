"""Task Worker — background thread for executing SmartRPA tasks.

Extracted from gui.py. Full TaskWorker(QThread) class with:
- BT format detection
- Behavior Tree / Classic State Machine dispatch
- Popup handling, fast mode, region anchoring
"""
import os
import json

from PySide6.QtCore import QThread, Signal

from smartrpa import Controller, Vision, TaskEngine, BTEngine, PopupHandler


class TaskWorker(QThread):
    """Background worker that executes a task.json or task.bt.json file."""

    log = Signal(str, str)       # message, level
    finished = Signal(dict)      # stats dict
    step = Signal(str)           # current step description

    def __init__(self, task_file: str, tpl_dir: str = None,
                 no_popup: bool = False, region: tuple = None,
                 fast_mode: bool = False):
        """Initialize the task worker.

        Args:
            task_file: Path to task.json or task.bt.json.
            tpl_dir: Override template directory.
            no_popup: Disable popup handling.
            region: (x, y, w, h) screen region to operate within.
            fast_mode: Skip human-like delays.
        """
        super().__init__()
        self.task_file = task_file
        self.tpl_dir = tpl_dir
        self.no_popup = no_popup
        self.region = region
        self.fast_mode = fast_mode
        self._active = True
        self._engine = None  # BTEngine or TaskEngine

    def _is_bt_format(self, path: str) -> bool:
        """Detect if a task file uses the Behavior Tree format."""
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return "root" in data
        except Exception:
            return False

    def run(self) -> None:
        """Execute the task in a background thread."""
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
                self.log.emit(
                    f"BT任务: {os.path.basename(self.task_file)}", "INFO"
                )
                self._engine = engine
                engine.run()
                s = engine._ctx.stats
                self.log.emit(
                    f"完成: {s['steps']}步 {s['popups_handled']}弹窗 {s['errors']}错误",
                    "SUCCESS",
                )
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
                self.log.emit(
                    f"任务: {os.path.basename(self.task_file)}", "INFO"
                )
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
                self.log.emit(
                    f"完成: {s['steps']}步 {s['popups_handled']}弹窗 {s['errors']}错误",
                    "SUCCESS",
                )
                self.finished.emit(s)

        except Exception as e:
            import traceback
            self.log.emit(str(e), "ERROR")
            self.log.emit(traceback.format_exc(), "ERROR")

    def stop(self) -> None:
        """Request the task engine to stop at the next safe point."""
        self._active = False
        if self._engine:
            self._engine.stop()
