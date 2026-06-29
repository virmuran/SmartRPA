"""人类行为模拟器 - 贝塞尔曲线鼠标轨迹 + 高斯随机延迟
参考: https://github.com/NC22/BezierCurveMouseMovements
"""
import random
import math
import time
import numpy as np
from typing import Tuple, List


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
    """
    生成贝塞尔曲线的鼠标移动路径。

    Args:
        start: 起点 (x, y)
        end: 终点 (x, y)
        steps: 移动步数，None则随机(30-60)
        curvature: 曲率 0-1，None则随机

    Returns:
        路径点列表 [(x, y), ...]
    """
    if steps is None:
        steps = random.randint(30, 60)
    if curvature is None:
        curvature = random.uniform(0.3, 0.7)

    # 计算中间控制点（让路径有自然的弯曲）
    mid_x = (start[0] + end[0]) / 2
    mid_y = (start[1] + end[1]) / 2
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    dist = math.hypot(dx, dy)

    # 两个控制点，使路径呈S形（模仿手腕运动）
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

    # 生成路径
    path = []
    for i in range(steps + 1):
        t = i / steps
        point = _bezier_point(t, control_points)
        path.append((int(point[0]), int(point[1])))

    return path


class HumanLike:
    """人类操作模拟器"""

    def __init__(self, mouse_controller=None):
        """
        Args:
            mouse_controller: pyautogui 或 pynput.mouse.Controller
        """
        self.mouse = mouse_controller
        self._last_click_time = 0
        self.fast_mode: bool = False

    def set_fast_mode(self, enabled: bool):
        """启用/禁用快速模式（游戏场景）"""
        self.fast_mode = enabled

    # ========== 鼠标操作 ==========

    def move_to(self, x: int, y: int, duration: float = None,
                 use_bezier: bool = True):
        """
        移动到目标位置，使用贝塞尔曲线模拟真人鼠标轨迹

        Args:
            x, y: 目标坐标
            duration: 移动时长(秒)，None则根据距离自动计算
            use_bezier: 是否使用贝塞尔曲线
        """
        if self.mouse is None:
            import pyautogui
            self.mouse = pyautogui

        # 快速模式：瞬移，不画轨迹
        if self.fast_mode:
            try:
                import ctypes
                ctypes.windll.user32.SetCursorPos(x, y)
            except Exception:
                self.mouse.moveTo(x, y, duration=0)
            return

        if use_bezier:
            # 获取当前鼠标位置
            try:
                cur_x, cur_y = self.mouse.position()
            except Exception:
                cur_x, cur_y = (100, 100)

            path = generate_bezier_path((cur_x, cur_y), (x, y))

            if duration is None:
                # 真人移动速度约 300-800 px/s
                dist = math.hypot(x - cur_x, y - cur_y)
                duration = max(0.15, min(1.5, dist / random.uniform(300, 800)))

            step_delay = duration / len(path)
            for px, py in path:
                try:
                    self.mouse.moveTo(px, py, _pause=False)
                except Exception:
                    import pyautogui as pag
                    pag.moveTo(px, py, _pause=False)
                time.sleep(step_delay * random.uniform(0.9, 1.1))
        else:
            if duration is None:
                duration = random.uniform(0.1, 0.5)
            try:
                self.mouse.moveTo(x, y, duration=duration)
            except Exception:
                import pyautogui as pag
                pag.moveTo(x, y, duration=duration)

    def click(self, x: int = None, y: int = None,
              button: str = "left", clicks: int = 1):
        """点击，自动加微小随机偏移"""
        import pyautogui

        if x is not None and y is not None:
            # 在目标周围加入±3px的随机偏移（真人不会每次都点同一个像素）
            ox = random.randint(-3, 3)
            oy = random.randint(-3, 3)
            self.move_to(x + ox, y + oy)

        # 点击间隔
        now = time.time()
        if now - self._last_click_time < 0.05:
            time.sleep(random.uniform(0.05, 0.15))
        self._last_click_time = now

        pyautogui.click(button=button, clicks=clicks)

    def drag(self, x1: int, y1: int, x2: int, y2: int,
             duration: float = None):
        """拖拽（模拟滑动）"""
        self.move_to(x1, y1)
        import pyautogui
        if duration is None:
            duration = random.uniform(0.3, 0.8)
        pyautogui.drag(x2 - x1, y2 - y1, duration=duration)

    def scroll(self, direction: str = "down", amount: int = 300):
        """鼠标滚轮滚动（down向上滚为正像素，up向上滚为负像素）"""
        import pyautogui
        delta = amount if direction == "down" else -amount
        if self.fast_mode:
            pyautogui.scroll(delta)
        else:
            # 真人滚轮：分几次小步滚动
            steps = random.randint(2, 4)
            per_step = delta // steps
            for _ in range(steps):
                pyautogui.scroll(per_step + random.randint(-20, 20))
                time.sleep(random.uniform(0.03, 0.08))    # ========== 键盘操作 ==========

    def press_key(self, key: str):
        """按下按键，加随机力度延迟（真人不会精准按0.05秒）"""
        import pyautogui
        # 按键前随机犹豫
        time.sleep(random.uniform(0.02, 0.08))
        pyautogui.press(key)

    def type_text(self, text: str, wpm: int = None):
        """
        逐字输入文本，模拟真人打字速度

        Args:
            wpm: 打字速度(字/分钟)，None则随机60-120
        """
        if wpm is None:
            wpm = random.randint(60, 120)

        ms_per_char = 60000 / wpm  # 每个字符的毫秒数

        for char in text:
            import pyautogui
            pyautogui.write(char)
            # 字符间延迟符合高斯分布
            delay = random.gauss(ms_per_char / 1000, ms_per_char / 5000)
            time.sleep(max(0.02, delay))

    # ========== 随机延迟 ==========

    @staticmethod
    def random_delay(mean: float = 0.5, std: float = 0.2):
        """
        高斯分布随机延迟（比均匀分布更像真人）

        Args:
            mean: 平均延迟(秒)
            std: 标准差(秒)
        """
        delay = random.gauss(mean, std)
        time.sleep(max(0.05, delay))

    @staticmethod
    def human_delay(action_type: str = "click", fast_mode: bool = False):
        """
        根据操作类型选择不同的延迟分布

        - click: 0.1-0.3s（点击很快）
        - read: 0.5-2s（阅读/等待）
        - transition: 0.3-0.8s（界面切换）
        - think: 1-3s（决策时间）
        - fast: 所有类型 ≈ 10ms（游戏模式）
        """
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
