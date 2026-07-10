"""Action Recorder — record mouse/keyboard interactions → task JSON.

Extracted from gui.py. Full ActionRecorder(QThread) class with recording logic:
- Automatic 60x60 template capture on click
- Click node description: "点击 sN.png"
- pynput-based mouse/keyboard listening
"""
import os
import json
import time
import datetime
import numpy as np

from PySide6.QtCore import QThread, Signal

from smartrpa.ui.theme import data_dir


class ActionRecorder(QThread):
    """Record user mouse clicks and key presses to generate a task."""

    log = Signal(str, str)      # message, level
    finished = Signal(str)      # task_json_path

    def __init__(self, parent=None, stop_key: str = None):
        """Initialize the recorder.

        Args:
            parent: Parent QObject.
            stop_key: pynput key string to stop recording (default: "Key.f6").
        """
        super().__init__(parent)
        self._active = False
        self._events = []
        self._stop_key = stop_key or "Key.f6"  # default: F6

    def stop(self) -> None:
        """Signal the recorder to stop listening and build the task."""
        self._active = False

    def run(self) -> None:
        """Start recording thread: listen for mouse/keyboard events."""
        self._active = True
        self._events = []
        try:
            from pynput import mouse, keyboard
        except ImportError:
            self.log.emit("请安装 pynput: pip install pynput", "ERROR")
            return

        def on_click(x: int, y: int, button, pressed: bool):
            if not self._active:
                return False
            if not pressed:
                return
            if self._events and self._events[-1][1] == "click":
                last_x, last_y = self._events[-1][2][:2]
                if abs(x - last_x) < 3 and abs(y - last_y) < 3:
                    return
            self._events.append((time.time(), "click", (x, y)))
            self.log.emit(f"  📍 点击 ({x}, {y})", "INFO")

        def on_press(key):
            if not self._active:
                return False
            # Check stop key
            current = str(key) if hasattr(key, 'char') else str(key)
            if self._stop_key == current:
                self.log.emit("检测到停止快捷键，正在停止录制...", "INFO")
                self._active = False
                return False
            try:
                k = key.char
            except AttributeError:
                k = str(key).replace("Key.", "")
            self._events.append((time.time(), "press", k))
            self.log.emit(f"  ⌨ 按键 {k}", "INFO")

        m_listener = mouse.Listener(on_click=on_click)
        k_listener = keyboard.Listener(on_press=on_press)
        m_listener.start()
        k_listener.start()

        # Keep running until stopped
        while self._active:
            time.sleep(0.1)

        m_listener.stop()
        k_listener.stop()
        self._build_task()

    def _build_task(self) -> None:
        """Build task.json from recorded events."""
        if not self._events:
            self.log.emit("没有记录到任何操作", "WARN")
            return

        # Filter: merge clicks at same position, remove sub-second duplicates
        filtered = []
        for ev in self._events:
            if not filtered:
                filtered.append(ev)
                continue
            # Merge if same type and very close position (click) or same key (press)
            if ev[1] == "click" and filtered[-1][1] == "click":
                lx, ly = filtered[-1][2]
                cx, cy = ev[2]
                if abs(cx - lx) < 5 and abs(cy - ly) < 5:
                    continue  # skip duplicate at same spot
            filtered.append(ev)

        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:21]
        task_dir = data_dir(f"tasks/{now}")
        tpl_dir = os.path.join(task_dir, "templates")
        os.makedirs(tpl_dir, exist_ok=True)

        tasks, step_num = {}, 0
        prev_time = filtered[0][0]
        import mss as _m
        import cv2 as _c

        for ev in filtered:
            ts, etype, data = ev
            gap = ts - prev_time
            prev_time = ts

            # Note: gaps > 2s are intentionally not auto-inserted as steps.
            # Users should use wait_until (visual detection) in the flow editor
            # for robust timing instead of fixed delays.

            step_num += 1
            sid = f"Step{step_num}"

            if etype == "click":
                x, y = data
                # Capture area around click (60x60, focused on target)
                with _m.mss() as sct:
                    cx, cy = max(0, x - 30), max(0, y - 30)
                    region = {"left": cx, "top": cy, "width": 60, "height": 60}
                    img = sct.grab(region)
                    tpl_name = f"s{step_num}"
                    _c.imwrite(
                        os.path.join(tpl_dir, f"{tpl_name}.png"),
                        _c.cvtColor(np.array(img), _c.COLOR_BGRA2BGR)
                    )
                # Use lower threshold + multi-scale for recorded templates
                tasks[sid] = {
                    "desc": f"点击 {tpl_name}.png",
                    "action": "click",
                    "params": {
                        "template": tpl_name,
                        "threshold": 0.7,
                        "multi_scale": True,
                    },
                }
            elif etype == "press":
                tasks[sid] = {
                    "desc": f"按键 {data}",
                    "action": "press",
                    "params": {"key": data},
                }

            if step_num > 1:
                tasks[f"Step{step_num - 1}"]["next"] = [sid]

        # Write task JSON
        tasks["_meta"] = {
            "name": f"录制_{datetime.datetime.now().strftime('%m月%d日_%H%M')}",
            "created": now,
            "modified": datetime.datetime.now().isoformat(),
        }
        with open(os.path.join(task_dir, "task.json"), "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)

        self.log.emit(f"录制完成: {step_num}步 → {task_dir}/task.json", "SUCCESS")
        self.finished.emit(os.path.join(task_dir, "task.json"))
