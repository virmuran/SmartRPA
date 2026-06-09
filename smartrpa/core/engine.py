"""任务引擎 - 状态机驱动的任务执行器"""
import json
import time
import logging
from typing import Dict, List, Optional, Callable, Any
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
    """

    def __init__(self,
                 controller: Controller = None,
                 vision: Vision = None,
                 popup: PopupHandler = None):
        self.controller = controller or Controller()
        self.vision = vision or Vision()
        self.popup = popup

        self._tasks: Dict[str, dict] = {}        # 任务定义
        self._callbacks: Dict[str, Callable] = {} # 回调函数
        self._running = False
        self._stats = {"steps": 0, "errors": 0, "popups_handled": 0}

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
        # Only load dict entries (skip _comment, _game etc. which are strings)
        tasks = {k: v for k, v in data.items() if isinstance(v, dict)}
        self._tasks.update(tasks)
        logger.info(f"Loaded {len(tasks)} task definitions")

    def on(self, name: str, func: Callable):
        """注册回调函数"""
        self._callbacks[name] = func

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

            # ── 步骤1：截图 ──
            screenshot = self.controller.screenshot()

            # ── 步骤2：弹窗检测（每个步骤前） ──
            if self.popup and self.popup.enabled:
                if self.popup.handle(screenshot):
                    self._stats["popups_handled"] += 1
                    logger.info("[弹窗] 已处理")
                    screenshot = self.controller.screenshot()

            # ── 步骤3：执行当前任务 ──
            logger.info(f"[{step_count}] {current}: {task.get('desc', '')}")

            result = self._execute_step(screenshot, task)

            # ── 步骤4：根据结果跳转 ──
            if result:
                next_tasks = task.get("next", [])
            else:
                next_tasks = task.get("onErrorNext", task.get("next", []))
                self._stats["errors"] += 1
                logger.warning(f"  └ 失败，尝试: {next_tasks}")

            # 随机延迟（模拟真人）
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

    # ========== 步骤执行 ==========

    def _execute_step(self, screenshot, task: dict) -> bool:
        """执行单个任务步骤，返回是否成功"""
        action = task.get("action", "click")
        params = task.get("params", {})

        try:
            if action == "click":
                return self._do_click(screenshot, params)
            elif action == "press":
                return self._do_press(params)
            elif action == "type":
                return self._do_type(params)
            elif action == "wait":
                return self._do_wait(params)
            elif action == "wait_until":
                return self._do_wait_until(params)
            elif action == "swipe":
                return self._do_swipe(params)
            elif action == "callback":
                return self._do_callback(params)
            elif action == "find":
                return self._do_find(screenshot, params)
            elif action == "if":
                return self._do_if(screenshot, params)
            else:
                logger.error(f"未知动作: {action}")
                return False
        except Exception as e:
            logger.error(f"执行异常: {e}")
            return False

    def _do_click(self, screenshot, params: dict) -> bool:
        """点击操作 - 核心：通过模板匹配找到目标并点击"""
        template = params.get("template")
        threshold = params.get("threshold", 0.8)
        roi = params.get("roi")

        if template:
            result = self.vision.find(screenshot, template, threshold, roi)
            if result.found:
                self.controller.click(result.center[0], result.center[1])
                return True
            else:
                logger.warning(f"  └ 未找到: {template} (阈值={threshold})")
                return False

        # 没有template=直接点坐标
        x = params.get("x", 0)
        y = params.get("y", 0)
        self.controller.click(x, y)
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
        timeout = params.get("timeout", 60)  # 最大等待秒数
        interval = params.get("interval", 1)  # 检测间隔

        logger.info(f"等待出现: {template} (超时={timeout}s)")
        start = time.time()
        while time.time() - start < timeout:
            screenshot = self.controller.screenshot()
            # 先处理弹窗
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
        x1, y1 = params.get("from", (0, 0))
        x2, y2 = params.get("to", (0, 0))
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
            result = self.vision.find(screenshot, template, threshold)
            return result.found
        return False

    def _do_if(self, screenshot, params: dict) -> bool:
        """条件判断"""
        condition = params.get("condition", {})
        cond_type = condition.get("type", "find")

        if cond_type == "find":
            template = condition.get("template")
            if template:
                result = self.vision.find(screenshot, template,
                                          condition.get("threshold", 0.8))
                return result.found

        return False
