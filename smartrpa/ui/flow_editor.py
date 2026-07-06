"""Visual flow editor for behavior trees and task graphs.

Powered by QGraphicsView. Renders task nodes as boxes connected by
directed arrows. Supports zoom, pan, double-click editing.
"""

from math import atan2, pi, sin, cos
from typing import Dict, List, Optional, Tuple
import os

from PySide6.QtCore import (
    Qt, QRectF, QPointF, QLineF, Signal,
)
from PySide6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPainterPath,
    QPolygonF, QWheelEvent, QMouseEvent,
)
from PySide6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsItem,
    QGraphicsRectItem, QGraphicsTextItem, QGraphicsPathItem,
    QGraphicsEllipseItem, QGraphicsLineItem,
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QComboBox, QSpinBox,
    QDoubleSpinBox, QLineEdit, QFormLayout, QGroupBox,
    QScrollArea, QApplication, QSplitter, QFrame,
)


# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

NODE_W = 160
NODE_H = 54
H_GAP = 60
V_GAP = 36
CORNER_R = 6
ARROW_SIZE = 8

# Colors
C_SUCCESS = QColor("#22c55e")
C_FAILURE = QColor("#ef4444")
C_NODE_BG = QColor("#ffffff")
C_NODE_BORDER = QColor("#d1d5db")
C_NODE_TEXT = QColor("#1f2937")
C_NODE_SELECTED = QColor("#3b82f6")
C_NODE_ACTION = QColor("#dbeafe")
C_NODE_COMPOSITE = QColor("#fef3c7")
C_NODE_CONDITION = QColor("#fce7f3")
C_GRID = QColor("#f3f4f6")
C_PORT_HOVER = QColor("#3b82f6")


# ---------------------------------------------------------------------------
# Node type icon mapping
# ---------------------------------------------------------------------------

TYPE_ICONS = {
    "sequence":    ">>",
    "selector":    "?|",
    "retry":       "↻",
    "timeout":     "⏱",
    "inverter":    "!",
    "repeat":      "🔁",
    "parallel":    "||",
    "click":       "👆",
    "move":        "➤",
    "press":       "⌨",
    "type":        "Aa",
    "wait":        "🕐",
    "wait_until":  "👁",
    "swipe":       "↔",
    "find":        "🔍",
    "find_text":   "🔤",
    "find_color":  "🎨",
    "if":          "?",
    "exec":        "▶",
    "hotkey":      "🔑",
    "ocr":         "T",
    "callback":    "fn",
    "set_var":     "$=",
    "log":         "📋",
    "condition":   "?",
}

TYPE_COLORS = {
    "sequence":  C_NODE_COMPOSITE,
    "selector":  C_NODE_COMPOSITE,
    "retry":     C_NODE_COMPOSITE,
    "timeout":   C_NODE_COMPOSITE,
    "inverter":  C_NODE_COMPOSITE,
    "parallel":  C_NODE_COMPOSITE,
}


# Node help information — rich descriptions, params, examples for each node type
# ---------------------------------------------------------------------------

NODE_HELP = {
    "click": {
        "desc": "在屏幕上找到目标图片并点击（或直接点击坐标）。",
        "detail": "用模板匹配定位目标位置后模拟鼠标左键点击。支持点击验证和滚动查找。",
        "params": [
            ("template", "str", "", "目标模板图片路径，如 sign_btn.png"),
            ("threshold", "float", "0.8", "匹配精度 0.1~1.0，越高越严格"),
            ("x / y", "int", "—", "直接指定坐标点（无需模板时）"),
            ("roi", "list", "—", "限定搜索区域 [x,y,w,h]"),
            ("retry", "int", "0", "失败自动重试次数"),
        ],
        "example": 'template="sign_btn.png"  threshold=0.8  retry=3',
        "source": "_action_click() → vision.find() → controller.click()",
    },
    "move": {
        "desc": "将鼠标移动到目标位置，不点击。常用于悬停触发下拉菜单。",
        "detail": "找到目标图片后将鼠标移到其中心位置。不产生任何点击事件。",
        "params": [
            ("template", "str", "", "目标模板图片路径"),
            ("threshold", "float", "0.8", "匹配精度"),
        ],
        "example": 'template="more_btn.png"  → 悬停展开下拉菜单',
        "source": "_action_move() → vision.find() → controller.move_to()",
    },
    "swipe": {
        "desc": "从起点拖拽到终点，模拟鼠标滑动操作。",
        "detail": "按住鼠标从 A 点拖到 B 点并释放。用于滑动验证码、拖拽排序等场景。",
        "params": [
            ("from", "list", "[0,0]", "起点坐标 [x, y]"),
            ("to", "list", "[100,100]", "终点坐标 [x, y]"),
        ],
        "example": 'from=[200,500]  to=[600,500]  → 向右滑动',
        "source": "_action_swipe() → controller.drag(x1,y1, x2,y2)",
    },
    "press": {
        "desc": "按下并释放单个键盘键。",
        "detail": "模拟一次按键事件。支持普通字母、数字和特殊功能键。",
        "params": [
            ("key", "str", "", "键名: enter/tab/esc/space/f5"),
        ],
        "examples": ['key="enter"', 'key="tab"'],
        "source": "_action_press() -> controller.press_key(key)",
    },
    "type": {
        "desc": "在当前焦点位置输入一段文字。",
        "detail": "逐字符模拟键盘输入。输入前确保光标已在正确的输入框内（通常先 click 再 type）。",
        "params": [
            ("text", "str", "", "要输入的文字内容"),
        ],
        "examples": ['text="Python教程"'],
        "source": "_action_type() -> controller.type_text(text)",
    },
    "hotkey": {
        "desc": "同时按下多个键（组合快捷键），然后逆序释放。",
        "detail": "模拟 Ctrl+C、Alt+F4 等组合键操作。keys 列表中的键会同时按下。",
        "params": [
            ("keys", "list", "[]", '按键列表: ["ctrl","c"]'),
        ],
        "examples": ['keys=["ctrl","c"]', 'keys=["alt","f4"]'],
        "source": "_action_hotkey() -> pydirectinput.keyDown/Up",
    },
    "wait": {
        "desc": "暂停指定秒数，不做任何操作。",
        "detail": "固定延迟等待。适用于加载时间固定的场景。如果加载时间不稳定，建议改用 wait_until。",
        "params": [
            ("seconds", "float", "1.0", "等待秒数"),
        ],
        "example": 'seconds=2  → 等待 2 秒让页面加载',
        "source": "_action_wait() → time.sleep(seconds)",
    },
    "wait_until": {
        "desc": "持续截屏检查，直到目标画面出现（或超时失败）。",
        "detail": "每 interval 秒截屏一次，用模板匹配查找目标。找到立刻返回成功，超过 timeout 秒返回失败。期间自动检测弹窗。",
        "params": [
            ("template", "str", "", "要等待出现的模板图片（必填）"),
            ("timeout", "float", "60", "最长等待秒数"),
            ("interval", "float", "1", "检查间隔秒数"),
            ("threshold", "float", "0.8", "匹配精度"),
        ],
        "example": 'template="success.png"  timeout=30  → 等成功页出现',
        "source": "_action_wait_until() → 循环 screenshot + vision.find()",
    },
    "find": {
        "desc": "检查屏幕上是否存在某个模板图片。只判断，不操作鼠标键盘。",
        "detail": "纯视觉判断节点。常放在 selector 中作为分支条件，或配合其他逻辑使用。",
        "params": [
            ("template", "str", "", "目标模板图片路径"),
            ("threshold", "float", "0.8", "匹配精度"),
        ],
        "example": 'template="popup_close.png"  → 有弹窗就关闭',
        "source": "_action_find() → vision.find(ss, template) → bool",
    },
    "find_text": {
        "desc": "识别屏幕文字，检查是否包含指定关键词。",
        "detail": "调用 OCR 引擎读取屏幕指定区域（或全屏），搜索关键词是否出现。",
        "params": [
            ("keyword", "str", "", "要搜索的关键词"),
            ("roi", "list", "—", "限定 OCR 区域 [x,y,w,h]"),
            ("lang", "str", '"chi_sim+eng"', "OCR 语言"),
        ],
        "example": 'keyword="签到成功"  → 确认签到结果',
        "source": "_action_find_text() → vision.find_text(ss, keyword)",
    },
    "find_color": {
        "desc": "检测屏幕上是否存在指定颜色区域。",
        "detail": "在指定区域内搜索目标颜色的像素占比是否达到阈值。适合检测状态指示灯、进度条等。",
        "params": [
            ("target", "list", "[R,G,B]", "目标颜色 RGB 值"),
            ("tolerance", "int", "40", "颜色容差 0~255"),
            ("min_pct", "float", "0.15", "最小占比 0~1"),
            ("roi", "list", "—", "限定搜索区域 [x,y,w,h]"),
        ],
        "example": 'target=[0,255,0]  → 检测绿色进度条是否满',
        "source": "_action_find_color() → vision.find_color_region()",
    },
    "exec": {
        "desc": "执行一条系统命令（cmd/shell 命令行）。",
        "detail": "通过 subprocess 调用系统命令。可启动程序、运行脚本、打开网页等。支持同步等待和异步两种模式。",
        "params": [
            ("cmd", "str", "", "命令字符串"),
            ("cwd", "str", '"."', "工作目录"),
            ("wait", "bool", "false", "是否等命令结束"),
        ],
        "examples": ['cmd="start msedge https://tieba.baidu.com"', 'cmd="notepad.exe"  wait=true'],
        "source": "_action_exec() → subprocess.Popen/run(cmd)",
    },
    "set_var": {
        "desc": "设置一个变量供后续节点引用。支持直接赋值、OCR 读取、计数三种来源。",
        "detail": "变量存储在 ActionContext.vars 字典中，后续节点可用 {变量名} 格式引用（如 log 的 msg 字段）。",
        "params": [
            ("name", "str", "", "变量名"),
            ("from", "str", '"value"', '来源: value/ocr/count'),
            ("value", "any", "—", "from=value 时直接赋的值"),
            ("roi", "list", "—", "from=ocr 时 OCR 区域"),
            ("template", "str", "—", "from=count 时计数的模板"),
        ],
        "examples": ['name="counter" from="value" value=0', 'name="balance" from="ocr" roi=[100,200,300,50]'],
        "source": "_action_set_var() → ctx.vars[name] = value",
    },
    "log": {
        "desc": "在运行日志中输出一行信息，支持变量替换。",
        "detail": "输出到日志面板和控制台。消息中可用 {变量名} 引用之前 set_var 存储的值。",
        "params": [
            ("msg", "str", "", "日志内容，支持 {var} 变量替换"),
        ],
        "example": 'msg="处理完成，共 {count} 条"',
        "source": "_action_log() → logger.info(msg)",
    },
    # --- Composite nodes ---
    "sequence": {
        "desc": "顺序执行所有子节点。一个失败则全部停止。",
        "detail": "相当于「先做A，再做B，再做C」。只有全部子节点都返回 SUCCESS 才算成功。",
        "params": [],
        "example": "click(A) → wait_until(B) → log(C)",
        "source": "SequenceNode.tick() → 逐个 child.tick(), FAILURE 即停",
    },
    "selector": {
        "desc": "依次尝试子节点，哪个先成功就用哪个。",
        "detail": "相当于「试试A，不行就试B」。第一个成功的子节点决定整体结果。全部失败才失败。",
        "params": [],
        "example": "try: click(关闭弹窗)  fallback: press(esc)",
        "source": "SelectorNode.tick() → 逐个尝试, SUCCESS 即停",
    },
    "retry": {
        "desc": "子节点失败时自动重试最多 N 次。",
        "detail": "每次重试前重新截图、检测弹窗。间隔 N 秒后重试。",
        "params": [
            ("count", "int", "3", "最大重试次数"),
            ("interval", "float", "1.0", "每次重试间隔秒数"),
        ],
        "example": "count=3 → 失败后最多再试 3 次",
        "source": "RetryNode.tick() → 循环 + time.sleep(interval)",
    },
    "timeout": {
        "desc": "限制子节点的总执行时间，超时则强制失败。",
        "detail": "从子节点开始计时，超过设定秒数立即终止并返回 FAILURE。防止流程卡死。",
        "params": [
            ("seconds", "float", "30", "超时秒数"),
        ],
        "example": "seconds=60 → 整个流程限时 60 秒",
        "source": "TimeoutNode.tick() → time.time()-start > seconds → FAIL",
    },
    "repeat": {
        "desc": "重复执行子节点，直到它失败才停止。",
        "detail": "相当于 while(success){ continue }。适合批量处理：每次处理一项，处理完了(find 失败) 就退出循环。",
        "params": [
            ("max_iterations", "int", "1000", "最大循环次数上限"),
        ],
        "example": "repeat → find+click → 直到 find 找不到为止",
        "source": "RepeatNode.tick() → while(SUCCESS && iter<max) loop",
    },
}


