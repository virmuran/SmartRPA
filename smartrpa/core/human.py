"""人类行为模拟器 - 贝塞尔曲线鼠标轨迹 + 高斯随机延迟
参考: https://github.com/NC22/BezierCurveMouseMovements
v1.1 — pyautogui → pydirectinput (Python 3.13 兼容)
"""
import random
import math
import time
import ctypes
import numpy as np
import pydirectinput
from typing import Tuple, List

# 降低 pydirectinput 默认延迟
pydirectinput.PAUSE = 0.001


def _get_cursor_pos():
    """获取当前鼠标位置（跨平台兼容）"""
    pt = ctypes.wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return (pt.x, pt.y)


def _mouse_scroll(amount: int):
    """鼠标滚轮滚动，正值向上，负值向下"""
    ctypes.windll.user32.mouse_event(0x0800, 0, 0, amount, 0)  # MOUSEEVENTF_WHEEL


def _bezier_point(t: float, points: List[Tuple[float, float]]) -> Tuple[float, float]:
    """计算贝塞尔曲线上t位置的点（德卡斯特里奥算法）"""
    pts = [list(p) for p in points]
    n = len(pts) - 1
    for k in range(n):
        for i in range(n - k):
            pts[i][0] = (1 - t) * pts[i][0] + t * pts[i + 1][0]
            pts[i][1] = (1 - t) * pts[i][1] + t * pts[i + 1][1]
    return (pts[0][0], pts[0][1])


def generate_bezier_path(
    start: Tuple[int, int],
    end: Tuple[int, int],
    steps: int = None,
    curvature: float = None
) -> List[Tuple[int, int]]:
    """生成贝塞尔曲线的鼠标移动路径"""
    if steps is None:
        steps = random.randint(30, 60)
    if curvature is None:
        curvature = random.uniform(0.3, 0.7)

    mid_x = (start[0] + end[0]) / 2
    mid_y = (start[1] + end[1]) / 2
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    dist = math.hypot(dx, dy)

    offset = dist * curvature * 0.3
    ctrl1 = (
        start[0] + dx * 0.3 + random.uniform(-offset, offset),
        start[1] + dy * 0.3 + random.uniform(-offset, offset),
    )
    ctrl2 = (
        start[0] + dx * 0.7 + random.uniform(-offset, offset),
        start[1] + dy * 0.7 + random.uniform(-offset, offset),
    )

    control_points = [start, ctrl1, ctrl2, end]
    path = []
    for i in range(steps + 1):
        t = i / steps
        point = _bezier_point(t, control_points)
        path.append((int(point[0]), int(point[1])))
    return path


class HumanLike:
    """人类操作模拟器 — pydirectinput 版"""

    def __init__(self):
        self._last_click_time = 0
        self.fast_mode: bool = False

    def set_fast_mode(self, enabled: bool):
        """启用/禁用快速模式（游戏场景）"""
        self.fast_mode = enabled

    # ========== 鼠标操作 ==========

    def move_to(self, x: int, y: int, duration: float = None,
                 use_bezier: bool = True):
        """移动到目标位置，使用贝塞尔曲线模拟真人鼠标轨迹"""
        if self.fast_mode:
            ctypes.windll.user32.SetCursorPos(x, y)
            return

        if use_bezier:
            cur_x, cur_y = _get_cursor_pos()
            path = generate_bezier_path((cur_x, cur_y), (x, y))

            if duration is None:
                dist = math.hypot(x - cur_x, y - cur_y)
                duration = max(0.15, min(1.5, dist / random.uniform(300, 800)))

            step_delay = duration / len(path)
            for px, py in path:
                pydirectinput.moveTo(px, py)
                time.sleep(step_delay * random.uniform(0.9, 1.1))
        else:
            if duration is None:
                duration = random.uniform(0.1, 0.5)
            pydirectinput.moveTo(x, y)

    def click(self, x: int = None, y: int = None,
              button: str = "left", clicks: int = 1):
        """点击，自动加微小随机偏移"""
        if x is not None and y is not None:
            ox = random.randint(-3, 3)
            oy = random.randint(-3, 3)
            self.move_to(x + ox, y + oy)

        now = time.time()
        if now - self._last_click_time < 0.05:
            time.sleep(random.uniform(0.05, 0.15))
        self._last_click_time = now

        pos = _get_cursor_pos()
        pydirectinput.click(pos[0], pos[1], button=button, clicks=clicks)

    def drag(self, x1: int, y1: int, x2: int, y2: int,
             duration: float = None):
        """拖拽（模拟滑动）"""
        self.move_to(x1, y1)
        if duration is None:
            duration = random.uniform(0.3, 0.8)
        pydirectinput.mouseDown()
        self.move_to(x2, y2, duration=duration)
        pydirectinput.mouseUp()

    def scroll(self, direction: str = "down", amount: int = 300):
        """鼠标滚轮滚动（down=向上滚=positive）"""
        delta = amount if direction == "down" else -amount
        if self.fast_mode:
            _mouse_scroll(delta)
        else:
            steps = random.randint(2, 4)
            per_step = delta // steps
            for _ in range(steps):
                _mouse_scroll(per_step + random.randint(-20, 20))
                time.sleep(random.uniform(0.03, 0.08))

    # ========== 键盘操作 ==========

    def press_key(self, key: str):
        """按下按键，加随机力度延迟"""
        time.sleep(random.uniform(0.02, 0.08))
        pydirectinput.press(key)

    def type_text(self, text: str, wpm: int = None):
        """逐字输入文本，模拟真人打字速度"""
        if wpm is None:
            wpm = random.randint(60, 120)
        ms_per_char = 60000 / wpm

        for char in text:
            pydirectinput.write(char)
            delay = random.gauss(ms_per_char / 1000, ms_per_char / 5000)
            time.sleep(max(0.02, delay))

    # ========== 随机延迟 ==========

    @staticmethod
    def random_delay(mean: float = 0.5, std: float = 0.2):
        delay = random.gauss(mean, std)
        time.sleep(max(0.05, delay))

    @staticmethod
    def human_delay(action_type: str = "click", fast_mode: bool = False):
        """根据操作类型选择不同的延迟分布"""
        if fast_mode:
            time.sleep(random.uniform(0.005, 0.015))
            return

        delays = {
            "click":      (0.15, 0.08),
            "read":       (1.0, 0.5),
            "transition": (0.5, 0.25),
            "think":      (2.0, 1.0),
        }
        mean, std = delays.get(action_type, (0.3, 0.15))
        delay = abs(random.gauss(mean, std))
        time.sleep(max(0.05, min(5.0, delay)))
