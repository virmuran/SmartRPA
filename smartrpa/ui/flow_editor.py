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
                 config: dict = None, x: float = 0, y: float = 0) -> FlowNode:
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
        return node

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
        self.clear_all()

        # Topological depth calculation (handles cycles via back-edge detection)
        depths: Dict[str, int] = {}
        visiting = set()

        def calc_depth(node_id: str, depth: int):
            if node_id is None or node_id in visiting:
                return  # Cycle detected, don't recurse
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
        """Load from a behavior-tree JSON structure with smart auto-layout.

        Uses bottom-up width calculation so parent nodes are centered
        over their children. No overlapping, arrows are straight-ish.
        """
        self.clear_all()

        # 1. Pre-calculate subtree widths (bottom-up)
        def subtree_width(node_dict: dict) -> float:
            children = node_dict.get("children", [])
            child = node_dict.get("child")
            if child:
                children = list(children) + [child]
            if not children:
                return NODE_W + H_GAP  # leaf: room for its own width + spacing
            w = sum(subtree_width(c) for c in children)
            return w

        # 2. Place nodes top-down using subtree widths
        def place(node_dict: dict, start_x: float, y: float,
                  parent_id: Optional[str] = None):
            node_type = node_dict.get("type", "action")
            name = node_dict.get("name", node_type)
            node_id = name or f"node_{len(self._nodes)}"
            base_id = node_id
            counter = 1
            while node_id in self._nodes:
                node_id = f"{base_id}_{counter}"
                counter += 1

            # Parent centered in its allocated width
            w = subtree_width(node_dict)
            x = start_x + w / 2 - NODE_W / 2
            self.add_node(node_id, name, node_type, node_dict, x, y)

            if parent_id:
                self.connect_nodes(parent_id, node_id, success=True)

            # Children
            children = node_dict.get("children", [])
            child = node_dict.get("child")
            if child:
                children = list(children) + [child]
            if children:
                child_y = y + NODE_H + V_GAP
                cx = start_x
                for c in children:
                    cw = subtree_width(c)
                    place(c, cx, child_y, node_id)
                    cx += cw

            return node_id

        root_width = subtree_width(root)
        place(root, 0, 40)

        # Center the view on root (suppress snap while doing layout)
        for node in self._nodes.values():
            node._layout_mode = True

        self._clear_guides()  # ensure no stray guides affect bounding rect
        items_rect = self.itemsBoundingRect().adjusted(-40, -40, 40, 40)
        self.setSceneRect(items_rect)

        center_x = items_rect.width() / 2 - root_width / 2
        if center_x > 40:
            dx = 40 - center_x
            for node in self._nodes.values():
                node.setX(node.x() + dx)

        for node in self._nodes.values():
            node._layout_mode = False

    def delete_selected(self):
        """Remove selected nodes and their connections."""
        to_remove = [n for n in self._nodes.values() if n.isSelected()]
        if not to_remove:
            # Try to remove selected arrows
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

        for node in to_remove:
            # Remove connected arrows
            for a in list(self._arrows):
                if a.source is node or a.target is node:
                    if a in self._arrows:
                        self.removeItem(a)
                        self._arrows.remove(a)
            # Remove node
            del self._nodes[node.node_id]
            self.removeItem(node)

        self._update_arrows()

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
        ("⌨+ 组合键", "hotkey"),
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

        node = self._scene.add_node(nid, name, node_type, config, cx, cy)

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

    def eventFilter(self, obj, event):
        """Handle delete key to remove selected nodes."""
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Delete:
            self._scene.delete_selected()
            return True
        return super().eventFilter(obj, event)

    def clear(self):
        self._scene.clear_all()
        self._prop_editor.setVisible(False)
        self._tasks_data = {}
        self._current_file = ""