# ---------------------------------------------------------------------------
# FlowNode -- a single task/action box
# ---------------------------------------------------------------------------

class FlowNode(QGraphicsRectItem):
    """A node in the flow graph. Stores task config data."""

    nodeDoubleClicked = Signal(dict)   # config dict
    nodeSelected = Signal(dict)

    def __init__(self, node_id: str, name: str, node_type: str = "action",
                 config: dict = None, x: float = 0, y: float = 0):
        # QGraphicsRectItem is NOT a QObject -- can't use Signal on it.
        # Use callback attributes instead; set by FlowScene.add_node.
        super().__init__(0, 0, NODE_W, NODE_H)
        self.setPos(x, y)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(10)

        self.node_id = node_id
        self._name = name
        self.node_type = node_type
        self.config = config or {}

        self._hovered = False
        self._selected = False

        # Callbacks (set by FlowScene)
        self._on_dclick = lambda cfg: None
        self._on_select = lambda cfg: None
        self._on_port_start = lambda node_id, port: None
        self._on_port_move = lambda pos: None
        self._on_port_end = lambda pos: None

        # Programmatic move flag (skip snap in layout mode)
        self._layout_mode = False

        # Port drag state
        self._dragging_port: Optional[str] = None  # "success" or "failure"

        # Color based on type
        self._bg = TYPE_COLORS.get(node_type, C_NODE_ACTION)

        # Output ports (positioned at right edge)
        self._success_port: QPointF = None
        self._failure_port: QPointF = None

    def boundingRect(self):
        return QRectF(-2, -2, NODE_W + 4, NODE_H + 4)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)

        r = QRectF(0, 0, NODE_W, NODE_H)

        # Shadow
        if self.isSelected() or self._hovered:
            shadow_path = QPainterPath()
            shadow_path.addRoundedRect(r.adjusted(1, 2, 1, 2), CORNER_R, CORNER_R)
            painter.fillPath(shadow_path, QColor(0, 0, 0, 40))

        # Background
        path = QPainterPath()
        path.addRoundedRect(r, CORNER_R, CORNER_R)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self._bg if not self.isSelected() else QColor("#dbeafe"))
        painter.drawPath(path)

        # Border
        if self.isSelected():
            painter.setPen(QPen(C_NODE_SELECTED, 2))
        elif self._hovered:
            painter.setPen(QPen(C_NODE_BORDER.darker(120), 1.5))
        else:
            painter.setPen(QPen(C_NODE_BORDER, 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

        # Left accent bar (type indicator)
        accent = QRectF(0, 0, 4, NODE_H)
        accent_path = QPainterPath()
        accent_path.addRoundedRect(accent, CORNER_R, CORNER_R)
        # Clip to left rounded part
        painter.save()
        painter.setClipRect(QRectF(-2, -2, 6, NODE_H + 4))
        painter.setPen(Qt.NoPen)
        if self.node_type in ("click", "move", "press", "type", "swipe",
                              "hotkey", "exec", "wait", "wait_until", "ocr",
                              "find_text", "log", "set_var", "callback"):
            painter.setBrush(QColor("#3b82f6"))  # blue = action
        elif self.node_type in ("find", "find_color", "if", "condition"):
            painter.setBrush(QColor("#f59e0b"))  # amber = condition
        else:
            painter.setBrush(QColor("#8b5cf6"))  # purple = composite
        painter.drawPath(accent_path)
        painter.restore()

        # Icon
        icon = TYPE_ICONS.get(self.node_type, "?")
        icon_font = QFont("Segoe UI Symbol, Microsoft YaHei", 13)
        painter.setFont(icon_font)
        painter.setPen(C_NODE_TEXT)
        painter.drawText(QRectF(10, 0, 28, NODE_H), Qt.AlignVCenter | Qt.AlignLeft, icon)

        # Name text
        text_font = QFont("Microsoft YaHei", 10)
        text_font.setBold(False)
        painter.setFont(text_font)
        display = self._name if len(self._name) <= 14 else self._name[:13] + "..."
        painter.drawText(QRectF(40, 0, NODE_W - 60, NODE_H),
                        Qt.AlignVCenter | Qt.AlignLeft, display)

        # Type badge
        badge_font = QFont("Microsoft YaHei", 8)
        painter.setFont(badge_font)
        painter.setPen(QColor("#9ca3af"))
        painter.drawText(QRectF(0, NODE_H - 16, NODE_W - 10, 14),
                        Qt.AlignRight | Qt.AlignVCenter, self.node_type)

        # Ports (always visible for connection dragging)
        port_r = 6
        painter.setPen(QPen(C_SUCCESS.darker(120), 1.5))
        painter.setBrush(C_SUCCESS)
        painter.drawEllipse(QPointF(NODE_W, NODE_H * 0.33), port_r, port_r)
        painter.setPen(QPen(C_FAILURE.darker(120), 1.5))
        painter.setBrush(C_FAILURE)
        painter.drawEllipse(QPointF(NODE_W, NODE_H * 0.67), port_r, port_r)

        # Port labels
        tiny_font = QFont("Microsoft YaHei", 7)
        painter.setFont(tiny_font)
        painter.setPen(C_SUCCESS.darker(150))
        painter.drawText(QRectF(NODE_W + 8, NODE_H * 0.33 - 8, 20, 16),
                        Qt.AlignLeft, "S")
        painter.setPen(C_FAILURE.darker(150))
        painter.drawText(QRectF(NODE_W + 8, NODE_H * 0.67 - 8, 20, 16),
                        Qt.AlignLeft, "F")

        # Update port positions
        self._success_port = QPointF(NODE_W, NODE_H * 0.33)
        self._failure_port = QPointF(NODE_W, NODE_H * 0.67)

    def hoverEnterEvent(self, event):
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def mouseDoubleClickEvent(self, event):
        self._on_dclick(self.config)
        super().mouseDoubleClickEvent(event)

    def port_hit_test(self, scene_pos: QPointF) -> Optional[str]:
        """Check if scene_pos hits a port. Returns 'success', 'failure', or None."""
        local = self.mapFromScene(scene_pos)
        sp = QPointF(NODE_W, NODE_H * 0.33)
        fp = QPointF(NODE_W, NODE_H * 0.67)
        r = 10  # hit radius
        d1 = (local.x() - sp.x()) ** 2 + (local.y() - sp.y()) ** 2
        d2 = (local.x() - fp.x()) ** 2 + (local.y() - fp.y()) ** 2
        if d1 < r * r:
            return "success"
        if d2 < r * r:
            return "failure"
        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            port = self.port_hit_test(event.scenePos())
            if port:
                self._dragging_port = port
                self._on_port_start(self.node_id, port)
                event.accept()
                return
            self._on_select(self.config)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging_port:
            self._on_port_move(event.scenePos())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._dragging_port:
            self._on_port_end(event.scenePos())
            self._dragging_port = None
            event.accept()
            return
        if self.scene():
            getattr(self.scene(), '_clear_guides', lambda: None)()
        super().mouseReleaseEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            sc = self.scene()
            if self._layout_mode or not hasattr(sc, '_show_guides'):
                return value
            # Snap to grid: round to nearest 20px
            new_x = round(value.x() / 20) * 20
            new_y = round(value.y() / 20) * 20
            snapped = QPointF(new_x, new_y)
            sc._show_guides(self, snapped)
            return snapped

        if change == QGraphicsItem.ItemPositionHasChanged:
            # Notify scene to update arrows
            if self.scene():
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, lambda: getattr(
                    self.scene(), '_update_arrows', lambda: None)())
        return super().itemChange(change, value)

    @property
    def success_port(self) -> QPointF:
        return self.mapToScene(self._success_port or QPointF(NODE_W, NODE_H * 0.33))

    @property
    def failure_port(self) -> QPointF:
        return self.mapToScene(self._failure_port or QPointF(NODE_W, NODE_H * 0.67))

    @property
    def input_port(self) -> QPointF:
        return self.mapToScene(QPointF(0, NODE_H / 2))


# ---------------------------------------------------------------------------
# FlowArrow -- directed connection line
# ---------------------------------------------------------------------------

class FlowArrow(QGraphicsPathItem):
    """Arrow connecting two nodes."""

    def __init__(self, source: FlowNode, target: FlowNode,
                 success: bool = True, label: str = ""):
        super().__init__()
        self.source = source
        self.target = target
        self.success = success
        self.label = label
        self._color = C_SUCCESS if success else C_FAILURE
        self.setZValue(5)
        self.update_path()

    def update_path(self):
        """Recalculate the arrow path."""
        if self.success:
            src = self.source.success_port
        else:
            src = self.source.failure_port
        dst = self.target.input_port

        path = QPainterPath()
        path.moveTo(src)

        # Control points for bezier curve
        dx = dst.x() - src.x()
        ctrl_dist = max(abs(dx) * 0.4, 40)
        c1 = QPointF(src.x() + ctrl_dist, src.y())
        c2 = QPointF(dst.x() - ctrl_dist, dst.y())
        path.cubicTo(c1, c2, dst)

        self.setPath(path)

        # Update pen
        pen = QPen(self._color, 2 if self.success else 1.5)
        if not self.success:
            pen.setStyle(Qt.DashLine)
        self.setPen(pen)

    def paint(self, painter: QPainter, option, widget=None):
        super().paint(painter, option, widget)

        # Arrowhead
        path = self.path()
        if path.isEmpty():
            return
        end_point = path.pointAtPercent(1.0)

        # Get tangent at end
        t = 0.98
        pt_before = path.pointAtPercent(t)
        angle = atan2(end_point.y() - pt_before.y(),
                      end_point.x() - pt_before.x())

        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self._color)

        arrow = QPolygonF([
            end_point,
            QPointF(end_point.x() - ARROW_SIZE * cos(angle - pi / 6),
                    end_point.y() - ARROW_SIZE * sin(angle - pi / 6)),
            QPointF(end_point.x() - ARROW_SIZE * cos(angle + pi / 6),
                    end_point.y() - ARROW_SIZE * sin(angle + pi / 6)),
        ])
        painter.drawPolygon(arrow)

        # Arrow body (ensure it overlaps the target node slightly)
        painter.setPen(QPen(self._color, 2 if self.success else 1.5))
        painter.drawLine(
            QPointF(end_point.x() - ARROW_SIZE * 0.7 * cos(angle),
                    end_point.y() - ARROW_SIZE * 0.7 * sin(angle)),
            end_point,
        )


