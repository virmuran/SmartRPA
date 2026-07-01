"""Visual flow editor for behavior trees and task graphs.

Powered by QGraphicsView. Renders task nodes as boxes connected by
directed arrows. Supports zoom, pan, double-click editing.
"""

from math import atan2, pi, sin, cos
from typing import Dict, List, Optional, Tuple

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
    QGraphicsEllipseItem, QWidget, QVBoxLayout, QHBoxLayout,
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
    "find_text":   "OCR",
    "find_color":  "🎨",
    "if":          "?",
    "exec":        "▶",
    "hotkey":      "⌨+",
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


# ---------------------------------------------------------------------------
# FlowNode -- a single task/action box
# ---------------------------------------------------------------------------

class FlowNode(QGraphicsRectItem):
    """A node in the flow graph. Stores task config data."""

    nodeDoubleClicked = Signal(dict)   # config dict
    nodeSelected = Signal(dict)

    def __init__(self, node_id: str, name: str, node_type: str = "action",
                 config: dict = None, x: float = 0, y: float = 0):
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

        # Ports indicators (small circles at edges)
        if self._hovered or self.isSelected():
            painter.setPen(Qt.NoPen)
            # Success port (right, upper half)
            painter.setBrush(C_SUCCESS)
            painter.drawEllipse(QPointF(NODE_W, NODE_H * 0.33), 5, 5)
            # Failure port (right, lower half)
            painter.setBrush(C_FAILURE)
            painter.drawEllipse(QPointF(NODE_W, NODE_H * 0.67), 5, 5)

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
        self.nodeDoubleClicked.emit(self.config)
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.nodeSelected.emit(self.config)
        super().mousePressEvent(event)

    def itemChange(self, change, value):
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
                 config: dict = None, x: float = 0, y: float = 0) -> FlowNode:
        """Add a node to the scene."""
        node = FlowNode(node_id, name, node_type, config, x, y)
        node.nodeDoubleClicked.connect(self.nodeDoubleClicked.emit)
        node.nodeSelected.connect(self.nodeSelected.emit)
        self.addItem(node)
        self._nodes[node_id] = node
        return node

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
        self.clear_all()

        # Topological depth calculation
        depths: Dict[str, int] = {}
        visited = set()

        def calc_depth(node_id: str, depth: int):
            if node_id is None or node_id in visited:
                return
            if depth > depths.get(node_id, -1):
                depths[node_id] = depth
            task = tasks.get(node_id, {})
            for next_id in (task.get("next") or []):
                calc_depth(next_id, depth + 1)
            for next_id in (task.get("onErrorNext") or []):
                calc_depth(next_id, depth + 1)

        visited.clear()
        calc_depth(entry, 0)

        # For nodes not reachable, assign depth 0
        for nid in tasks:
            if nid not in depths:
                depths[nid] = 0

        # Group nodes by depth
        layers: Dict[int, List[str]] = {}
        for nid, d in depths.items():
            layers.setdefault(d, []).append(nid)

        # Position nodes
        max_depth = max(layers.keys()) if layers else 0
        for depth in sorted(layers.keys()):
            nodes = layers[depth]
            n_count = len(nodes)
            total_w = n_count * (NODE_W + H_GAP) - H_GAP

            for i, nid in enumerate(nodes):
                task = tasks.get(nid, {})
                name = task.get("desc", nid)
                action = task.get("action", "click")
                x = (max_depth * (NODE_W + H_GAP) - total_w) / 2 + i * (NODE_W + H_GAP) + 40
                y = 40 + depth * (NODE_H + V_GAP)
                self.add_node(nid, name, action, task, x, y)

        # Draw arrows
        for nid, task in tasks.items():
            for next_id in (task.get("next") or []):
                if next_id in self._nodes:
                    self.connect_nodes(nid, next_id, success=True)
            for next_id in (task.get("onErrorNext") or []):
                if next_id in self._nodes:
                    self.connect_nodes(nid, next_id, success=False)

        # Auto-fit
        items_rect = self.itemsBoundingRect().adjusted(-40, -40, 40, 40)
        self.setSceneRect(items_rect)

    def load_bt_tree(self, root: dict):
        """Load from a behavior-tree JSON structure.

        root: {"type": "sequence", "name": "...", "children": [...]}
        """
        self.clear_all()

        def add_tree_node(node_dict: dict, parent_id: Optional[str],
                         x: float, y: float) -> str:
            node_type = node_dict.get("type", "action")
            name = node_dict.get("name", node_type)
            node_id = name or f"node_{len(self._nodes)}"
            # Ensure unique ID
            base_id = node_id
            counter = 1
            while node_id in self._nodes:
                node_id = f"{base_id}_{counter}"
                counter += 1

            self.add_node(node_id, name, node_type, node_dict, x, y)

            if parent_id:
                self.connect_nodes(parent_id, node_id, success=True)

            # Handle composite nodes
            children = node_dict.get("children", [])
            child_node = node_dict.get("child")

            if children:
                child_y = y + NODE_H + V_GAP
                child_count = len(children)
                total_w = child_count * (NODE_W + H_GAP) - H_GAP
                start_x = x - total_w / 2 + NODE_W / 2
                for i, child in enumerate(children):
                    cx = start_x + i * (NODE_W + H_GAP)
                    add_tree_node(child, node_id, cx, child_y)

            if child_node:
                child_y = y + NODE_H + V_GAP
                add_tree_node(child_node, node_id, x, child_y)

            return node_id

        add_tree_node(root, None, 400, 40)

        # Auto-fit
        items_rect = self.itemsBoundingRect().adjusted(-40, -40, 40, 40)
        self.setSceneRect(items_rect)

    def get_node(self, node_id: str) -> Optional[FlowNode]:
        return self._nodes.get(node_id)


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
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setBackgroundBrush(QColor("#fafafa"))
        self.setFrameShape(QFrame.NoFrame)

        self._zoom = 1.0
        self._min_zoom = 0.15
        self._max_zoom = 3.0

    def wheelEvent(self, event: QWheelEvent):
        factor = 1.15
        if event.angleDelta().y() < 0:
            factor = 1.0 / factor

        new_zoom = self._zoom * factor
        if self._min_zoom <= new_zoom <= self._max_zoom:
            self._zoom = new_zoom
            self.scale(factor, factor)

    def fit_all(self):
        self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)
        self._zoom = self.transform().m11()

    def reset_view(self):
        self.resetTransform()
        self._zoom = 1.0
        self.fit_all()


