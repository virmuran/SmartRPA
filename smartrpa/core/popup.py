"""弹窗干扰处理 - 自动检测并关闭弹窗/广告"""
import time
import numpy as np
from typing import List, Optional, Callable


class PopupHandler:
    """
    弹窗干扰处理器。

    设计思想：在执行每个任务步骤前，先扫描屏幕是否有弹窗。
    如果有，优先处理弹窗（关闭），然后再继续任务。

    支持两种弹窗处理方式：
    1. 模板匹配：通过注册关闭按钮和广告特征模板来检测并关闭
    2. 内置通用策略：按 Escape、点击右上角关闭区等
    """

    def __init__(self, vision, controller):
        """
        Args:
            vision: Vision识别器实例
            controller: Controller设备控制实例
        """
        self.vision = vision
        self.controller = controller
        self._close_templates: List[str] = []
        self._ad_templates: List[str] = []
        self._enabled = True
        self._max_attempts = 5
        self._builtin_registered = False

    def add_close_template(self, name: str):
        """注册一个关闭按钮的模板图片名"""
        self._close_templates.append(name)

    def add_ad_template(self, name: str):
        """注册一个广告特征模板图片名"""
        self._ad_templates.append(name)

    def register_builtin_strategies(self):
        """
        注册内置通用弹窗处理策略（无需模板图片）。

        策略列表：
        - Escape 键：大多数对话框支持
        - 右上角关闭区：Windows 原生弹窗
        - 回车键：确认默认选项
        """
        self._builtin_registered = True

    # ========== 干扰检测 ==========

    def detect(self, screenshot: np.ndarray) -> Optional[str]:
        """
        检测是否有弹窗/广告

        Returns:
            检测到的弹窗类型名称，或None
        """
        if not self._enabled:
            return None

        for name in self._ad_templates:
            result = self.vision.find(screenshot, name, threshold=0.7)
            if result.found:
                return f"ad:{name}"

        for name in self._close_templates:
            result = self.vision.find(screenshot, name, threshold=0.75)
            if result.found:
                return f"popup:{name}"

        return None

    def handle(self, screenshot: np.ndarray) -> bool:
        """
        处理检测到的弹窗

        Returns:
            True=已处理，False=没有弹窗或处理失败
        """
        popup_type = self.detect(screenshot)
        if popup_type is None:
            return False

        attempts = 0
        while attempts < self._max_attempts:
            closed = self._try_close_by_template(screenshot)
            if not closed and self._builtin_registered:
                closed = self._try_close_by_strategy(screenshot)

            time.sleep(0.3)
            screenshot = self.controller.screenshot()
            if self.detect(screenshot) is None:
                return True

            attempts += 1

        return False

    def _try_close_by_template(self, screenshot: np.ndarray) -> bool:
        for name in self._close_templates:
            result = self.vision.find(screenshot, name, threshold=0.75)
            if result.found:
                self.controller.click(result.center[0], result.center[1])
                time.sleep(0.5)
                return True
        return False

    def _try_close_by_strategy(self, screenshot: np.ndarray) -> bool:
        """
        使用内置通用策略尝试关闭弹窗。

        按优先级尝试：
        1. Escape 键
        2. 右上角关闭区（窗口标题栏右边缘）
        3. 回车键（确认默认选项）
        4. 屏幕中心点击（处理全屏弹窗/广告）
        """
        sw, sh = self.controller.screen_size

        self.controller.press_key("esc")
        time.sleep(0.3)

        self.controller.click(sw - 15, 15)
        time.sleep(0.3)

        self.controller.press_key("enter")
        time.sleep(0.3)

        self.controller.click(sw // 2, sh // 2)
        time.sleep(0.3)

        return True

    def wrap(self, action: Callable, screenshot: np.ndarray = None) -> bool:
        """
        包装一个操作：先处理弹窗，再执行操作
        """
        if screenshot is not None:
            self.handle(screenshot)

        action()

        time.sleep(0.3)
        new_screenshot = self.controller.screenshot()
        self.handle(new_screenshot)

        return True

    @property
    def enabled(self):
        return self._enabled

    @enabled.setter
    def enabled(self, val: bool):
        self._enabled = val
