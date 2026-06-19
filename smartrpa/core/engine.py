"""任务引擎 - 状态机驱动的任务执行器"""
import json
import time
import logging
from typing import Dict, List, Optional, Callable, Any, Tuple
from pathlib import Path

from .controller import Controller
from .vision import Vision, Found
from .popup import PopupHandler

logger = logging.getLogger(__name__)


class TaskEngine:
    """
    任务引擎 - SmartRPA核心。

    职责：
    1. 加载JSON任务配置
    2. 状态机驱动任务执行
    3. 每个步骤前检测并处理弹窗
    4. 真人化所有操作
    5. 窗口锚定（窗口移动后自动补偿偏移）
    6. 失败自动重试（可配次数和间隔）
    """

    def __init__(self,
                 controller: Controller = None,
                 vision: Vision = None,
                 popup: PopupHandler = None):
        self.controller = controller or Controller()
        self.vision = vision or Vision()
        self.popup = popup

        self._tasks: Dict[str, dict] = {}
        self._callbacks: Dict[str, Callable] = {}
        self._vars: Dict[str, any] = {}  # Runtime variables
        self._running = False
        self._stats = {"steps": 0, "errors": 0, "popups_handled": 0}

        # 窗口锚定
        self._anchor_offset: Tuple[int, int] = (0, 0)
        self._anchor_template: Optional[str] = None
        self._anchor_threshold: float = 0.8

    # ========== 配置加载 ==========

    def load(self, path: str):
        """加载JSON任务文件或目录"""
        p = Path(path)
        if p.is_dir():
            for f in sorted(p.glob("*.json")):
                self._load_file(f)
        else:
            self._load_file(p)

    def _load_file(self, filepath: Path):
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        tasks = {k: v for k, v in data.items()
                 if isinstance(v, dict) and not k.startswith('_')}
        self._tasks.update(tasks)
        logger.info(f"Loaded {len(tasks)} task definitions")

    def on(self, name: str, func: Callable):
        """注册回调函数"""
        self._callbacks[name] = func

    # ========== 窗口锚定 ==========

    def configure_anchor(self, template: str, threshold: float = 0.8):
        """
        配置窗口锚定模板。

        Args:
            template: 用于定位窗口的模板图片（如窗口标题栏）
            threshold: 匹配阈值
        """
        self._anchor_template = template
        self._anchor_threshold = threshold

    def _calibrate_anchor(self) -> Tuple[int, int]:
        """
        执行锚定校准，返回当前偏移量 (dx, dy)。

        如果上一次校准的偏移量与当前相差超过阈值，
        说明窗口移动了，重新计算偏移。

        Returns:
            (dx, dy) 当前窗口相对于初始位置的偏移
        """
        if not self._anchor_template:
            return (0, 0)

        screenshot = self.controller.screenshot()
        result = self.vision.find(screenshot, self._anchor_template,
                                  threshold=self._anchor_threshold)
        if result.found:
            # 假设锚定模板在参考截图中位于 (0, 0)
            return (result.x, result.y)

        logger.warning(f"锚定模板 '{self._anchor_template}' 未找到，偏移不生效")
        return (0, 0)

    def _apply_anchor_to_roi(self, roi: Optional[Tuple[int, int, int, int]]) -> Optional[Tuple[int, int, int, int]]:
        """
        将锚定偏移应用到 ROI 区域。

        Args:
            roi: 原始 ROI (x, y, w, h)

        Returns:
            偏移后的 ROI
        """
        if roi is None or self._anchor_offset == (0, 0):
            return roi
        dx, dy = self._anchor_offset
        return (roi[0] - dx, roi[1] - dy, roi[2], roi[3])

    # ========== 任务执行 ==========

    def run(self, entry: str, max_steps: int = 1000):
        """
        执行任务

        Args:
            entry: 入口任务名
            max_steps: 最大步数（防止死循环）
        """
        self._running = True
        current = entry
        step_count = 0

        # 首次校准锚定
        if self._anchor_template:
            self._anchor_offset = self._calibrate_anchor()
            if self._anchor_offset != (0, 0):
                logger.info(f"窗口锚定偏移: {self._anchor_offset}")

        logger.info(f"开始执行: {entry}")

        while self._running and step_count < max_steps:
            if current is None:
                logger.info("任务链结束")
                break

            task = self._tasks.get(current)
            if task is None:
                logger.error(f"任务 '{current}' 未定义")
                break

            step_count += 1
            self._stats["steps"] += 1

            # 定期重新校准锚定（每 10 步一次）
            if self._anchor_template and step_count % 10 == 0:
                self._anchor_offset = self._calibrate_anchor()

            # 截图
            screenshot = self.controller.screenshot()

            # 弹窗检测（每个步骤前）
            if self.popup and self.popup.enabled:
                if self.popup.handle(screenshot):
                    self._stats["popups_handled"] += 1
                    logger.info("[弹窗] 已处理")
                    screenshot = self.controller.screenshot()

            # 执行当前任务
            logger.info(f"[{step_count}] {current}: {task.get('desc', '')}")

            result = self._execute_step(screenshot, task)

            # 根据结果跳转
            if result:
                next_tasks = task.get("next", [])
            else:
                next_tasks = task.get("onErrorNext", task.get("next", []))
                self._stats["errors"] += 1
                logger.warning(f"  └ 失败，尝试: {next_tasks}")

            # 随机延迟
            delay_type = task.get("humanDelay", "transition")
            self.controller.random_delay(delay_type)

            # 子任务
            sub_tasks = task.get("sub", [])
            for sub in sub_tasks:
                sub_task = self._tasks.get(sub)
                if sub_task:
                    screenshot = self.controller.screenshot()
                    if self.popup:
                        self.popup.handle(screenshot)
                    self._execute_step(screenshot, sub_task)

            # 下一个任务
            current = next_tasks[0] if next_tasks else None

        logger.info(f"执行结束: {self._stats['steps']}步, "
                    f"{self._stats['errors']}次失败, "
                    f"{self._stats['popups_handled']}次弹窗处理")

    def stop(self):
        self._running = False

    # ========== 步骤执行（含重试机制） ==========

    def _execute_step(self, screenshot, task: dict) -> bool:
        """执行单个任务步骤，支持自动重试"""
        action = task.get("action", "click")
        params = task.get("params", {})

        # 应用锚定偏移到 params 中的 ROI
        if "roi" in params:
            params = dict(params)
            params["roi"] = self._apply_anchor_to_roi(params["roi"])

        # 读取重试配置
        retry_cfg = task.get("retry", {})
        retry_count = retry_cfg.get("count", 0) if isinstance(retry_cfg, dict) else 0
        retry_interval = retry_cfg.get("interval", 1.0) if isinstance(retry_cfg, dict) else 1.0

        max_attempts = retry_count + 1

        for attempt in range(max_attempts):
            try:
                if action == "click":
                    success = self._do_click(screenshot, params)
                elif action == "press":
                    success = self._do_press(params)
                elif action == "type":
                    success = self._do_type(params)
                elif action == "wait":
                    success = self._do_wait(params)
                elif action == "wait_until":
                    success = self._do_wait_until(params)
                elif action == "swipe":
                    success = self._do_swipe(params)
                elif action == "callback":
                    success = self._do_callback(params)
                elif action == "find":
                    success = self._do_find(screenshot, params)
                elif action == "find_color":
                    success = self._do_find_color(screenshot, params)
                elif action == "if":
                    success = self._do_if(screenshot, params)
                elif action == "exec":
                    success = self._do_exec(params)
                elif action == "move":
                    success = self._do_move(screenshot, params)
                elif action == "hotkey":
                    success = self._do_hotkey(params)
                elif action == "ocr":
                    success = self._do_ocr(screenshot, params)
                elif action == "find_text":
                    success = self._do_find_text(screenshot, params)
                elif action == "set_var":
                    success = self._do_set_var(screenshot, params)
                elif action == "log":
                    success = self._do_log(params)
                else:
                    logger.error(f"未知动作: {action}")
                    success = False

                if success:
                    return True

                # 失败且还有重试次数
                if attempt < max_attempts - 1:
                    logger.info(f"  └ 第{attempt+1}次失败，{retry_interval}s后重试 (共{retry_count}次)")
                    # 重试前重新截图
                    time.sleep(retry_interval)
                    screenshot = self.controller.screenshot()
                    # 重试前处理弹窗
                    if self.popup and self.popup.enabled:
                        self.popup.handle(screenshot)
                        screenshot = self.controller.screenshot()
                else:
                    logger.warning(f"  └ 已重试{retry_count}次，仍失败")
                    return False

            except Exception as e:
                logger.error(f"执行异常: {e}")
                if attempt < max_attempts - 1:
                    time.sleep(retry_interval)
                    screenshot = self.controller.screenshot()
                else:
                    return False

        return False

    def _do_click(self, screenshot, params: dict) -> bool:
        """点击操作 - 核心：通过模板匹配找到目标并点击"""
        template = params.get("template")
        threshold = params.get("threshold", 0.8)
        roi = params.get("roi")

        # 应用锚定偏移到坐标参数
        dx, dy = self._anchor_offset

        if template:
            use_multi_scale = params.get("multi_scale", True)
            use_multi_angle = params.get("multi_angle", False)
            result = self.vision.find(screenshot, template, threshold, roi,
                                      use_multi_scale, use_multi_angle)
            if result.found:
                cx, cy = result.center
                self.controller.click(cx - dx, cy - dy)
                # 点击后验证
                if params.get("verify"):
                    return self._verify_click(template, threshold, params["verify"])
                return True
            else:
                logger.warning(f"  └ 未找到: {template} (阈值={threshold})")
                return False

        x = params.get("x", 0) - dx
        y = params.get("y", 0) - dy
        self.controller.click(x, y)
        return True

    def _verify_click(self, template: str, threshold: float, cfg: dict) -> bool:
        """
        点击后验证：等待目标出现或消失。
        cfg:
          disappear: true   → 等待模板消失（如弹窗关闭）
          appear: "xxx"     → 等待 xxx 模板出现（如新弹窗）
          timeout: 2.0      → 最长等待（秒）
          retry: 3          → 最多检测次数
        """
        import time, math
        timeout = cfg.get("timeout", 2.0)
        retries = cfg.get("retry", 3)
        interval = timeout / max(retries, 1)

        if cfg.get("disappear"):
            # 等待模板消失
            logger.info(f"  └ 验证: 等待 {template} 消失")
            for i in range(retries):
                time.sleep(interval)
                ss = self.controller.screenshot()
                r = self.vision.find(ss, template, threshold)
                if not r.found:
                    logger.info(f"  └ 验证通过: {template} 已消失")
                    return True
            logger.warning(f"  └ 验证失败: {template} 未消失")
            return False

        elif cfg.get("appear"):
            appear_tpl = cfg["appear"]
            appear_th = cfg.get("appear_threshold", threshold)
            logger.info(f"  └ 验证: 等待 {appear_tpl} 出现")
            for i in range(retries):
                time.sleep(interval)
                ss = self.controller.screenshot()
                r = self.vision.find(ss, appear_tpl, appear_th)
                if r.found:
                    logger.info(f"  └ 验证通过: {appear_tpl} 已出现")
                    return True
            logger.warning(f"  └ 验证失败: {appear_tpl} 未出现")
            return False

        return True

    def _do_press(self, params: dict) -> bool:
        """按键操作"""
        key = params.get("key", "")
        if key:
            self.controller.press_key(key)
        return True

    def _do_type(self, params: dict) -> bool:
        """输入文本"""
        text = params.get("text", "")
        self.controller.type_text(text)
        return True

    def _do_wait(self, params: dict) -> bool:
        """等待"""
        seconds = params.get("seconds", 1)
        time.sleep(seconds)
        return True

    def _do_wait_until(self, params: dict) -> bool:
        """智能等待：轮询检测模板，出现后立即继续"""
        template = params.get("template", "")
        threshold = params.get("threshold", 0.8)
        timeout = params.get("timeout", 60)
        interval = params.get("interval", 1)

        logger.info(f"等待出现: {template} (超时={timeout}s)")
        start = time.time()
        while time.time() - start < timeout:
            screenshot = self.controller.screenshot()
            if self.popup:
                self.popup.handle(screenshot)
            result = self.vision.find(screenshot, template, threshold)
            if result.found:
                logger.info(f"  └ 已出现 ({time.time()-start:.1f}s)")
                return True
            time.sleep(interval)
        logger.warning(f"  └ 超时未出现: {template}")
        return False

    def _do_swipe(self, params: dict) -> bool:
        """滑动"""
        dx, dy = self._anchor_offset
        x1 = params.get("from", (0, 0))[0] - dx
        y1 = params.get("from", (0, 0))[1] - dy
        x2 = params.get("to", (0, 0))[0] - dx
        y2 = params.get("to", (0, 0))[1] - dy
        self.controller.drag(x1, y1, x2, y2)
        return True

    def _do_callback(self, params: dict) -> bool:
        """执行回调函数"""
        name = params.get("name", "")
        func = self._callbacks.get(name)
        if func:
            return func(self, params)
        logger.error(f"回调函数 '{name}' 未注册")
        return False

    def _do_find(self, screenshot, params: dict) -> bool:
        """仅识别（不操作），用于条件判断"""
        template = params.get("template")
        threshold = params.get("threshold", 0.8)
        if template:
            use_multi_scale = params.get("multi_scale", True)
            use_multi_angle = params.get("multi_angle", False)
            roi = params.get("roi")
            result = self.vision.find(screenshot, template, threshold, roi,
                                      use_multi_scale, use_multi_angle)
            return result.found
        return False

    def _do_find_color(self, screenshot, params: dict) -> bool:
        """通过颜色检测区域（无需模板图片）"""
        target = params.get("target")
        if not target or len(target) != 3:
            return False
        tolerance = params.get("tolerance", 40)
        min_pct = params.get("min_pct", 0.15)
        roi = params.get("roi")
        result = self.vision.find_color_region(
            screenshot, tuple(target), tolerance, min_pct, roi)
        return result.found

    def _do_if(self, screenshot, params: dict) -> bool:
        """
        条件判断引擎 - 支持多种条件类型。

        条件类型:
          - find:       模板匹配检测
          - find_text:  OCR 文字检测
          - find_color: 颜色区域检测
          - compare:    变量比较 (>, <, ==, !=, >=, <=)
          - exists:     检查变量是否存在且非空
        """
        condition = params.get("condition", {})
        cond_type = condition.get("type", "find")

        if cond_type == "find":
            template = condition.get("template")
            if template:
                result = self.vision.find(screenshot, template,
                                          condition.get("threshold", 0.8))
                return result.found

        elif cond_type == "find_text":
            keyword = condition.get("keyword", "")
            if keyword:
                roi = condition.get("roi")
                lang = condition.get("lang", "chi_sim+eng")
                result = self.vision.find_text(screenshot, keyword, roi, lang)
                return result.found

        elif cond_type == "find_color":
            target = condition.get("target")
            if target and len(target) == 3:
                tolerance = condition.get("tolerance", 40)
                min_pct = condition.get("min_pct", 0.15)
                roi = condition.get("roi")
                result = self.vision.find_color_region(
                    screenshot, tuple(target), tolerance, min_pct, roi)
                return result.found

        elif cond_type == "compare":
            var_name = condition.get("var", "")
            op = condition.get("op", "==")
            value = condition.get("value")
            actual = self._vars.get(var_name)
            if actual is None:
                return False
            try:
                if op == "==":  return actual == value
                if op == "!=":  return actual != value
                if op == ">":   return float(actual) > float(value)
                if op == "<":   return float(actual) < float(value)
                if op == ">=":  return float(actual) >= float(value)
                if op == "<=":  return float(actual) <= float(value)
            except (ValueError, TypeError):
                return False

        elif cond_type == "exists":
            var_name = condition.get("var", "")
            return var_name in self._vars and self._vars[var_name] is not None

        return False

    def _do_set_var(self, screenshot, params: dict) -> bool:
        """
        设置运行时变量。
        支持从不同来源取值：
          - value: 直接赋值
          - ocr:   从屏幕 OCR 识别结果赋值
          - count: 模板匹配计数（find_all 结果数）
        """
        var_name = params.get("name", "")
        if not var_name:
            return False

        source = params.get("from", "value")

        if source == "value":
            self._vars[var_name] = params.get("value")
            logger.info(f"  └ 变量 {var_name} = {self._vars[var_name]}")
            return True

        elif source == "ocr":
            roi = params.get("roi")
            lang = params.get("lang", "chi_sim+eng")
            text = self.vision.ocr(screenshot, roi, lang)
            self._vars[var_name] = text
            logger.info(f"  └ 变量 {var_name} (OCR) = {text[:80]}")
            return True

        elif source == "count":
            template = params.get("template", "")
            threshold = params.get("threshold", 0.8)
            results = self.vision.find_all(screenshot, template, threshold)
            self._vars[var_name] = len(results)
            logger.info(f"  └ 变量 {var_name} (计数) = {len(results)}")
            return True

        return False

    def _do_log(self, params: dict) -> bool:
        """输出自定义日志消息（用于调试）"""
        msg = params.get("msg", "")
        if msg:
            # Support variable interpolation
            for k, v in self._vars.items():
                msg = msg.replace(f"{{{k}}}", str(v))
            logger.info(f"[LOG] {msg}")
        return True

    def _do_exec(self, params: dict) -> bool:
        """执行终端命令（启动程序、打开链接等）"""
        cmd = params.get("cmd", "")
        if not cmd:
            return False
        import subprocess
        try:
            subprocess.Popen(cmd, shell=True)
            logger.info(f"  └ 已执行: {cmd}")
            return True
        except Exception as e:
            logger.error(f"执行命令失败: {e}")
            return False

    def _do_move(self, screenshot, params: dict) -> bool:
        """移动鼠标到模板位置（悬停触发，不点击）"""
        template = params.get("template")
        threshold = params.get("threshold", 0.8)
        if template:
            use_multi_scale = params.get("multi_scale", True)
            use_multi_angle = params.get("multi_angle", False)
            roi = params.get("roi")
            result = self.vision.find(screenshot, template, threshold, roi,
                                      use_multi_scale, use_multi_angle)
            if result.found:
                self.controller.move_to(result.center[0], result.center[1])
                logger.info(f"  └ 悬停: {template} ({result.center[0]},{result.center[1]})")
                return True
            logger.warning(f"  └ 未找到悬停目标: {template}")
            return False
        return False

    def _do_hotkey(self, params: dict) -> bool:
        """发送组合键（如 alt+left 浏览器后退）"""
        keys = params.get("keys", [])
        if not keys:
            return False
        import pyautogui
        try:
            pyautogui.hotkey(*keys)
            logger.info(f"  └ 组合键: {'+'.join(keys)}")
            return True
        except Exception as e:
            logger.error(f"组合键失败: {e}")
            return False

    def _do_ocr(self, screenshot, params: dict) -> bool:
        """OCR 识别：读取屏幕文字并记录到日志"""
        roi = params.get("roi")
        lang = params.get("lang", "chi_sim+eng")
        text = self.vision.ocr(screenshot, roi, lang)
        if text:
            logger.info(f"  └ OCR识别: {text[:100]}")
            return True
        logger.warning("  └ OCR未识别到文字")
        return False

    def _do_find_text(self, screenshot, params: dict) -> bool:
        """查找屏幕文字：检测指定文字是否出现在屏幕上"""
        keyword = params.get("keyword", "")
        if not keyword:
            return False
        roi = params.get("roi")
        lang = params.get("lang", "chi_sim+eng")
        result = self.vision.find_text(screenshot, keyword, roi, lang)
        if result.found:
            logger.info(f"  └ 找到文字 '{keyword}' 在 ({result.x},{result.y})")
            return True
        logger.info(f"  └ 未找到文字 '{keyword}'")
        return False