# ---------------------------------------------------------------------------
# PropertyEditor -- right panel for editing node properties
# ---------------------------------------------------------------------------

class PropertyEditor(QWidget):
    """Panel showing editable properties for the selected node."""

    propertyChanged = Signal(str, dict)  # node_id, updated_config

    def __init__(self):
        super().__init__()
        self._current_node_id: Optional[str] = None
        self._current_config: dict = {}

        self.setMinimumWidth(240)
        self.setMaximumWidth(320)

        ly = QVBoxLayout(self)
        ly.setContentsMargins(0, 0, 0, 0)
        ly.setSpacing(8)

        # Title
        self._title = QLabel("属性")
        self._title.setStyleSheet(
            "font-size:13px; font-weight:600; color:#374151; "
            "padding:8px 12px; background:#f9fafb; border-radius:4px;")
        ly.addWidget(self._title)

        # Scroll area for properties
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")

        form_w = QWidget()
        self._form = QFormLayout(form_w)
        self._form.setContentsMargins(12, 8, 12, 8)
        self._form.setSpacing(8)
        scroll.setWidget(form_w)
        ly.addWidget(scroll, 1)

        self._form_w = form_w

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

        self.setVisible(False)

    def _clear_form(self):
        while self._form.rowCount() > 0:
            self._form.removeRow(0)

    def show_properties(self, node_id: str, config: dict):
        """Display properties for the given node."""
        self._current_node_id = node_id
        self._current_config = dict(config)
        self._clear_form()

        node_type = config.get("action", config.get("type", "action"))
        self._title.setText(f"属性 — {node_type}")

        self._form.addRow("名称:", self._make_input("desc",
                              config.get("desc", node_id)))
        self._form.addRow("类型:", QLabel(node_type))

        # Action-specific fields
        if "template" in config:
            self._form.addRow("模板:", self._make_input("template",
                                  config.get("template", "")))

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
            self._form.addRow("按键:", self._make_input("key",
                                  config.get("key", "")))

        if "text" in config:
            self._form.addRow("文本:", self._make_input("text",
                                  config.get("text", "")))

        if "msg" in config:
            self._form.addRow("消息:", self._make_input("msg",
                                  config.get("msg", "")))

        if "keys" in config:
            self._form.addRow("组合键:",
                self._make_input("keys", ",".join(config.get("keys", []))))

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

        # Left: toolbar + graph
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

        toolbar.addStretch()

        zoom_label = QLabel("100%")
        zoom_label.setStyleSheet("font-size:11px; color:#6b7280;")
        toolbar.addWidget(zoom_label)
        self._zoom_label = zoom_label

        left_ly.addLayout(toolbar)

        # Flow view
        self._scene = FlowScene()
        self._view = FlowView(self._scene)
        self._view.wheelEvent = self._make_wheel_event(self._view.wheelEvent)
        left_ly.addWidget(self._view, 1)

        ly.addWidget(left_w, 1)

        # Right: property editor
        self._prop_editor = PropertyEditor()
        self._prop_editor.propertyChanged.connect(self._on_property_changed)
        ly.addWidget(self._prop_editor)

        # Connect signals
        self._scene.nodeSelected.connect(self._on_node_selected)
        self._scene.nodeDoubleClicked.connect(self._on_node_double_clicked)

        self._tasks_data: dict = {}
        self._entry: str = ""

    def _btn_style(self):
        return """
            QPushButton { background:#f3f4f6; color:#374151; border:1px solid #d1d5db;
                border-radius:4px; padding:4px 10px; font-size:11px; min-height:22px; }
            QPushButton:hover { background:#e5e7eb; }
        """

    def _make_wheel_event(self, orig):
        def wrapper(event):
            orig(event)
            z = int(self._view._zoom * 100)
            self._zoom_label.setText(f"{z}%")
        return wrapper

    def _fit_view(self):
        self._view.fit_all()

    def _reset_view(self):
        self._view.reset_view()

    def load_flat_tasks(self, tasks: dict, entry: str):
        """Load from flat task format {TaskA: {action, next, ...}, ...}"""
        self._tasks_data = tasks
        self._entry = entry
        self._scene.auto_layout(tasks, entry)
        self._view.fit_all()

    def load_bt_tree(self, root: dict):
        """Load from behavior tree JSON."""
        self._scene.load_bt_tree(root)
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

    def clear(self):
        self._scene.clear_all()
        self._prop_editor.setVisible(False)
        self._tasks_data = {}
