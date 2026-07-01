"""Behavior Tree Engine for SmartRPA.

Node types:
  - Sequence:    run children in order, fail on first failure
  - Selector:    run children in order, succeed on first success (fallback)
  - Retry:       retry child N times on failure
  - Timeout:     fail if child takes too long
  - Inverter:    flip success/failure
  - Parallel:    run all children, succeed if M+ succeed
  - Action:      RPA operation (click, wait, find, etc.)
  - Condition:   check (find template, find text, compare var, etc.)

Each node returns Status.SUCCESS, Status.FAILURE, or Status.RUNNING.
The tree is serialized as JSON with a tree structure:

{
  "_meta": {"name": "...", "window": "*..."},
  "root": {
    "type": "sequence",
    "children": [
      {"type": "exec", "cmd": "start msedge..."},
      {"type": "click", "template": "btn", "retry": 3},
      ...
    ]
  }
}

Backward compatibility: old flat JSON
{"TaskA": {"action":"click", "next":["TaskB"]}, ...}
is converted to a Sequence node automatically.
"""

import json
import time
import logging
import threading
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Tuple, Union

logger = logging.getLogger(__name__)


class Status(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    RUNNING = "running"


# ---------------------------------------------------------------------------
# Action context -- holds all the infrastructure a leaf node needs
# ---------------------------------------------------------------------------

@dataclass
class ActionContext:
    """Shared state passed to every node tick."""
    controller: Any = None          # Controller instance
    vision: Any = None             # Vision instance
    popup: Any = None              # PopupHandler instance
    callbacks: Dict[str, Callable] = field(default_factory=dict)
    vars: Dict[str, Any] = field(default_factory=dict)
    stats: Dict[str, int] = field(default_factory=lambda: {
        "steps": 0, "errors": 0, "popups_handled": 0
    })
    anchor_offset: Tuple[int, int] = (0, 0)
    window_title: Optional[str] = None
    human_delay: str = "transition"

    # Current screenshot (updated each tick cycle)
    screenshot: Any = None


# ---------------------------------------------------------------------------
# Base node
# ---------------------------------------------------------------------------

class BTNode:
    """Abstract behavior tree node."""

    def __init__(self, name: str = ""):
        self.name = name
        self.parent: Optional["BTNode"] = None

    def tick(self, ctx: ActionContext) -> Status:
        """Execute one tick. Override in subclasses."""
        raise NotImplementedError

    def reset(self):
        """Reset internal state (called before re-run)."""
        pass

    def to_dict(self) -> dict:
        """Serialize to JSON-serializable dict."""
        raise NotImplementedError

    @staticmethod
    def from_dict(d: dict) -> "BTNode":
        """Deserialize from dict."""
        node_type = d.get("type", "action")
        name = d.get("name", d.get("desc", ""))
        params = d.get("params", {})

        if node_type == "sequence":
            children = [BTNode.from_dict(c) for c in d.get("children", [])]
            return SequenceNode(name, children)

        elif node_type == "selector":
            children = [BTNode.from_dict(c) for c in d.get("children", [])]
            return SelectorNode(name, children)

        elif node_type == "retry":
            count = d.get("count", d.get("retry_count", 3))
            interval = d.get("interval", 1.0)
            child_d = d.get("child")
            child = BTNode.from_dict(child_d) if child_d else None
            return RetryNode(name, count, interval, child)

        elif node_type == "timeout":
            seconds = d.get("seconds", d.get("timeout", 30))
            child_d = d.get("child")
            child = BTNode.from_dict(child_d) if child_d else None
            return TimeoutNode(name, seconds, child)

        elif node_type == "inverter":
            child_d = d.get("child")
            child = BTNode.from_dict(child_d) if child_d else None
            return InverterNode(name, child)

        elif node_type == "parallel":
            policy = d.get("policy", "all")
            children = [BTNode.from_dict(c) for c in d.get("children", [])]
            return ParallelNode(name, policy, children)

        elif node_type == "repeat":
            max_iter = d.get("max_iterations", 1000)
            child_d = d.get("child")
            child = BTNode.from_dict(child_d) if child_d else None
            return RepeatNode(name, child, max_iter)

        else:
            # Leaf: Action or Condition
            action = d.get("action", node_type)
            if action in ("if", "find", "find_text", "find_color", "compare", "exists"):
                return ConditionNode(name, d)
            return ActionNode(name, d)

    def __repr__(self):
        return f"{self.__class__.__name__}({self.name!r})"


# ---------------------------------------------------------------------------
# Composite nodes
# ---------------------------------------------------------------------------

class SequenceNode(BTNode):
    """Run children in order. Fail on first failure, succeed when all succeed."""

    def __init__(self, name: str = "", children: List[BTNode] = None):
        super().__init__(name)
        self.children = children or []
        for c in self.children:
            c.parent = self
        self._index = 0

    def reset(self):
        self._index = 0
        for c in self.children:
            c.reset()

    def tick(self, ctx: ActionContext) -> Status:
        while self._index < len(self.children):
            child = self.children[self._index]
            status = child.tick(ctx)
            if status != Status.SUCCESS:
                return status  # FAILURE or RUNNING
            self._index += 1
        return Status.SUCCESS

    def to_dict(self) -> dict:
        return {
            "type": "sequence",
            "name": self.name,
            "children": [c.to_dict() for c in self.children],
        }


class SelectorNode(BTNode):
    """Try children in order. Succeed on first success, fail when all fail."""

    def __init__(self, name: str = "", children: List[BTNode] = None):
        super().__init__(name)
        self.children = children or []
        for c in self.children:
            c.parent = self
        self._index = 0

    def reset(self):
        self._index = 0
        for c in self.children:
            c.reset()

    def tick(self, ctx: ActionContext) -> Status:
        while self._index < len(self.children):
            child = self.children[self._index]
            status = child.tick(ctx)
            if status != Status.FAILURE:
                return status  # SUCCESS or RUNNING
            self._index += 1
        return Status.FAILURE

    def to_dict(self) -> dict:
        return {
            "type": "selector",
            "name": self.name,
            "children": [c.to_dict() for c in self.children],
        }


class RetryNode(BTNode):
    """Retry child N times on failure."""

    def __init__(self, name: str = "", count: int = 3, interval: float = 1.0,
                 child: BTNode = None):
        super().__init__(name)
        self.count = count
        self.interval = interval
        self.child = child
        if child:
            child.parent = self
        self._attempt = 0

    def reset(self):
        self._attempt = 0
        if self.child:
            self.child.reset()

    def tick(self, ctx: ActionContext) -> Status:
        if not self.child:
            return Status.FAILURE

        while self._attempt < self.count:
            status = self.child.tick(ctx)
            if status == Status.SUCCESS:
                return Status.SUCCESS
            if status == Status.RUNNING:
                return Status.RUNNING

            # FAILURE -- retry
            self._attempt += 1
            if self._attempt < self.count:
                logger.info(f"  [重试] {self.name or self.child.name}: "
                           f"第{self._attempt}次失败, {self.interval}s后重试 (共{self.count}次)")
                time.sleep(self.interval)
                # Refresh screenshot after sleep
                if ctx.controller:
                    ctx.screenshot = ctx.controller.screenshot()
                if ctx.popup and ctx.popup.enabled:
                    ctx.popup.handle(ctx.screenshot)
                    ctx.stats["popups_handled"] += 1
                self.child.reset()

        return Status.FAILURE

    def to_dict(self) -> dict:
        return {
            "type": "retry",
            "name": self.name,
            "count": self.count,
            "interval": self.interval,
            "child": self.child.to_dict() if self.child else None,
        }


class TimeoutNode(BTNode):
    """Fail if child takes longer than `seconds`."""

    def __init__(self, name: str = "", seconds: float = 30, child: BTNode = None):
        super().__init__(name)
        self.seconds = seconds
        self.child = child
        if child:
            child.parent = self
        self._start_time: Optional[float] = None

    def reset(self):
        self._start_time = None
        if self.child:
            self.child.reset()

    def tick(self, ctx: ActionContext) -> Status:
        if not self.child:
            return Status.FAILURE

        if self._start_time is None:
            self._start_time = time.time()

        # Tick the child (may block for synchronous actions like 'wait')
        status = self.child.tick(ctx)

        # Check elapsed AFTER child returns (catches synchronous long operations)
        elapsed = time.time() - self._start_time
        if elapsed > self.seconds:
            logger.warning(f"  [超时] {self.name or self.child.name}: "
                          f"{elapsed:.1f}s > {self.seconds}s")
            return Status.FAILURE

        return status

    def to_dict(self) -> dict:
        return {
            "type": "timeout",
            "name": self.name,
            "seconds": self.seconds,
            "child": self.child.to_dict() if self.child else None,
        }


class RepeatNode(BTNode):
    """Repeat child until it fails. SUCCESS restarts, FAILURE propagates up.

    This is the BT equivalent of a 'while success' loop — perfect for
    RPA patterns like "keep trying to find and process items until none left".
    """

    def __init__(self, name: str = "", child: BTNode = None,
                 max_iterations: int = 1000):
        super().__init__(name)
        self.child = child
        if child:
            child.parent = self
        self.max_iterations = max_iterations
        self._iteration = 0

    def reset(self):
        self._iteration = 0
        if self.child:
            self.child.reset()

    def tick(self, ctx: ActionContext) -> Status:
        if not self.child:
            return Status.FAILURE

        while self._iteration < self.max_iterations:
            status = self.child.tick(ctx)
            if status == Status.FAILURE:
                return Status.FAILURE  # child failed -> stop repeating
            if status == Status.RUNNING:
                return Status.RUNNING
            # SUCCESS -> reset child and loop again
            self._iteration += 1
            self.child.reset()

        logger.warning(f"  [Repeat] max iterations ({self.max_iterations}) reached")
        return Status.SUCCESS

    def to_dict(self) -> dict:
        return {
            "type": "repeat",
            "name": self.name,
            "max_iterations": self.max_iterations,
            "child": self.child.to_dict() if self.child else None,
        }


class InverterNode(BTNode):
    """Flip child's result: SUCCESS -> FAILURE, FAILURE -> SUCCESS."""

    def __init__(self, name: str = "", child: BTNode = None):
        super().__init__(name)
        self.child = child
        if child:
            child.parent = self

    def reset(self):
        if self.child:
            self.child.reset()

    def tick(self, ctx: ActionContext) -> Status:
        if not self.child:
            return Status.FAILURE
        status = self.child.tick(ctx)
        if status == Status.SUCCESS:
            return Status.FAILURE
        if status == Status.FAILURE:
            return Status.SUCCESS
        return status  # RUNNING unchanged

    def to_dict(self) -> dict:
        return {
            "type": "inverter",
            "name": self.name,
            "child": self.child.to_dict() if self.child else None,
        }


class ParallelNode(BTNode):
    """Run all children. Policy: 'all' (all must succeed) or 'any' (one success enough)."""

    def __init__(self, name: str = "", policy: str = "all",
                 children: List[BTNode] = None):
        super().__init__(name)
        self.policy = policy  # "all" or "any"
        self.children = children or []
        for c in self.children:
            c.parent = self

    def reset(self):
        for c in self.children:
            c.reset()

    def tick(self, ctx: ActionContext) -> Status:
        successes = 0
        failures = 0
        for child in self.children:
            status = child.tick(ctx)
            if status == Status.SUCCESS:
                successes += 1
            elif status == Status.FAILURE:
                failures += 1
            else:
                return Status.RUNNING

        if self.policy == "any":
            return Status.SUCCESS if successes > 0 else Status.FAILURE
        else:  # "all"
            return Status.SUCCESS if failures == 0 else Status.FAILURE

    def to_dict(self) -> dict:
        return {
            "type": "parallel",
            "name": self.name,
            "policy": self.policy,
            "children": [c.to_dict() for c in self.children],
        }


# ---------------------------------------------------------------------------
# Leaf nodes: Action and Condition
# ---------------------------------------------------------------------------

class ActionNode(BTNode):
    """Execute an RPA action (click, wait, type, hotkey, exec, move, ocr, etc.)."""

    ACTION_DISPATCH = None  # set by BTEngine

    def __init__(self, name: str = "", config: dict = None):
        super().__init__(name)
        self.config = config or {}
        self.action = self.config.get("action",
                                      self.config.get("type", "click"))
        self.params = self.config.get("params", self.config)

    def tick(self, ctx: ActionContext) -> Status:
        ctx.stats["steps"] += 1
        desc = self.name or self.params.get("desc", self.config.get("desc", ""))
        logger.info(f"  [{self.action}] {desc}")

        # Retry logic (inline in ActionNode)
        retry_count = self.config.get("retry",
                      self.params.get("retry", 0))
        if isinstance(retry_count, dict):
            retry_count = retry_count.get("count", 0)
        retry_interval = 1.0
        if isinstance(self.config.get("retry"), dict):
            retry_interval = self.config["retry"].get("interval", 1.0)

        for attempt in range(retry_count + 1):
            try:
                success = ActionNode._execute(ctx, self.action, self.params)
                if success:
                    return Status.SUCCESS
                if attempt < retry_count:
                    logger.info(f"    retry {attempt+1}/{retry_count}")
                    time.sleep(retry_interval)
                    if ctx.controller:
                        ctx.screenshot = ctx.controller.screenshot()
                    if ctx.popup and ctx.popup.enabled:
                        ctx.popup.handle(ctx.screenshot)
            except Exception as e:
                logger.error(f"    exception: {e}")
                if attempt >= retry_count:
                    ctx.stats["errors"] += 1
                    return Status.FAILURE
                time.sleep(retry_interval)

        ctx.stats["errors"] += 1
        return Status.FAILURE

    @staticmethod
    def _execute(ctx: ActionContext, action: str, params: dict) -> bool:
        """Dispatch to the appropriate _do_xxx using the context."""
        # Delegate to the engine's dispatch function
        if ActionNode.ACTION_DISPATCH:
            return ActionNode.ACTION_DISPATCH(ctx, action, params)

        # Fallback inline dispatch
        ctrl = ctx.controller
        vis = ctx.vision
        ss = ctx.screenshot

        dx, dy = ctx.anchor_offset
        sx, sy = ctrl.capture_origin if ctrl else (0, 0)

        if action == "click":
            return _action_click(ctx, params, dx, dy, sx, sy)

        elif action == "move":
            return _action_move(ctx, params, dx, dy, sx, sy)

        elif action == "press":
            key = params.get("key", "")
            if key and ctrl:
                ctrl.press_key(key)
            return True

        elif action == "type":
            text = params.get("text", "")
            if text and ctrl:
                ctrl.type_text(text)
            return True

        elif action == "wait":
            time.sleep(params.get("seconds", 1))
            return True

        elif action == "wait_until":
            return _action_wait_until(ctx, params)

        elif action == "swipe":
            x1 = params.get("from", (0, 0))[0] + sx - dx
            y1 = params.get("from", (0, 0))[1] + sy - dy
            x2 = params.get("to", (0, 0))[0] + sx - dx
            y2 = params.get("to", (0, 0))[1] + sy - dy
            if ctrl:
                ctrl.drag(x1, y1, x2, y2)
            return True

        elif action == "callback":
            name = params.get("name", "")
            func = ctx.callbacks.get(name)
            if func:
                return func(ctx, params)
            logger.error(f"callback '{name}' not registered")
            return False

        elif action == "find":
            return _action_find(ctx, params)

        elif action == "find_color":
            return _action_find_color(ctx, params)

        elif action == "if":
            return _action_if(ctx, params)

        elif action == "exec":
            return _action_exec(params)

        elif action == "hotkey":
            return _action_hotkey(params)

        elif action == "ocr":
            return _action_ocr(ctx, params)

        elif action == "find_text":
            return _action_find_text(ctx, params)

        elif action == "set_var":
            return _action_set_var(ctx, params)

        elif action == "log":
            msg = params.get("msg", "")
            for k, v in ctx.vars.items():
                msg = msg.replace(f"{{{k}}}", str(v))
            logger.info(f"[LOG] {msg}")
            return True

        else:
            logger.error(f"unknown action: {action}")
            return False

    def to_dict(self) -> dict:
        d = {"type": self.action, "name": self.name}
        # Merge config fields (skip 'type', 'name', 'retry' -- retry is ActionNode's own)
        for k, v in self.config.items():
            if k not in ("type", "name", "action", "retry"):
                d[k] = v
        for k, v in self.params.items():
            if k not in ("action", "retry"):
                d[k] = v
        if self.config.get("retry"):
            d["retry"] = self.config["retry"]
        if self.params.get("retry"):
            d["retry"] = self.params["retry"]
        return d


class ConditionNode(BTNode):
    """Check a condition. Returns SUCCESS if true, FAILURE if false."""

    def __init__(self, name: str = "", config: dict = None):
        super().__init__(name)
        self.config = config or {}
        self.action = self.config.get("action", "if")
        self.params = self.config.get("params", self.config)

    def tick(self, ctx: ActionContext) -> Status:
        ctx.stats["steps"] += 1
        desc = self.name or self.params.get("desc", "")
        logger.info(f"  [cond] {desc}")

        cond_type = self.params.get("condition", self.params)
        if isinstance(cond_type, dict):
            cond_type = cond_type.get("type", "find")

        action_map = {
            "if": "if",
            "find": "if",
            "find_text": "if",
            "find_color": "if",
            "compare": "if",
            "exists": "if",
        }

        mapped_action = action_map.get(self.action, "if")
        try:
            success = ActionNode._execute(ctx, mapped_action, self.params)
        except Exception as e:
            logger.error(f"    condition exception: {e}")
            success = False

        return Status.SUCCESS if success else Status.FAILURE

    def to_dict(self) -> dict:
        d = {"type": "condition", "name": self.name, "action": self.action}
        d.update(self.config)
        return d


# ---------------------------------------------------------------------------
# Action implementations (standalone; no engine dependency)
# ---------------------------------------------------------------------------

def _anchor_xy(params, dx, dy, sx, sy):
    """Get absolute screen coordinates adjusted for anchor offset."""
    x = params.get("x", 0) + sx - dx
    y = params.get("y", 0) + sy - dy
    return x, y


def _action_click(ctx, params, dx, dy, sx, sy) -> bool:
    template = params.get("template")
    threshold = params.get("threshold", 0.8)
    roi = params.get("roi")

    if template and ctx.vision:
        result = ctx.vision.find(
            ctx.screenshot, template, threshold, roi,
            params.get("multi_scale", True),
            params.get("multi_angle", False),
        )
        if result.found:
            cx, cy = result.center
            ctx.controller.click(cx + sx - dx, cy + sy - dy)
            # Verify after click
            verify = params.get("verify")
            if verify:
                return _verify_click(ctx, template, threshold, verify)
            return True

        # Scroll search fallback
        scroll_cfg = params.get("scroll_search")
        if scroll_cfg:
            return _scroll_and_retry(ctx, template, threshold, roi,
                                     scroll_cfg, dx, dy,
                                     params.get("verify"))

        logger.warning(f"    not found: {template} (th={threshold})")
        return False

    if "x" in params or "y" in params:
        x, y = _anchor_xy(params, dx, dy, sx, sy)
        ctx.controller.click(x, y)
        return True

    return False


def _action_move(ctx, params, dx, dy, sx, sy) -> bool:
    template = params.get("template")
    threshold = params.get("threshold", 0.8)

    if template and ctx.vision:
        result = ctx.vision.find(
            ctx.screenshot, template, threshold, params.get("roi"),
            params.get("multi_scale", True),
            params.get("multi_angle", False),
        )
        if result.found:
            ctx.controller.move_to(result.center[0] + sx, result.center[1] + sy)
            return True
        logger.warning(f"    move target not found: {template}")
        return False
    return False


def _action_wait_until(ctx, params) -> bool:
    template = params.get("template", "")
    threshold = params.get("threshold", 0.8)
    timeout = params.get("timeout", 60)
    interval = params.get("interval", 1)

    logger.info(f"    waiting for: {template} (timeout={timeout}s)")
    start = time.time()
    while time.time() - start < timeout:
        ss = ctx.controller.screenshot()
        if ctx.popup and ctx.popup.enabled:
            ctx.popup.handle(ss)
        result = ctx.vision.find(ss, template, threshold)
        if result.found:
            logger.info(f"    appeared ({time.time()-start:.1f}s)")
            return True
        time.sleep(interval)

    logger.warning(f"    timeout: {template}")
    return False


def _action_find(ctx, params) -> bool:
    template = params.get("template")
    if template and ctx.vision:
        result = ctx.vision.find(
            ctx.screenshot, template, params.get("threshold", 0.8),
            params.get("roi"),
            params.get("multi_scale", True),
            params.get("multi_angle", False),
        )
        return result.found
    return False


def _action_find_color(ctx, params) -> bool:
    target = params.get("target")
    if not target or len(target) != 3:
        return False
    result = ctx.vision.find_color_region(
        ctx.screenshot, tuple(target),
        params.get("tolerance", 40),
        params.get("min_pct", 0.15),
        params.get("roi"),
    )
    return result.found


def _action_if(ctx, params) -> bool:
    condition = params.get("condition", {})
    cond_type = condition.get("type", "find")

    if cond_type == "find":
        template = condition.get("template")
        if template and ctx.vision:
            result = ctx.vision.find(
                ctx.screenshot, template,
                condition.get("threshold", 0.8),
            )
            return result.found

    elif cond_type == "find_text":
        keyword = condition.get("keyword", "")
        if keyword and ctx.vision:
            result = ctx.vision.find_text(
                ctx.screenshot, keyword,
                condition.get("roi"),
                condition.get("lang", "chi_sim+eng"),
            )
            return result.found

    elif cond_type == "find_color":
        target = condition.get("target")
        if target and len(target) == 3:
            result = ctx.vision.find_color_region(
                ctx.screenshot, tuple(target),
                condition.get("tolerance", 40),
                condition.get("min_pct", 0.15),
                condition.get("roi"),
            )
            return result.found

    elif cond_type == "compare":
        var_name = condition.get("var", "")
        op = condition.get("op", "==")
        value = condition.get("value")
        actual = ctx.vars.get(var_name)
        if actual is None:
            return False
        try:
            if op == "==": return actual == value
            if op == "!=": return actual != value
            if op == ">":  return float(actual) > float(value)
            if op == "<":  return float(actual) < float(value)
            if op == ">=": return float(actual) >= float(value)
            if op == "<=": return float(actual) <= float(value)
        except (ValueError, TypeError):
            return False

    elif cond_type == "exists":
        var_name = condition.get("var", "")
        return var_name in ctx.vars and ctx.vars[var_name] is not None

    return False


def _action_exec(params) -> bool:
    import subprocess
    cmd = params.get("cmd", "")
    if not cmd:
        return False
    cwd = params.get("cwd", ".")
    wait = params.get("wait", False)
    try:
        if wait:
            result = subprocess.run(cmd, shell=True, cwd=cwd)
            logger.info(f"    executed: {cmd} (exit={result.returncode})")
        else:
            subprocess.Popen(cmd, shell=True, cwd=cwd)
            logger.info(f"    executed: {cmd}")
        return True
    except Exception as e:
        logger.error(f"    exec failed: {e}")
        return False


def _action_hotkey(params) -> bool:
    keys = params.get("keys", [])
    if not keys:
        return False
    try:
        import pydirectinput
        for k in keys:
            pydirectinput.keyDown(k)
        for k in reversed(keys):
            pydirectinput.keyUp(k)
        logger.info(f"    hotkey: {'+'.join(keys)}")
        return True
    except Exception as e:
        logger.error(f"    hotkey failed: {e}")
        return False


def _action_ocr(ctx, params) -> bool:
    roi = params.get("roi")
    lang = params.get("lang", "chi_sim+eng")
    if ctx.vision:
        text = ctx.vision.ocr(ctx.screenshot, roi, lang)
        if text:
            logger.info(f"    OCR: {text[:100]}")
            return True
        logger.warning("    OCR: no text found")
    return False


def _action_find_text(ctx, params) -> bool:
    keyword = params.get("keyword", "")
    if not keyword or not ctx.vision:
        return False
    result = ctx.vision.find_text(
        ctx.screenshot, keyword,
        params.get("roi"),
        params.get("lang", "chi_sim+eng"),
    )
    if result.found:
        logger.info(f"    found text '{keyword}' at ({result.x},{result.y})")
    return result.found


def _action_set_var(ctx, params) -> bool:
    var_name = params.get("name", "")
    if not var_name:
        return False
    source = params.get("from", "value")

    if source == "value":
        ctx.vars[var_name] = params.get("value")
    elif source == "ocr":
        text = ctx.vision.ocr(ctx.screenshot, params.get("roi"),
                              params.get("lang", "chi_sim+eng"))
        ctx.vars[var_name] = text
    elif source == "count":
        template = params.get("template", "")
        results = ctx.vision.find_all(ctx.screenshot, template,
                                      params.get("threshold", 0.8))
        ctx.vars[var_name] = len(results)
    else:
        return False

    logger.info(f"    var {var_name} = {ctx.vars[var_name]}")
    return True


def _verify_click(ctx, template, threshold, cfg) -> bool:
    """Post-click verification: wait for template to disappear or appear."""
    timeout = cfg.get("timeout", 2.0)
    retries = cfg.get("retry", 3)
    interval = timeout / max(retries, 1)

    if cfg.get("disappear"):
        logger.info(f"    verifying: wait for {template} to disappear")
        for i in range(retries):
            time.sleep(interval)
            ss = ctx.controller.screenshot()
            r = ctx.vision.find(ss, template, threshold)
            if not r.found:
                logger.info(f"    verified: disappeared")
                return True
        logger.warning(f"    verify fail: still visible")
        return False

    elif cfg.get("appear"):
        appear_tpl = cfg["appear"]
        appear_th = cfg.get("appear_threshold", threshold)
        logger.info(f"    verifying: wait for {appear_tpl} to appear")
        for i in range(retries):
            time.sleep(interval)
            ss = ctx.controller.screenshot()
            r = ctx.vision.find(ss, appear_tpl, appear_th)
            if r.found:
                logger.info(f"    verified: appeared")
                return True
        logger.warning(f"    verify fail: not appeared")
        return False

    return True


def _scroll_and_retry(ctx, template, threshold, roi, cfg, dx, dy, verify_cfg=None) -> bool:
    """Scroll the page and retry finding the template."""
    direction = cfg.get("direction", "down")
    amount = cfg.get("amount", 300)
    max_attempts = cfg.get("max_attempts", 3)
    scroll_delay = cfg.get("delay", 0.5)

    logger.info(f"    scrolling {direction} {amount}px x{max_attempts}")
    for i in range(max_attempts):
        ctx.controller.scroll(direction, amount)
        time.sleep(scroll_delay)
        ss = ctx.controller.screenshot()
        result = ctx.vision.find(ss, template, threshold, roi)
        if result.found:
            cx, cy = result.center
            sx, sy = ctx.controller.capture_origin
            ctx.controller.click(cx + sx - dx, cy + sy - dy)
            if verify_cfg:
                return _verify_click(ctx, template, threshold, verify_cfg)
            return True
        logger.info(f"    scroll {i+1}: still not found")

    logger.warning(f"    scroll retries exhausted: {template}")
    return False


# ---------------------------------------------------------------------------
# Task format converters
# ---------------------------------------------------------------------------

def _convert_flat_to_tree(flat_data: dict) -> BTNode:
    """Convert old flat task format to behavior tree.

    Old format:
    {
      "_meta": {...},
      "TaskA": {"action":"click", "params":{...}, "next":["TaskB"], "onErrorNext":[...]},
      "TaskB": {...},
      ...
    }

    New format: Sequence of all tasks, with error handling via Selector.
    """
    tasks = {k: v for k, v in flat_data.items()
             if isinstance(v, dict) and not k.startswith('_')}

    if not tasks:
        return SequenceNode("empty")

    # Build a linked tree from the first task
    entry = list(tasks.keys())[0]
    visited = set()
    nodes = []

    def build_chain(task_name):
        if task_name is None or task_name in visited:
            return None
        visited.add(task_name)
        task = tasks.get(task_name)
        if not task:
            return None

        action = task.get("action", "click")
        desc = task.get("desc", task_name)
        params = task.get("params", {})

        # Create action node
        node = ActionNode(desc, {"action": action, "params": params})

        # Handle retry
        retry_cfg = task.get("retry")
        if retry_cfg:
            if isinstance(retry_cfg, dict):
                count = retry_cfg.get("count", 0)
                interval = retry_cfg.get("interval", 1.0)
            else:
                count = retry_cfg
                interval = 1.0
            if count > 0:
                node = RetryNode(f"{desc} (retry{count})", count, interval, node)

        # Handle error paths: wrap in Selector [success path, fallback path]
        next_tasks = task.get("next", [])
        on_error_next = task.get("onErrorNext")
        stop_on_error = task.get("stopOnError", False)

        if on_error_next and not stop_on_error:
            # Build success chain
            success_chain = SequenceNode(f"{desc}-ok")
            success_chain.children.append(node)
            if next_tasks:
                next_node = build_chain(next_tasks[0])
                if next_node:
                    success_chain.children.append(next_node)

            # Build fallback chain
            fallback_chain = SequenceNode(f"{desc}-fallback")
            fallback_chain.children.append(
                ActionNode(f"fallback-{on_error_next[0]}",
                          {"action": "log", "msg": f"Falling back: {on_error_next[0]}"}))
            next_node = build_chain(on_error_next[0])
            if next_node:
                fallback_chain.children.append(next_node)

            return SelectorNode(desc, [success_chain, fallback_chain])

        nodes.append(node)

        # Follow next
        if next_tasks:
            next_node = build_chain(next_tasks[0])
            if next_node:
                nodes.append(next_node)
        return node

    build_chain(entry)
    return SequenceNode(flat_data.get("_meta", {}).get("name", "task"), nodes)


# ---------------------------------------------------------------------------
# Behavior Tree Engine
# ---------------------------------------------------------------------------

class BTEngine:
    """Behavior-tree-driven task engine for SmartRPA.

    Usage:
        engine = BTEngine(controller, vision, popup)
        engine.load("examples/tieba/task.bt.json")
        engine.run()
    """

    MAX_STEPS = 5000

    def __init__(self, controller=None, vision=None, popup=None):
        self.controller = controller
        self.vision = vision
        self.popup = popup

        self._root: Optional[BTNode] = None
        self._meta: dict = {}
        self._running = False
        self._ctx = ActionContext(
            controller=controller,
            vision=vision,
            popup=popup,
        )

        # Register the action dispatcher for ActionNode
        ActionNode.ACTION_DISPATCH = None  # Use built-in _execute

        # Callbacks
        self._on_log: Optional[Callable] = None
        self._on_step: Optional[Callable] = None

    # -- config -----------------------------------------------------------

    def on(self, name: str, func: Callable):
        """Register a callback function (for 'callback' action)."""
        self._ctx.callbacks[name] = func

    def set_window_title(self, title: Optional[str]):
        """Set window title anchor."""
        self._ctx.window_title = title

    def configure_anchor(self, template: str, threshold: float = 0.8):
        """Configure template anchor (like old engine)."""
        self._anchor_template = template
        self._anchor_threshold = threshold

    def set_log_callback(self, cb: Callable):
        self._on_log = cb

    def set_step_callback(self, cb: Callable):
        self._on_step = cb

    # -- load -------------------------------------------------------------

    def load(self, path: str):
        """Load a task file (tree JSON or old flat JSON)."""
        p = Path(path)
        if p.is_dir():
            # Load first .json file
            for f in sorted(p.glob("*.json")):
                self._load_file(f)
                break
        else:
            self._load_file(p)

    def _load_file(self, filepath: Path):
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._meta = data.get("_meta", {})

        # Detect format
        if "root" in data:
            # New tree format
            self._root = BTNode.from_dict(data["root"])
            logger.info(f"Loaded BT task: {self._meta.get('name', filepath.stem)}")
        else:
            # Old flat format -- convert
            self._root = _convert_flat_to_tree(data)
            logger.info(f"Loaded flat task -> BT: "
                       f"{self._meta.get('name', filepath.stem)}")

    def load_tree(self, root: BTNode, meta: dict = None):
        """Directly set the tree root (for GUI tree editor)."""
        self._root = root
        self._meta = meta or {}

    # -- run --------------------------------------------------------------

    def _calibrate_anchor(self) -> Tuple[int, int]:
        """Calibrate window anchor offset (same logic as old engine)."""
        title = self._ctx.window_title
        if not title:
            return (0, 0)

        try:
            import win32gui
            pattern = title.replace("*", "____WILD____")
            parts = pattern.split("____WILD____")

            def find_win(hwnd, _):
                w_title = win32gui.GetWindowText(hwnd)
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                parts_clean = [p for p in parts if p]
                num_parts = len(parts)
                if num_parts == 3 and not parts[0] and not parts[-1]:
                    return parts[1] not in w_title
                if num_parts == 1:
                    return w_title != parts[0]
                if num_parts == 2 and not parts[1]:
                    return not w_title.startswith(parts[0])
                if num_parts == 2 and not parts[0]:
                    return not w_title.endswith(parts[1])
                if num_parts == 2:
                    return not (w_title.startswith(parts[0]) and w_title.endswith(parts[1]))
                if num_parts >= 3:
                    return not all(p in w_title for p in filter(None, parts))
                return True

            found = []
            win32gui.EnumWindows(find_win, None)
            if found:
                rect = win32gui.GetWindowRect(found[0])
                logger.info(f"Anchor: '{title}' -> ({rect[0]},{rect[1]})")
                return (rect[0], rect[1])
            else:
                logger.warning(f"Window not found: '{title}'")
        except ImportError:
            logger.warning("win32gui not installed, anchor disabled")
        return (0, 0)

    def run(self, timeout: float = 0):
        """Execute the behavior tree.

        Args:
            timeout: Global timeout in seconds (0 = no limit).
                     Also reads _meta.global_timeout as default.
        """
        if not self._root:
            logger.error("No task loaded")
            return

        # Task-level retry from _meta
        task_retry = self._meta.get("retry_on_failure", 0)
        if not isinstance(task_retry, int):
            task_retry = 0

        # Global timeout from meta or parameter
        if timeout <= 0:
            timeout = self._meta.get("global_timeout", 0)

        name = self._meta.get("name", "BT Task")
        global_start = time.time()

        for attempt in range(task_retry + 1):
            if attempt > 0:
                logger.info(f"[Task Retry] attempt {attempt+1}/{task_retry+1} — {name}")
                time.sleep(2)  # Cooldown between full restarts

            self._running = True
            self._ctx.stats = {"steps": 0, "errors": 0, "popups_handled": 0}
            self._root.reset()

            # Anchor calibration
            if self._ctx.window_title:
                self._ctx.anchor_offset = self._calibrate_anchor()

            # Speed mode from meta
            fast = self._meta.get("speed") == "fast"
            if fast and self.controller:
                self.controller.human.fast_mode = True

            logger.info(f"BT start: {name}" +
                       (f" (retry {attempt+1}/{task_retry+1})" if attempt > 0 else ""))

            step_count = 0
            failed = False
            while self._running and step_count < self.MAX_STEPS:
                # Global timeout check
                if timeout > 0 and (time.time() - global_start) > timeout:
                    logger.error(f"[Global Timeout] {timeout}s exceeded")
                    failed = True
                    break

                # Screenshot
                if self.controller:
                    self._ctx.screenshot = self.controller.screenshot()

                # Popup check
                if self.popup and self.popup.enabled:
                    if self.popup.handle(self._ctx.screenshot):
                        self._ctx.stats["popups_handled"] += 1
                        if self.controller:
                            self._ctx.screenshot = self.controller.screenshot()

                # Periodic anchor recalibration
                if self._ctx.window_title and step_count % 10 == 0:
                    self._ctx.anchor_offset = self._calibrate_anchor()

                # Tick the root
                status = self._root.tick(self._ctx)

                if status == Status.SUCCESS:
                    logger.info(f"BT done: SUCCESS "
                               f"({self._ctx.stats['steps']} steps, "
                               f"{self._ctx.stats['errors']} errors)")
                    break
                elif status == Status.FAILURE:
                    logger.error(f"BT done: FAILURE "
                                f"({self._ctx.stats['steps']} steps, "
                                f"{self._ctx.stats['errors']} errors)")
                    failed = True
                    break
                # RUNNING -> continue loop

                step_count += 1

            if not failed:
                break  # Success — don't retry

        logger.info(f"BT finished: {self._ctx.stats}")

    def stop(self):
        """Stop execution."""
        self._running = False

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> dict:
        """Export the tree as a JSON-serializable dict."""
        return {
            "_meta": self._meta,
            "root": self._root.to_dict() if self._root else None,
        }

    def to_json(self, indent: int = 2) -> str:
        """Export the tree as a JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def save(self, path: str):
        """Save the tree to a JSON file."""
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())
        logger.info(f"Saved BT to {path}")

    @property
    def stats(self):
        return dict(self._ctx.stats)

    @property
    def root(self):
        return self._root