# ---------------------------------------------------------------------------
# FlowScene -- the graph scene
# ---------------------------------------------------------------------------

class FlowScene(QGraphicsScene):
    """Scene managing flow nodes and their connections."""

    nodeSelected = Signal(dict)
    nodeDoubleClicked = Signal(dict)

    def __init__(self):
        super().__init__()
        self._nodes: Dict[str, FlowNode] = {}
        self._arrows: List[FlowArrow] = []
        self._grid_visible = True
        self._guide_items: List[QGraphicsLineItem] = []

        # Connection drag state
        self._drag_src_node: Optional[FlowNode] = None
        self._drag_src_port: Optional[str] = None
        self._temp_line: Optional[QGraphicsPathItem] = None

        # Undo/redo stacks
        self._undo_stack: list = []
        self._redo_stack: list = []
        self._undo_batching = False
        self._undo_group: list = []

    def _show_guides(self, moving_node: FlowNode, new_pos: QPointF):
        """Show alignment guides when dragging a node."""
        self._clear_guides()
        mx, my = new_pos.x(), new_pos.y()
        guide_pen = QPen(QColor("#3b82f6"), 1, Qt.DashLine)

        # Use bounding rect of all nodes as guide extent (not huge magic numbers)
        all_rect = self.itemsBoundingRect()
        y0 = all_rect.top() - 100
        y1 = all_rect.bottom() + 100
        x0 = all_rect.left() - 100
        x1 = all_rect.right() + 100

        for node in self._nodes.values():
            if node is moving_node:
                continue
            nx, ny = node.x(), node.y()
            # Vertical alignment
            if abs(mx - nx) < 10:
                line = QGraphicsLineItem(nx, y0, nx, y1)
                line.setPen(guide_pen)
                line.setZValue(50)
                self.addItem(line)
                self._guide_items.append(line)
            # Horizontal alignment
            if abs(my - ny) < 10:
                line = QGraphicsLineItem(x0, ny, x1, ny)
                line.setPen(guide_pen)
                line.setZValue(50)
                self.addItem(line)
                self._guide_items.append(line)

    def _clear_guides(self):
        """Remove all alignment guide lines."""
        for item in self._guide_items:
            if item in self.items():
                self.removeItem(item)
        self._guide_items.clear()

    def set_grid_visible(self, v: bool):
        self._grid_visible = v
        self.update()

    def drawBackground(self, painter: QPainter, rect: QRectF):
        if not self._grid_visible:
            return
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.setPen(QPen(C_GRID, 1))

        left = int(rect.left()) - (int(rect.left()) % 40)
        top = int(rect.top()) - (int(rect.top()) % 40)

        lines = []
        for x in range(int(left), int(rect.right()), 40):
            lines.append((x, rect.top(), x, rect.bottom()))
        for y in range(int(top), int(rect.bottom()), 40):
            lines.append((rect.left(), y, rect.right(), y))

        for x1, y1, x2, y2 in lines:
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    def add_node(self, node_id: str, name: str, node_type: str = "action",
                 config: dict = None, x: float = 0, y: float = 0,
                 record_undo: bool = False) -> FlowNode:
        """Add a node to the scene."""
        node = FlowNode(node_id, name, node_type, config, x, y)
        # Use callbacks (FlowNode is not a QObject, can't use signals)
        node._on_dclick = self.nodeDoubleClicked.emit
        node._on_select = self.nodeSelected.emit
        node._on_port_start = self._on_node_port_start
        node._on_port_move = self._on_node_port_move
        node._on_port_end = self._on_node_port_end
        self.addItem(node)
        self._nodes[node_id] = node

        if record_undo and not node._layout_mode:
            cfg = dict(config or {})
            self._push_undo(
                lambda nid=node_id: self._remove_node_by_id(nid),
                lambda: self.add_node(node_id, name, node_type, cfg, x, y, False)
            )
        return node

    def _remove_node_by_id(self, node_id: str):
        """Remove a node and its arrows without undo recording."""
        node = self._nodes.get(node_id)
        if not node:
            return
        for a in list(self._arrows):
            if a.source is node or a.target is node:
                self.removeItem(a)
                self._arrows.remove(a)
        del self._nodes[node_id]
        self.removeItem(node)

    # ── Connection dragging ──

    def _on_node_port_start(self, node_id: str, port: str):
        self._drag_src_node = self._nodes.get(node_id)
        self._drag_src_port = port

        # Create temp line
        self._temp_line = QGraphicsPathItem()
        if port == "success":
            self._temp_line.setPen(QPen(C_SUCCESS, 2))
        else:
            self._temp_line.setPen(QPen(C_FAILURE, 1.5, Qt.DashLine))
        self._temp_line.setZValue(100)
        self.addItem(self._temp_line)

    def _on_node_port_move(self, scene_pos: QPointF):
        if not self._temp_line or not self._drag_src_node:
            return
        if self._drag_src_port == "success":
            src = self._drag_src_node.success_port
        else:
            src = self._drag_src_node.failure_port

        # Bezier from port to cursor
        path = QPainterPath()
        path.moveTo(src)
        dx = scene_pos.x() - src.x()
        ctrl_dist = max(abs(dx) * 0.4, 40)
        c1 = QPointF(src.x() + ctrl_dist, src.y())
        c2 = QPointF(scene_pos.x() - ctrl_dist, scene_pos.y())
        path.cubicTo(c1, c2, scene_pos)
        self._temp_line.setPath(path)

    def _on_node_port_end(self, scene_pos: QPointF):
        if not self._temp_line:
            return
        self.removeItem(self._temp_line)
        self._temp_line = None
        src = self._drag_src_node
        port = self._drag_src_port
        self._drag_src_node = None
        self._drag_src_port = None
        if not src:
            return

        # Find target node under cursor
        target_items = self.items(scene_pos, deviceTransform=self.views()[0].viewportTransform() if self.views() else None)
        for item in target_items:
            if isinstance(item, FlowNode) and item is not src:
                # Create connection
                self.connect_nodes(src.node_id, item.node_id, port == "success")
                return

    def connect_nodes(self, from_id: str, to_id: str, success: bool = True):
        """Draw an arrow between two nodes."""
        src = self._nodes.get(from_id)
        dst = self._nodes.get(to_id)
        if src and dst:
            arrow = FlowArrow(src, dst, success)
            self.addItem(arrow)
            self._arrows.append(arrow)

    def clear_all(self):
        """Remove all nodes and arrows."""
        for a in self._arrows:
            self.removeItem(a)
        self._arrows.clear()
        for n in list(self._nodes.values()):
            self.removeItem(n)
        self._nodes.clear()

    def _update_arrows(self):
        """Refresh all arrow paths (called after node moves)."""
        for arrow in self._arrows:
            arrow.update_path()

    def auto_layout(self, tasks: dict, entry: str):
        """Auto-layout from flat task dict.

        Args:
            tasks: {node_id: {action, next, onErrorNext, desc, ...}}
            entry: Entry node ID
        """
    # ── Left-to-right layout ──
    MAX_COL_HEIGHT = 700

    def auto_layout(self, tasks: dict, entry: str):
        """Left-to-right flat layout with column wrapping."""
        self.clear_all()

        depths: Dict[str, int] = {}
        visiting = set()

        def calc_depth(node_id: str, depth: int):
            if node_id is None or node_id in visiting:
                return
            visiting.add(node_id)
            if depth > depths.get(node_id, -1):
                depths[node_id] = depth
            task = tasks.get(node_id, {})
            for next_id in (task.get("next") or []):
                calc_depth(next_id, depth + 1)
            for next_id in (task.get("onErrorNext") or []):
                calc_depth(next_id, depth + 1)
            visiting.discard(node_id)

        calc_depth(entry, 0)
        for nid in tasks:
            if nid not in depths:
                depths[nid] = 0

        layers: Dict[int, List[str]] = {}
        for nid, d in depths.items():
            layers.setdefault(d, []).append(nid)

        # Assign to columns (wrap if column exceeds MAX_COL_HEIGHT)
        columns: List[List[str]] = []
        cur_col: List[str] = []
        for depth in sorted(layers.keys()):
            nids = layers[depth]
            needed = len(nids) * (NODE_H + V_GAP)
            cur_h = len(cur_col) * (NODE_H + V_GAP)
            if cur_col and cur_h + needed > self.MAX_COL_HEIGHT:
                columns.append(cur_col)
                cur_col = []
            cur_col.extend(nids)
        if cur_col:
            columns.append(cur_col)

        # Place nodes: column N at x = col * (NODE_W + H_GAP)
        for ci, col_ids in enumerate(columns):
            col_x = 40 + ci * (NODE_W + H_GAP)
            y = 40
            for nid in col_ids:
                task = tasks.get(nid, {})
                name = task.get("desc", nid)
                action = task.get("action", "click")
                self.add_node(nid, name, action, task, col_x, y)
                y += NODE_H + V_GAP

        for nid, task in tasks.items():
            for next_id in (task.get("next") or []):
                if next_id in self._nodes:
                    self.connect_nodes(nid, next_id, success=True)
            for next_id in (task.get("onErrorNext") or []):
                if next_id in self._nodes:
                    self.connect_nodes(nid, next_id, success=False)

        self.setSceneRect(self.itemsBoundingRect().adjusted(-40, -40, 40, 40))

    def load_bt_tree(self, root: dict):
        """Left-to-right BT tree layout. Parent on left, children on right."""
        self.clear_all()

        def subtree_height(node_dict: dict) -> float:
            children = node_dict.get("children", [])
            child = node_dict.get("child")
            if child:
                children = list(children) + [child]
            if not children:
                return NODE_H + V_GAP
            return sum(subtree_height(c) for c in children)

        def place(node_dict: dict, x: float, start_y: float,
                  parent_id: Optional[str] = None):
            node_type = node_dict.get("type", "action")
            name = node_dict.get("name", node_type)
            node_id = name or f"node_{len(self._nodes)}"
            base_id = node_id
            counter = 1
            while node_id in self._nodes:
                node_id = f"{base_id}_{counter}"
                counter += 1

            h = subtree_height(node_dict)
            y = start_y + h / 2 - NODE_H / 2
            self.add_node(node_id, name, node_type, node_dict, x, y)

            if parent_id:
                self.connect_nodes(parent_id, node_id, success=True)

            children = node_dict.get("children", [])
            child = node_dict.get("child")
            if child:
                children = list(children) + [child]
            if children:
                child_x = x + NODE_W + H_GAP
                cy = start_y
                for c in children:
                    ch = subtree_height(c)
                    place(c, child_x, cy, node_id)
                    cy += ch
            return node_id

        root_h = subtree_height(root)
        place(root, 40, 40)

        for node in self._nodes.values():
            node._layout_mode = True

        self._clear_guides()
        self.setSceneRect(self.itemsBoundingRect().adjusted(-40, -40, 40, 40))

        # Center vertically
        items_r = self.itemsBoundingRect()
        dy = items_r.height() / 2 - root_h / 2 - 40
        if abs(dy) > 20:
            for node in self._nodes.values():
                node.setY(node.y() - dy)

        for node in self._nodes.values():
            node._layout_mode = False

    def delete_selected(self):
        """Remove selected nodes and their connections (with undo)."""
        to_remove = [n for n in self._nodes.values() if n.isSelected()]
        if not to_remove:
            arrow_removed = False
            for a in list(self._arrows):
                if a.isSelected():
                    self.removeItem(a)
                    self._arrows.remove(a)
                    arrow_removed = True
            if not arrow_removed:
                return
            self._update_arrows()
            return

        # Save state for undo
        snapshots = []
        for node in to_remove:
            connected = [(a.source.node_id, a.target.node_id, a.success)
                         for a in self._arrows
                         if a.source is node or a.target is node]
            snap = (node.node_id, node._name, node.node_type,
                    dict(node.config), node.x(), node.y(), connected)
            snapshots.append(snap)

        # Remove nodes
        for node in to_remove:
            self._remove_node_by_id(node.node_id)

        # Push undo
        def undo_del():
            for snap in snapshots:
                nid, name, ntype, cfg, x, y, conns = snap
                self.add_node(nid, name, ntype, cfg, x, y, False)
                for src_id, tgt_id, succ in conns:
                    new_src = self._nodes.get(src_id)
                    new_tgt = self._nodes.get(tgt_id)
                    if new_src and new_tgt:
                        self.connect_nodes(src_id, tgt_id, succ)

        def redo_del():
            for snap in snapshots:
                self._remove_node_by_id(snap[0])

        self._push_undo(undo_del, redo_del)
        self._update_arrows()

    def get_node(self, node_id: str) -> Optional[FlowNode]:
        return self._nodes.get(node_id)

    # ── Undo/Redo ──

    def _push_undo(self, undo_action, redo_action):
        """Push an undo/redo pair onto the stack."""
        if self._undo_batching:
            self._undo_group.append((undo_action, redo_action))
            return
        self._undo_stack.append((undo_action, redo_action))
        self._redo_stack.clear()
        if len(self._undo_stack) > 50:
            self._undo_stack.pop(0)

    def _begin_undo_group(self):
        self._undo_batching = True
        self._undo_group = []

    def _end_undo_group(self):
        self._undo_batching = False
        if self._undo_group:
            # Combine into one undo entry
            def undo_all():
                for u, r in reversed(self._undo_group):
                    u()
            def redo_all():
                for u, r in self._undo_group:
                    r()
            self._undo_stack.append((undo_all, redo_all))
            self._redo_stack.clear()
            self._undo_group = []

    def undo(self):
        if not self._undo_stack:
            return
        undo_fn, redo_fn = self._undo_stack.pop()
        undo_fn()
        self._redo_stack.append((undo_fn, redo_fn))
        self._update_arrows()

    def redo(self):
        if not self._redo_stack:
            return
        undo_fn, redo_fn = self._redo_stack.pop()
        redo_fn()
        self._undo_stack.append((undo_fn, redo_fn))
        self._update_arrows()

    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0


