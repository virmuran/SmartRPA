"""设备控制层 - 截图 + 键鼠操作"""
import time
import numpy as np
import mss
import cv2
from typing import Tuple, Optional


class Controller:
    """统一设备控制接口"""

    def __init__(self):
        self._sct = mss.mss()
        self._human = None  # 延迟初始化

    @property
    def human(self):
        if self._human is None:
            from .human import HumanLike
            self._human = HumanLike()
        return self._human

    # ========== 截图 ==========

    def screenshot(self, region: Tuple[int, int, int, int] = None) -> np.ndarray:
        """
        截取屏幕区域

        Args:
            region: (x, y, w, h)，None=全屏

        Returns:
            BGR格式numpy数组
        """
        if region:
            x, y, w, h = region
            monitor = {"left": x, "top": y, "width": w, "height": h}
        else:
            monitor = self._sct.monitors[1]

        img = self._sct.grab(monitor)
        result = np.array(img)
        if result.shape[2] == 4:
            result = result[:, :, :3]  # BGRA → BGR
        return result

    @property
    def screen_size(self) -> Tuple[int, int]:
        m = self._sct.monitors[1]
        return (m["width"], m["height"])

    # ========== 鼠标操作（委托给HumanLike） ==========

    def click(self, x: int, y: int, use_human: bool = True):
        """点击指定坐标"""
        if use_human:
            self.human.click(x, y)
        else:
            import pyautogui
            pyautogui.click(x, y)

    def move_to(self, x: int, y: int):
        """移动鼠标"""
        self.human.move_to(x, y)

    def drag(self, x1: int, y1: int, x2: int, y2: int):
        """拖拽"""
        self.human.drag(x1, y1, x2, y2)

    # ========== 键盘操作 ==========

    def press_key(self, key: str):
        """按下按键"""
        self.human.press_key(key)

    def type_text(self, text: str):
        """输入文本"""
        self.human.type_text(text)

    # ========== 便捷方法 ==========

    def random_delay(self, action_type: str = "click"):
        """随机延迟（模拟真人操作间隔）"""
        self.human.human_delay(action_type, getattr(self.human, 'fast_mode', False))
