"""设备控制层 - 截图 + 键鼠操作"""
import time
import numpy as np
import mss
import cv2
from typing import Tuple, Optional, List
from screeninfo import get_monitors


class Monitor:
    """单个显示器信息"""
    def __init__(self, m):
        self.x = m.x
        self.y = m.y
        self.w = m.width
        self.h = m.height
        self.name = m.name or ""
        self.is_primary = m.is_primary

    def contains(self, px: int, py: int) -> bool:
        return self.x <= px < self.x + self.w and self.y <= py < self.y + self.h

    def __repr__(self):
        return f"Monitor({self.name} {'P' if self.is_primary else ''} {self.w}x{self.h} @ ({self.x},{self.y}))"


class Controller:
    """统一设备控制接口。支持截图缓存避免重复截屏。"""

    def __init__(self):
        self._sct = mss.mss()
        self._human = None  # 延迟初始化
        self._monitors: List[Monitor] = self._detect_monitors()

        # Screenshot cache
        self._cache_ss: Optional[np.ndarray] = None
        self._cache_valid: bool = False

    def _detect_monitors(self) -> List[Monitor]:
        """使用 screeninfo 检测所有显示器布局"""
        monitors = [Monitor(m) for m in get_monitors()]
        for mon in monitors:
            print(f"[Controller] {mon}")
        return monitors

    @property
    def monitors(self) -> List[Monitor]:
        return self._monitors

    @property
    def primary(self) -> Optional[Monitor]:
        for m in self._monitors:
            if m.is_primary:
                return m
        return self._monitors[0] if self._monitors else None

    @property
    def human(self):
        if self._human is None:
            from .human import HumanLike
            self._human = HumanLike()
        return self._human

    # ========== 截图 ==========

    def screenshot(self, region: Tuple[int, int, int, int] = None, use_cache: bool = True) -> np.ndarray:
        """
        截取屏幕区域（支持缓存避免重复截屏）。

        Args:
            region: (x, y, w, h)，None=全虚拟桌面（所有显示器拼接）
            use_cache: 是否使用缓存。通常为True，只有需要强制刷新时设为False。

        Returns:
            BGR格式numpy数组
        """
        if use_cache and not region and self._cache_valid and self._cache_ss is not None:
            return self._cache_ss

        if region:
            x, y, w, h = region
            monitor = {"left": x, "top": y, "width": w, "height": h}
        else:
            monitor = self._sct.monitors[0]

        img = self._sct.grab(monitor)
        result = np.array(img)
        if result.shape[2] == 4:
            result = result[:, :, :3]

        if not region:
            self._cache_ss = result.copy()
            self._cache_valid = True

        return result

    def invalidate_cache(self):
        """使截图缓存失效（在执行点击/按键等修改屏幕状态的操作后调用）。"""
        self._cache_valid = False

    @property
    def screen_size(self) -> Tuple[int, int]:
        m = self._sct.monitors[0]
        return (m["width"], m["height"])

    @property
    def capture_origin(self) -> Tuple[int, int]:
        """截图原点在虚拟桌面中的偏移 (left, top)。

        单屏时为 (0,0)；双屏副屏在左侧时可能为 (-1920, 0)。
        mss 截图的像素 (px,py) 对应虚拟桌面 (px+left, py+top)。
        """
        m = self._sct.monitors[0]
        return (m["left"], m["top"])

    # ========== 鼠标操作（委托给HumanLike） ==========

    def click(self, x: int, y: int, use_human: bool = True):
        """点击指定坐标"""
        if use_human:
            self.human.click(x, y)
        else:
            import pydirectinput
            pydirectinput.click(x, y)
        self.invalidate_cache()

    def move_to(self, x: int, y: int):
        """移动鼠标"""
        self.human.move_to(x, y)

    def drag(self, x1: int, y1: int, x2: int, y2: int):
        """拖拽"""
        self.human.drag(x1, y1, x2, y2)
        self.invalidate_cache()

    def scroll(self, direction: str = "down", amount: int = 300):
        """鼠标滚轮滚动"""
        self.human.scroll(direction, amount)
        self.invalidate_cache()

    # ========== 键盘操作 ==========

    def press_key(self, key: str):
        """按下按键"""
        self.human.press_key(key)
        self.invalidate_cache()

    def type_text(self, text: str):
        """输入文本"""
        self.human.type_text(text)
        self.invalidate_cache()

    # ========== 便捷方法 ==========

    def random_delay(self, action_type: str = "click"):
        """随机延迟（模拟真人操作间隔）"""
        self.human.human_delay(action_type, getattr(self.human, 'fast_mode', False))