# ---------------------------------------------------------------------------
# FlowView -- the QGraphicsView wrapper
# ---------------------------------------------------------------------------

class FlowView(QGraphicsView):
    """Zoomable, pannable flow graph view."""

    def __init__(self, scene: FlowScene):
        super().__init__(scene)
        self._scene = scene
        self.setRenderHint(QPainter.Antialiasing)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setBackgroundBrush(QColor("#fafafa"))
        self.setFrameShape(QFrame.NoFrame)

        # Cursor: arrow by default, hand only when panning
        self.viewport().setCursor(Qt.ArrowCursor)
        self.setDragMode(QGraphicsView.NoDrag)
        self._panning = False
        self._pan_start = QPointF()

        self._zoom = 1.0
        self._min_zoom = 0.15
        self._max_zoom = 3.0
        self._on_zoom = None  # callback(zoom_pct)

    def wheelEvent(self, event: QWheelEvent):
        factor = 1.15
        if event.angleDelta().y() < 0:
            factor = 1.0 / factor

        # Read actual zoom from view transform (not cached _zoom)
        current = self.transform().m11()
        new_zoom = current * factor

        # Clamp to allowed range
        if new_zoom < self._min_zoom:
            factor = self._min_zoom / current
            new_zoom = self._min_zoom
        elif new_zoom > self._max_zoom:
            factor = self._max_zoom / current
            new_zoom = self._max_zoom

        if abs(factor - 1.0) > 0.001:
            self._zoom = new_zoom
            self.scale(factor, factor)
            if self._on_zoom:
                self._on_zoom(int(new_zoom * 100))

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._pan_start = event.position()
            self.viewport().setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._panning:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - int(delta.x()))
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - int(delta.y()))
            event.accept()
            return

        # Check if hovering over a port → change cursor
        scene_pos = self.mapToScene(event.pos())
        for node in self._scene._nodes.values():
            if node.port_hit_test(scene_pos):
                self.viewport().setCursor(Qt.CrossCursor)
                break
        else:
            self.viewport().setCursor(Qt.ArrowCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MiddleButton and self._panning:
            self._panning = False
            self.viewport().setCursor(Qt.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def fit_all(self):
        self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)
        self._zoom = self.transform().m11()

    def reset_view(self):
        self.resetTransform()
        self._zoom = 1.0
        self.fit_all()


# ---------------------------------------------------------------------------
# NodePalettePanel -- left panel with node type buttons
# ---------------------------------------------------------------------------

NODE_CATEGORIES = [
    ("鼠标", [
        ("👆 点击", "click"),
        ("➤ 移动", "move"),
        ("↔ 滑动", "swipe"),
    ]),
    ("键盘", [
        ("⌨ 按键", "press"),
        ("Aa 输入", "type"),
        ("🔑 组合键", "hotkey"),
    ]),
    ("等待", [
        ("🕐 等待", "wait"),
        ("👁 等到", "wait_until"),
    ]),
    ("视觉", [
        ("🔍 查找", "find"),
        ("OCR 识字", "find_text"),
        ("🎨 颜色", "find_color"),
    ]),
    ("流程", [
        (">> 顺序", "sequence"),
        ("?| 选择", "selector"),
        ("↻ 重试", "retry"),
        ("⏱ 超时", "timeout"),
        ("🔁 循环", "repeat"),
    ]),
    ("系统", [
        ("▶ 命令", "exec"),
        ("$= 赋值", "set_var"),
        ("📋 日志", "log"),
    ]),
]


class NodePalettePanel(QWidget):
    """Left sidebar panel with draggable node-type buttons."""

    nodeRequested = Signal(str)  # node_type

    def __init__(self):
        super().__init__()
        self.setFixedWidth(130)
        self.setStyleSheet("background:#f5f5f8; border-right:1px solid #e5e7eb;")

        ly = QVBoxLayout(self)
        ly.setContentsMargins(0, 0, 0, 0)
        ly.setSpacing(0)

        # Header
        hdr = QLabel("节点")
        hdr.setStyleSheet(
            "font-size:12px; font-weight:600; color:#374151; "
            "padding:8px 10px; background:#e5e7eb;")
        ly.addWidget(hdr)

        # Scrollable body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")

        body = QWidget()
        body.setStyleSheet("background:transparent;")
        body_ly = QVBoxLayout(body)
        body_ly.setContentsMargins(4, 4, 4, 4)
        body_ly.setSpacing(2)

        for cat_name, items in NODE_CATEGORIES:
            # Category header
            cat_lbl = QLabel(cat_name)
            cat_lbl.setStyleSheet(
                "font-size:10px; font-weight:600; color:#9ca3af; "
                "padding:6px 6px 2px 6px; text-transform:uppercase;")
            body_ly.addWidget(cat_lbl)

            # Node buttons
            for label, ntype in items:
                btn = QPushButton(label)
                btn.setCursor(Qt.PointingHandCursor)
                btn.setStyleSheet("""
                    QPushButton {
                        background: white; color: #374151;
                        border: 1px solid #e5e7eb; border-radius: 3px;
                        padding: 3px 6px; font-size: 11px; text-align: left;
                        min-height: 22px;
                    }
                    QPushButton:hover {
                        background: #eff6ff; border-color: #93c5fd;
                    }
                """)
                btn.clicked.connect(lambda checked, t=ntype: self.nodeRequested.emit(t))
                body_ly.addWidget(btn)

        body_ly.addStretch(1)
        scroll.setWidget(body)
        ly.addWidget(scroll, 1)


# ---------------------------------------------------------------------------
# PropertyEditor -- right panel for editing node properties
# ---------------------------------------------------------------------------

class PropertyEditor(QWidget):
    """Panel showing editable properties for the selected node.
    Supports dock-style collapse: click minimize button to shrink to a narrow
    strip, click again to expand back.
    """

    propertyChanged = Signal(str, dict)  # node_id, updated_config

    def __init__(self):
        super().__init__()
        self._current_node_id: Optional[str] = None
        self._current_config: dict = {}
        self._template_dir: str = ""  # set by FlowEditor
        self._help_expanded = True  # inner help card toggle

        main_ly = QVBoxLayout(self)
        main_ly.setContentsMargins(0, 0, 0, 0)
        main_ly.setSpacing(0)

        # ═══ Expanded content ═══
        self._content = QWidget()
        ly = QVBoxLayout(self._content)
        ly.setContentsMargins(0, 0, 0, 0)
        ly.setSpacing(0)

        # ── Title row with close button ──
        title_row = QWidget()
        title_ly = QHBoxLayout(title_row)
        title_ly.setContentsMargins(10, 6, 6, 6)

        self._title = QLabel("属性")
        self._title.setStyleSheet(
            "font-size:13px; font-weight:600; color:#374151;")
        title_ly.addWidget(self._title, 1)

        # Close button — hides the entire panel (one button, that's it)
        close_btn = QPushButton()
        close_btn.setFixedSize(18, 18)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setToolTip("关闭")
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: none;
                color: #9ca3af; border-radius: 9px;
                qproperty-icon: url(close_icon);
            }
            QPushButton:hover {
                background: #f3f4f6; color: #374151;
            }
        """)
        # Draw × using unicode
        close_btn.setText("\u2715")
        close_btn.setStyleSheet("""
            QPushButton {
                font-size: 11px; font-weight: normal;
                color: #9ca3af; background: transparent;
                border: none; border-radius: 9px;
            }
            QPushButton:hover {
                color: #ef4444; background: #fef2f2;
            }
        """)
        close_btn.clicked.connect(self.hide)  # just hide the panel, simple
        title_ly.addWidget(close_btn)

        ly.addWidget(title_row)

        # ── Help card container (collapsible inner area) ──
        self._help_container = QWidget()
        self._help_container.setStyleSheet(
            "background:#fafbfc; border-bottom:1px solid #e5e7eb;")
        help_ly = QVBoxLayout(self._help_container)
        help_ly.setContentsMargins(10, 4, 10, 8)
        help_ly.setSpacing(6)
        self._help_layout = help_ly

        ly.addWidget(self._help_container)

        # ── Edit form area (always visible when expanded) ──
        form_w = QWidget()
        self._form = QFormLayout(form_w)
        self._form.setContentsMargins(12, 8, 12, 8)
        self._form.setSpacing(8)
        ly.addWidget(form_w, 1)

        self._form_w = form_w
        self._key_recording = False

        # Apply button
        self._apply_btn = QPushButton("应用")
        self._apply_btn.setStyleSheet("""
            QPushButton {
                background: #3b82f6; color: white; border: none;
                border-radius: 4px; padding: 6px 16px; font-weight: 600;
                font-size: 12px; min-height: 28px;
            }
            QPushButton:hover { background: #2563eb; }
        """)
        self._apply_btn.clicked.connect(self._apply)
        ly.addWidget(self._apply_btn)

        main_ly.addWidget(self._content)

        self.setVisible(False)

    def _clear_form(self):
        while self._form.rowCount() > 0:
            self._form.removeRow(0)
        # Also clear help container
        while self._help_layout.count():
            item = self._help_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _toggle_help(self):
        """Toggle collapse/expand of the help card section."""
        self._help_expanded = not self._help_expanded
        self._help_container.setVisible(self._help_expanded)
        if hasattr(self, '_help_toggle_btn'):
            self._help_toggle_btn.setText("▲" if self._help_expanded else "▼")

    def _add_help_card(self, help_info: dict, node_type: str):
        """Insert a rich help card into the collapsible help container."""

        # ── Description block ──
        desc_lbl = QLabel(help_info["desc"])
        desc_lbl.setStyleSheet(
            "font-size:13px; font-weight:600; color:#1e40af; "
            "padding:2px 0; line-height:1.5;")
        desc_lbl.setWordWrap(True)
        self._help_layout.addWidget(desc_lbl)

        # Detail text (softer, secondary)
        if "detail" in help_info:
            detail_lbl = QLabel(help_info["detail"])
            detail_lbl.setStyleSheet(
                "font-size:11px; color:#6b7280; "
                "padding:0 0 6px 0; line-height:1.5;")
            detail_lbl.setWordWrap(True)
            self._help_layout.addWidget(detail_lbl)

        # ── Parameter table ──
        params = help_info.get("params", [])
        if params:
            # Header row
            hdr_w = QWidget()
            hdr_ly = QHBoxLayout(hdr_w)
            hdr_ly.setContentsMargins(0, 4, 0, 2)
            for txt, w in [("参数", 70), ("类型", 50), ("默认", 60), ("说明", 999)]:
                lbl = QLabel(txt)
                lbl.setStyleSheet("font-size:10px; font-weight:600; color:#9ca3af;")
                if w < 999:
                    lbl.setFixedWidth(w)
                hdr_ly.addWidget(lbl)
            self._help_layout.addWidget(hdr_w)

            # Data rows
            for pname, ptype, pdefault, pdesc in params:
                row_w = QWidget()
                row_ly = QHBoxLayout(row_w)
                row_ly.setContentsMargins(0, 1, 0, 1)
                for val, w in [(pname, 70), (ptype, 50), (pdefault, 60)]:
                    lbl = QLabel(str(val))
                    lbl.setStyleSheet(
                        "font-size:11px; color:#374151;"
                        "font-family:'Cascadia Code',monospace;")
                    lbl.setFixedWidth(w)
                    row_ly.addWidget(lbl)
                desc_lbl = QLabel(pdesc)
                desc_lbl.setStyleSheet("font-size:11px; color:#6b7280;")
                desc_lbl.setMinimumWidth(120)
                row_ly.addWidget(desc_lbl, 1)
                self._help_layout.addWidget(row_w)

        # ── Quick-fill example buttons ──
        ex_list = help_info.get("examples", [])
        if isinstance(ex_list, str):
            ex_list = [ex_list]
        if not ex_list:
            single = help_info.get("example")
            if single:
                ex_list = [single]
        if ex_list:
            tip = QLabel("点击示例快速填入:")
            tip.setStyleSheet("font-size:10px; color:#9ca3af; padding:6px 0 2px 0;")
            self._help_layout.addWidget(tip)
            btn_row = QWidget()
            btn_ly = QHBoxLayout(btn_row)
            btn_ly.setContentsMargins(0, 0, 0, 0)
            btn_ly.setSpacing(6)
            for i, ex in enumerate(ex_list[:3]):  # max 3 quick-fill buttons
                lbl_text = ex if len(ex) <= 38 else ex[:35] + "..."
                btn = QPushButton(f"📋 {lbl_text}")
                btn.setStyleSheet(
                    "QPushButton{font-size:10px; font-family:'Cascadia Code',monospace; "
                    "color:#059669; background:#ecfdf5; border:1px solid #a7f3d0; "
                    "border-radius:4px; padding:4px 8px; text-align:left;} "
                    "QPushButton:hover{background:#d1fae5; border-color:#059669;}")
                btn.setCursor(Qt.PointingHandCursor)
                btn.clicked.connect(lambda checked, e=ex: self._apply_example(e))
                btn_ly.addWidget(btn, 1)
            btn_ly.addStretch()
            self._help_layout.addWidget(btn_row)

    def show_properties(self, node_id: str, config: dict):
        """Display properties for the given node."""
        self._current_node_id = node_id
        self._current_config = dict(config)
        self._clear_form()

        # Reset help to expanded state
        self._help_expanded = True
        self._help_container.setVisible(True)

        node_type = config.get("action", config.get("type", "action"))
        self._title.setText(f"属性 — {node_type}")

        # ── Help Card: description + params + example ──
        help_info = NODE_HELP.get(node_type)
        if help_info:
            # Add inline toggle button for help area
            help_hdr = QWidget()
            hdr_ly = QHBoxLayout(help_hdr)
            hdr_ly.setContentsMargins(0, 0, 0, 4)
            lbl = QLabel("节点说明")
            lbl.setStyleSheet("font-size:11px; font-weight:600; color:#6b7280;")
            hdr_ly.addWidget(lbl, 1)

            self._help_toggle_btn = QPushButton("▲")
            self._help_toggle_btn.setFixedSize(20, 20)
            self._help_toggle_btn.setCursor(Qt.PointingHandCursor)
            self._help_toggle_btn.setStyleSheet("""
                QPushButton {
                    background:transparent; border:none;
                    font-size:10px; color:#9ca3af;
                    border-radius:10px;
                }
                QPushButton:hover { background:#f3f4f6; color:#374151; }
            """)
            self._help_toggle_btn.clicked.connect(self._toggle_help)
            hdr_ly.addWidget(self._help_toggle_btn)
            self._help_layout.addWidget(help_hdr)

            self._add_help_card(help_info, node_type)

        # Editable fields
        self._form.addRow("名称:", self._make_input("desc",
                              config.get("desc", node_id)))
        self._form.addRow("类型:", QLabel(node_type))

        # Action-specific fields
        if "template" in config:
            row_w = QWidget()
            row_ly = QHBoxLayout(row_w)
            row_ly.setContentsMargins(0, 0, 0, 0)
            row_ly.setSpacing(4)

            inp = QLineEdit(config.get("template", ""))
            inp.setStyleSheet(self._input_style())
            setattr(inp, "_field", "template")
            inp.textChanged.connect(lambda t, i=inp:
                self._current_config.__setitem__(i._field, t))
            row_ly.addWidget(inp, 1)

            btn_style = "QPushButton{background:#f3f4f6;border:1px solid #d1d5db;border-radius:3px;padding:3px 8px;font-size:10px;}QPushButton:hover{background:#e5e7eb;}"

            pick_btn = QPushButton("选择")
            pick_btn.setStyleSheet(btn_style)
            pick_btn.clicked.connect(self._pick_template)
            row_ly.addWidget(pick_btn)

            cap_btn = QPushButton("截取")
            cap_btn.setStyleSheet(btn_style)
            cap_btn.clicked.connect(self._capture_screen)
            row_ly.addWidget(cap_btn)

            self._form.addRow("模板:", row_w)

            # Thumbnail preview
            tpl_name = config.get("template", "")
            if tpl_name and self._template_dir:
                tpl_path = os.path.join(self._template_dir, f"{tpl_name}.png") if not tpl_name.endswith('.png') else os.path.join(self._template_dir, tpl_name)
                if os.path.exists(tpl_path):
                    thumb = QLabel()
                    pix = QPixmap(tpl_path).scaled(120, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    thumb.setPixmap(pix)
                    thumb.setStyleSheet("border:1px solid #e5e7eb;border-radius:3px;")
                    self._form.addRow("预览:", thumb)

        if "threshold" in config:
            spin = QDoubleSpinBox()
            spin.setRange(0.1, 1.0)
            spin.setSingleStep(0.05)
            spin.setValue(config.get("threshold", 0.8))
            self._form.addRow("阈值:", spin)
            setattr(spin, "_field", "threshold")
            spin.valueChanged.connect(lambda v, s=spin:
                self._current_config.__setitem__(s._field, v))

        if "timeout" in config:
            spin = QDoubleSpinBox()
            spin.setRange(1, 600)
            spin.setValue(config.get("timeout", 30))
            self._form.addRow("超时(s):", spin)
            setattr(spin, "_field", "timeout")
            spin.valueChanged.connect(lambda v, s=spin:
                self._current_config.__setitem__(s._field, v))

        if "seconds" in config:
            spin = QDoubleSpinBox()
            spin.setRange(0.1, 300)
            spin.setValue(config.get("seconds", 1))
            self._form.addRow("等待(s):", spin)
            setattr(spin, "_field", "seconds")
            spin.valueChanged.connect(lambda v, s=spin:
                self._current_config.__setitem__(s._field, v))

        if "cmd" in config:
            self._form.addRow("命令:", self._make_input("cmd",
                                  config.get("cmd", "")))

        if "key" in config:
            row_w = QWidget()
            row_ly = QHBoxLayout(row_w)
            row_ly.setContentsMargins(0, 0, 0, 0)
            row_ly.setSpacing(4)

            key_inp = QLineEdit(config.get("key", ""))
            key_inp.setStyleSheet(self._input_style())
            key_inp.setPlaceholderText("按录制按钮或手动输入")
            setattr(key_inp, "_field", "key")
            key_inp.textChanged.connect(lambda t, i=key_inp:
                self._current_config.__setitem__(i._field, t))
            row_ly.addWidget(key_inp, 1)

            rec_btn = QPushButton("录制")
            rec_btn.setStyleSheet("QPushButton{background:#fef3c7;border:1px solid #f59e0b;border-radius:3px;padding:3px 8px;font-size:10px;}QPushButton:hover{background:#fde68a;}")
            rec_btn.clicked.connect(lambda: self._record_key(key_inp))
            row_ly.addWidget(rec_btn)
            self._form.addRow("按键:", row_w)

        if "text" in config:
            self._form.addRow("文本:", self._make_input("text",
                                  config.get("text", "")))

        if "msg" in config:
            self._form.addRow("消息:", self._make_input("msg",
                                  config.get("msg", "")))

        if "keys" in config:
            row_w = QWidget()
            row_ly = QHBoxLayout(row_w)
            row_ly.setContentsMargins(0, 0, 0, 0)
            row_ly.setSpacing(4)

            keys_str = ",".join(config.get("keys", []))
            keys_inp = QLineEdit(keys_str)
            keys_inp.setStyleSheet(self._input_style())
            keys_inp.setPlaceholderText("按录制或输入，逗号分隔")
            setattr(keys_inp, "_field", "keys")
            keys_inp.textChanged.connect(lambda t, i=keys_inp:
                self._current_config.__setitem__(i._field,
                    [k.strip() for k in t.split(",") if k.strip()]))
            row_ly.addWidget(keys_inp, 1)

            rec_btn = QPushButton("录制")
            rec_btn.setStyleSheet("QPushButton{background:#fef3c7;border:1px solid #f59e0b;border-radius:3px;padding:3px 8px;font-size:10px;}QPushButton:hover{background:#fde68a;}")
            rec_btn.clicked.connect(lambda: self._record_keys(keys_inp))
            row_ly.addWidget(rec_btn)
            self._form.addRow("组合键:", row_w)

        if "keyword" in config:
            self._form.addRow("关键词:",
                self._make_input("keyword", config.get("keyword", "")))

        # Composite node fields
        if "count" in config:
            spin = QSpinBox()
            spin.setRange(1, 100)
            spin.setValue(config.get("count", 3))
            self._form.addRow("重试次数:", spin)
            setattr(spin, "_field", "count")
            spin.valueChanged.connect(lambda v, s=spin:
                self._current_config.__setitem__(s._field, v))

        if node_type == "timeout":
            spin = QSpinBox()
            spin.setRange(1, 3600)
            spin.setValue(config.get("seconds", 30))
            self._form.addRow("超时(s):", spin)
            setattr(spin, "_field", "seconds")
            spin.valueChanged.connect(lambda v, s=spin:
                self._current_config.__setitem__(s._field, v))

        self.setVisible(True)

    def _make_input(self, field: str, default: str = "") -> QLineEdit:
        inp = QLineEdit(str(default))
        inp.setStyleSheet("""
            QLineEdit { border:1px solid #d1d5db; border-radius:3px;
                padding:4px 8px; font-size:11px; min-height:22px; }
            QLineEdit:focus { border-color:#3b82f6; }
        """)
        setattr(inp, "_field", field)
        inp.textChanged.connect(lambda t, i=inp:
            self._current_config.__setitem__(i._field, t))
        return inp

    def _input_style(self):
        return "QLineEdit{border:1px solid #d1d5db;border-radius:3px;padding:4px 8px;font-size:11px;min-height:22px;}QLineEdit:focus{border-color:#3b82f6;}"

    def _pick_template(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "选择截图", "", "PNG图片 (*.png)")
        if not path:
            return

        import shutil
        basename = os.path.basename(path)
        name_no_ext = os.path.splitext(basename)[0]

        # Copy to template dir if available
        if self._template_dir:
            os.makedirs(self._template_dir, exist_ok=True)
            dest = os.path.join(self._template_dir, basename)
            if path != dest:
                shutil.copy2(path, dest)
            self._current_config["template"] = name_no_ext
        else:
            self._current_config["template"] = name_no_ext

        # Refresh display
        self.show_properties(self._current_node_id, self._current_config)

    def _capture_screen(self):
        """Minimize and let user select region, save as template screenshot."""
        import uuid
        screen_name = f"tpl_{uuid.uuid4().hex[:8]}"

        # Use a dialog-based region selector
        try:
            from PySide6.QtWidgets import QApplication
            # Minimize all windows
            for w in QApplication.topLevelWidgets():
                if w.isVisible():
                    w.showMinimized()

            # Small delay for windows to minimize
            import time
            time.sleep(0.3)

            # Full screen screenshot using PIL/Pillow
            try:
                import numpy as np
                from PIL import ImageGrab
                img = ImageGrab.grab()
                arr = np.array(img)
            except ImportError:
                from PySide6.QtGui import QScreen, QPixmap
                screen = QApplication.primaryScreen()
                pix = screen.grabWindow(0)
                img = pix.toImage()
                arr = None

            # TODO: region selection overlay — for now, capture full screen
            # and save with a generated name
            if self._template_dir:
                os.makedirs(self._template_dir, exist_ok=True)
                dest = os.path.join(self._template_dir, f"{screen_name}.png")
                if arr is not None:
                    from PIL import Image
                    Image.fromarray(arr).save(dest)
                else:
                    img.save(dest)
                self._current_config["template"] = screen_name
                self.show_properties(self._current_node_id, self._current_config)
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "截取失败", f"屏幕截取出错: {e}")

    def _record_key(self, input_widget: QLineEdit):
        """Record a single keypress into the input field."""
        input_widget.setText("按下任意键...")
        input_widget.setFocus()

        def on_key(event):
            key_name = event.text()
            if not key_name:
                key_name = event.key()
                # Map common special keys
                key_map = {
                    0x01000020: "shift", 0x01000021: "ctrl",
                    0x01000022: "alt",   0x01000023: "alt",
                    0x01000013: "enter", 0x01000001: "tab",
                    0x01000003: "backspace", 0x01000010: "esc",
                    0x01000030: "up", 0x01000031: "down",
                    0x01000032: "left", 0x01000033: "right",
                }
                key_name = key_map.get(event.key(), f"key_{event.key()}")
            input_widget.setText(key_name)
            self._current_config["key"] = key_name
            input_widget.keyPressEvent = None  # Stop recording
            return True

        input_widget.keyPressEvent = on_key

    def _record_keys(self, input_widget: QLineEdit):
        """Record multiple keypresses (combo) into the input field."""
        keys = []
        input_widget.setText("按下组合键 (Esc结束)...")
        input_widget.setFocus()

        def on_key(event):
            if event.key() == 0x01000010:  # Esc
                result = ",".join(keys)
                input_widget.setText(result)
                self._current_config["keys"] = keys
                input_widget.keyPressEvent = None
                return True
            key_name = event.text()
            if key_name and key_name not in keys:
                keys.append(key_name.lower())
            input_widget.setText(",".join(keys))
            return True

        input_widget.keyPressEvent = on_key

    def _apply_example(self, example_str: str):
        """Parse an example string and fill values into config, then refresh UI.

        Parses patterns like:  cmd="start msedge"  keys=["ctrl","c"]
        threshold=0.8  timeout=30
        """
        import re

        # Match key="value" and key=[list] patterns
        pairs = re.findall(
            r'(\w[\w_]*)=(?:"([^"]*)"|\[([^\]]*)\]|(\S+))',
            example_str)

        for key, str_val, list_val, bare_val in pairs:
            if str_val:
                self._current_config[key] = str_val
            elif list_val:
                # Parse list: ["a","b"] -> ["a", "b"]
                items = [x.strip().strip('"') for x in list_val.split(",") if x.strip()]
                self._current_config[key] = items
            elif bare_val:
                # Bare value (number, True/False)
                if bare_val.lower() == "true":
                    self._current_config[key] = True
                elif bare_val.lower() == "false":
                    self._current_config[key] = False
                else:
                    try:
                        self._current_config[key] = int(bare_val)
                    except ValueError:
                        try:
                            self._current_config[key] = float(bare_val)
                        except ValueError:
                            self._current_config[key] = bare_val

        # Re-render form with updated config (preserves current node selection)
        if self._current_node_id:
            self.show_properties(self._current_node_id, dict(self._current_config))

    def _apply(self):
        if self._current_node_id:
            self.propertyChanged.emit(self._current_node_id,
                                     dict(self._current_config))


# ---------------------------------------------------------------------------
# FlowEditor -- the complete editor widget
# ---------------------------------------------------------------------------

class FlowEditor(QWidget):
    """Complete visual flow editor: graph view + property panel."""

    taskEdited = Signal(str, dict)  # filename, updated_data

    def __init__(self):
        super().__init__()

        ly = QHBoxLayout(self)
        ly.setContentsMargins(0, 0, 0, 0)
        ly.setSpacing(0)

        # ═══ Left: node palette ═══
        self._palette = NodePalettePanel()
        self._palette.nodeRequested.connect(self._add_node_by_type)
        ly.addWidget(self._palette)

        # ═══ Center: toolbar + graph ═══
        left_w = QWidget()
        left_ly = QVBoxLayout(left_w)
        left_ly.setContentsMargins(0, 0, 0, 0)
        left_ly.setSpacing(4)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 6, 8, 6)
        toolbar.setSpacing(6)

        fit_btn = QPushButton("适应")
        fit_btn.clicked.connect(self._fit_view)
        fit_btn.setStyleSheet(self._btn_style())
        toolbar.addWidget(fit_btn)

        reset_btn = QPushButton("重置")
        reset_btn.clicked.connect(self._reset_view)
        reset_btn.setStyleSheet(self._btn_style())
        toolbar.addWidget(reset_btn)

        opt_btn = QPushButton("优化布局")
        opt_btn.clicked.connect(self._optimize_layout)
        opt_btn.setStyleSheet(self._btn_style())
        toolbar.addWidget(opt_btn)

        und_btn = QPushButton("↶")
        und_btn.setToolTip("撤销 (Ctrl+Z)")
        und_btn.clicked.connect(self._undo)
        und_btn.setStyleSheet(self._btn_style())
        und_btn.setFixedWidth(32)
        toolbar.addWidget(und_btn)
        self._undo_btn = und_btn

        red_btn = QPushButton("↷")
        red_btn.setToolTip("重做 (Ctrl+Y)")
        red_btn.clicked.connect(self._redo)
        red_btn.setStyleSheet(self._btn_style())
        red_btn.setFixedWidth(32)
        toolbar.addWidget(red_btn)
        self._redo_btn = red_btn

        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._save)
        save_btn.setStyleSheet(self._btn_style().replace("#f3f4f6", "#dbeafe").replace("#374151", "#1d4ed8"))
        toolbar.addWidget(save_btn)

        toolbar.addStretch()

        zoom_label = QLabel("100%")
        zoom_label.setStyleSheet("font-size:11px; color:#6b7280;")
        toolbar.addWidget(zoom_label)
        self._zoom_label = zoom_label

        left_ly.addLayout(toolbar)

        # Flow view
        self._scene = FlowScene()
        self._view = FlowView(self._scene)
        self._view._on_zoom = lambda z: self._zoom_label.setText(f"{z}%")
        left_ly.addWidget(self._view, 1)

        ly.addWidget(left_w, 1)

        # ═══ Right: property editor ═══
        self._prop_editor = PropertyEditor()
        self._prop_editor.propertyChanged.connect(self._on_property_changed)
        ly.addWidget(self._prop_editor)

        # Connect signals
        self._scene.nodeSelected.connect(self._on_node_selected)
        self._scene.nodeDoubleClicked.connect(self._on_node_double_clicked)

        # Delete key handling
        self._view.installEventFilter(self)
        self.setFocusPolicy(Qt.StrongFocus)

        self._tasks_data: dict = {}
        self._entry: str = ""
        self._bt_root: dict = None
        self._format: str = "flat"
        self._current_file: str = ""  # path to saved file

    def _btn_style(self):
        return """
            QPushButton { background:#f3f4f6; color:#374151; border:1px solid #d1d5db;
                border-radius:4px; padding:4px 10px; font-size:11px; min-height:22px; }
            QPushButton:hover { background:#e5e7eb; }
        """

    def _fit_view(self):
        self._view.fit_all()
        z = int(self._view._zoom * 100)
        self._zoom_label.setText(f"{z}%")

    def _reset_view(self):
        self._view.reset_view()
        z = int(self._view._zoom * 100)
        self._zoom_label.setText(f"{z}%")

    def load_flat_tasks(self, tasks: dict, entry: str):
        """Load from flat task format {TaskA: {action, next, ...}, ...}"""
        self._format = "flat"
        self._tasks_data = tasks
        self._entry = entry
        self._scene.auto_layout(tasks, entry)
        self._view.fit_all()

    def load_bt_tree(self, root: dict):
        """Load from behavior tree JSON."""
        self._format = "bt"
        self._bt_root = root
        self._tasks_data = {}
        self._scene.load_bt_tree(root)
        self._view.fit_all()

    def _optimize_layout(self):
        """Re-run auto-layout on current nodes (after user manual adjustments)."""
        if self._format == "bt" and self._bt_root:
            self._scene.load_bt_tree(self._bt_root)
            self._view.fit_all()
        elif self._format == "flat" and self._tasks_data:
            self._scene.auto_layout(self._tasks_data, self._entry)
            self._view.fit_all()

    def _on_node_selected(self, config: dict):
        pass  # Selection-only, no property display

    def _on_node_double_clicked(self, config: dict):
        # Find the node in tasks_data by matching config
        for nid, node in self._scene._nodes.items():
            if node.config == config:
                self._prop_editor.show_properties(nid, config)
                break

    def _on_property_changed(self, node_id: str, config: dict):
        # Update the node's config
        node = self._scene.get_node(node_id)
        if node:
            node.config = config
            node._name = config.get("desc", node_id)
            node.node_type = config.get("action", config.get("type", node.node_type))
            node._bg = TYPE_COLORS.get(node.node_type, C_NODE_ACTION)
            node.update()
            self._scene._update_arrows()

            # Update tasks_data
            if node_id in self._tasks_data:
                self._tasks_data[node_id].update(config)

    def _add_node_by_type(self, node_type: str):
        """Add a new node of given type to the center of the canvas."""
        import uuid
        nid = f"node_{uuid.uuid4().hex[:6]}"
        name = node_type

        # Default config per type
        defaults = {
            "click": {"action": "click", "desc": "点击", "template": "", "threshold": 0.8},
            "move": {"action": "move", "desc": "移动", "template": "", "threshold": 0.8},
            "swipe": {"action": "swipe", "desc": "滑动", "from": [0, 0], "to": [100, 100]},
            "press": {"action": "press", "desc": "按键", "key": ""},
            "type": {"action": "type", "desc": "输入", "text": ""},
            "hotkey": {"action": "hotkey", "desc": "组合键", "keys": []},
            "wait": {"action": "wait", "desc": "等待", "seconds": 1},
            "wait_until": {"action": "wait_until", "desc": "等到出现", "template": "", "timeout": 30},
            "find": {"action": "find", "desc": "查找", "template": "", "threshold": 0.8},
            "find_text": {"action": "find_text", "desc": "识字", "keyword": ""},
            "find_color": {"action": "find_color", "desc": "颜色检测", "target": [255, 0, 0]},
            "exec": {"action": "exec", "desc": "执行命令", "cmd": ""},
            "set_var": {"action": "set_var", "desc": "设置变量", "name": "", "value": ""},
            "log": {"action": "log", "desc": "日志", "msg": ""},
            "sequence": {"type": "sequence", "name": "顺序", "children": []},
            "selector": {"type": "selector", "name": "选择", "children": []},
            "retry": {"type": "retry", "name": "重试", "count": 3, "child": None},
            "timeout": {"type": "timeout", "name": "超时", "seconds": 30, "child": None},
            "repeat": {"type": "repeat", "name": "循环", "child": None},
        }

        config = defaults.get(node_type, {"action": node_type, "desc": node_type})

        # Place at center of visible area
        vr = self._view.mapToScene(self._view.viewport().rect()).boundingRect()
        cx = vr.center().x() - NODE_W / 2
        cy = vr.center().y() - NODE_H / 2

        node = self._scene.add_node(nid, name, node_type, config, cx, cy, record_undo=True)

        # If we're in BT format, update _bt_root
        if self._format == "bt":
            # Just mark this as a dangling node
            self._bt_root = config

    def _save(self):
        """Save current tree to file."""
        if not self._current_file:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "提示", "请先在顶部下拉框选择一个任务再保存")
            return

        # Build BT dict from scene
        if self._format == "bt" and self._bt_root:
            bt_dict = {"_meta": {
                "name": self._bt_root.get("name", ""),
                "window": "",
                "retry_on_failure": 0,
                "global_timeout": 0,
                "modified": "",
            }}
            bt_dict["root"] = self._scene_to_dict()
        else:
            bt_dict = {"_meta": {"name": "", "modified": ""}}
            bt_dict["root"] = self._scene_to_dict()

        # Preserve existing meta if loading from file
        try:
            import json as _json
            with open(self._current_file, encoding="utf-8") as f:
                old = _json.load(f)
            old_meta = old.get("_meta", {})
            bt_dict["_meta"].update({k: v for k, v in old_meta.items()
                                     if k not in ("modified",)})
        except Exception:
            pass

        import datetime, json as _json
        bt_dict["_meta"]["modified"] = datetime.datetime.now().isoformat()

        with open(self._current_file, "w", encoding="utf-8") as f:
            _json.dump(bt_dict, f, ensure_ascii=False, indent=2)

        # Emit signal for parent to refresh
        self.taskEdited.emit(self._current_file, bt_dict)
        self._bt_root = bt_dict.get("root", {})

    def _scene_to_dict(self) -> dict:
        """Convert current scene nodes to a BT JSON dict."""
        nodes = self._scene._nodes
        if not nodes:
            return {}

        # Find roots (nodes with no incoming connections)
        targets = set()
        for arrow in self._scene._arrows:
            targets.add(arrow.target.node_id)
        roots = [n for nid, n in nodes.items() if nid not in targets]

        if not roots:
            return {}

        def node_to_dict(node: FlowNode) -> dict:
            d = {"type": node.node_type, "name": node._name}
            d.update({k: v for k, v in node.config.items()
                     if k not in ("type", "name", "desc", "action")})

            # Find children via arrows
            out_arrows = [a for a in self._scene._arrows if a.source.node_id == node.node_id]
            if out_arrows:
                children = []
                for a in out_arrows:
                    child_dict = node_to_dict(a.target)
                    children.append(child_dict)
                if node.node_type in ("sequence", "selector"):
                    d["children"] = children
                else:
                    d["child"] = children[0] if children else None
            return d

        if len(roots) == 1:
            return node_to_dict(roots[0])
        else:
            return {"type": "sequence", "name": "root",
                    "children": [node_to_dict(r) for r in roots]}

    def set_current_file(self, path: str):
        self._current_file = path
        # Set template directory for screenshot association
        tpl_dir = os.path.join(os.path.dirname(path), "templates")
        if os.path.isdir(tpl_dir):
            self._prop_editor._template_dir = tpl_dir

    def eventFilter(self, obj, event):
        """Handle delete key and Ctrl+Z/Y shortcuts."""
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Delete:
                self._scene.delete_selected()
                return True
            if event.key() == Qt.Key_Z and event.modifiers() == Qt.ControlModifier:
                self._undo()
                return True
            if event.key() == Qt.Key_Y and event.modifiers() == Qt.ControlModifier:
                self._redo()
                return True
        return super().eventFilter(obj, event)

    def _undo(self):
        self._scene.undo()

    def _redo(self):
        self._scene.redo()

    def clear(self):
        self._scene.clear_all()
        self._prop_editor.setVisible(False)
        self._tasks_data = {}
        self._current_file = ""
