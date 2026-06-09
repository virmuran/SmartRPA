"""弹窗干扰处理 - 自动检测并关闭弹窗/广告"""
import time
import numpy as np
from typing import List, Tuple, Optional, Callable


class PopupHandler:
    """
    弹窗干扰处理器。

    设计思想：在执行每个任务步骤前，先扫描屏幕是否有弹窗。
    如果有，优先处理弹窗（关闭），然后再继续任务。

    这是SmartRPA对比传统连点器的核心优势之一。
    """

    def __init__(self, vision, controller):
        """
        Args:
            vision: Vision识别器实例
            controller: Controller设备控制实例
        """
        self.vision = vision
        self.controller = controller
        self._close_templates: List[str] = []  # "关闭"按钮模板列表
        self._ad_templates: List[str] = []     # 广告特征模板列表
        self._enabled = True
        self._max_attempts = 5                 # 最多尝试关闭几次

    def add_close_template(self, name: str):
        """注册一个"关闭"按钮的模板图片名"""
        self._close_templates.append(name)

    def add_ad_template(self, name: str):
        """注册一个广告特征模板图片名"""
        self._ad_templates.append(name)

    # ========== 干扰检测 ==========

    def detect(self, screenshot: np.ndarray) -> Optional[str]:
        """
        检测是否有弹窗/广告

        Returns:
            检测到的弹窗类型名称，或None
        """
        if not self._enabled:
            return None

        # 先检测广告特征（更快）
        for name in self._ad_templates:
            result = self.vision.find(screenshot, name, threshold=0.7)
            if result.found:
                return f"ad:{name}"

        # 再检测关闭按钮（说明有弹窗）
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
            # 找关闭按钮
            for name in self._close_templates:
                result = self.vision.find(screenshot, name, threshold=0.75)
                if result.found:
                    self.controller.click(result.center[0], result.center[1])
                    time.sleep(0.5)
                    break

            # 重新截图检查是否关闭成功
            time.sleep(0.3)
            screenshot = self.controller.screenshot()
            if self.detect(screenshot) is None:
                return True  # 关闭成功

            attempts += 1

        return False

    def wrap(self, action: Callable, screenshot: np.ndarray = None) -> bool:
        """
        包装一个操作：先处理弹窗，再执行操作

        Usage:
            handler.wrap(lambda: controller.click(x, y), screenshot)
        """
        # 先处理可能的弹窗
        if screenshot is not None:
            self.handle(screenshot)

        # 执行操作
        action()

        # 操作后可能触发新弹窗
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
