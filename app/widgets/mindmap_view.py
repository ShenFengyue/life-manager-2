"""思维导图视图：XMind 逻辑图风格的卡片与连线。

交互约定：
    左键单击卡片 → 打开记录窗口（不点击就不会产生任何数据）
    右键卡片     → 节点菜单（改结构、置顶、归档、删除…）
    滚轮         → 上下滚动；Ctrl + 滚轮 → 缩放；中键拖动 → 平移
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsObject,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsView,
    QStyleOptionGraphicsItem,
    QWidget,
)

from .. import theme
from ..mindmap import Layout, Placement
from .common import log_cursor


@dataclass(frozen=True)
class CardData:
    """一张卡片的展示内容。"""

    node_id: str
    title: str
    subtitle: str
    kind: str  # area | process | thread
    color: str
    pinned: bool = False
    archived: bool = False
    tooltip: str = ""
    today_count: int = 0


class MindMapCard(QGraphicsObject):
    """一个节点卡片。"""

    RADIUS = 9.0

    def __init__(self, data: CardData, placement: Placement, view: "MindMapView") -> None:
        super().__init__()
        self.data = data
        self.placement = placement
        self._view = view
        self._hovered = False
        self._pressed = False
        self.setPos(placement.x, placement.y)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setZValue(2)
        if data.tooltip:
            self.setToolTip(data.tooltip)
        self._title_font = QFont()
        self._title_font.setPointSize(10)
        self._title_font.setBold(True)
        self._subtitle_font = QFont()
        self._subtitle_font.setPointSize(8)

    # ------------------------------------------------------------ 绘制
    def boundingRect(self) -> QRectF:  # pragma: no cover - Qt 覆写
        return QRectF(0, 0, self.placement.width, self.placement.height)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget=None) -> None:  # pragma: no cover
        rect = self.boundingRect().adjusted(0.5, 0.5, -0.5, -0.5)
        accent = QColor(self.data.color)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        if self.data.kind == "area":
            background = QColor(accent)
            background.setAlpha(26)
            border = accent if self._hovered else QColor(accent)
            border.setAlpha(150 if not self._hovered else 255)
        else:
            background = QColor(theme.BG if not self.data.archived else theme.SURFACE)
            border = accent if self._hovered else QColor(theme.BORDER)

        painter.setBrush(QBrush(background))
        pen = QPen(border)
        pen.setWidthF(1.6 if self._hovered else 1.0)
        painter.setPen(pen)
        painter.drawRoundedRect(rect, self.RADIUS, self.RADIUS)

        if self.data.kind != "area":
            # 左侧色条：颜色来自所属领域
            bar = QRectF(rect.left() + 1, rect.top() + 6, 3.0, rect.height() - 12)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(accent))
            painter.drawRoundedRect(bar, 1.5, 1.5)

        padding_left = 12.0 if self.data.kind == "area" else 14.0
        available = rect.width() - padding_left - 30

        painter.setFont(self._title_font)
        painter.setPen(QPen(QColor(theme.TEXT if not self.data.archived else theme.TEXT_MUTED)))
        metrics = QFontMetrics(self._title_font)
        title = metrics.elidedText(self.data.title, Qt.TextElideMode.ElideRight, int(available))
        painter.drawText(
            QRectF(rect.left() + padding_left, rect.top() + 7, available, 16),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            title,
        )

        painter.setFont(self._subtitle_font)
        sub_metrics = QFontMetrics(self._subtitle_font)
        subtitle_rect = QRectF(
            rect.left() + padding_left, rect.top() + 24, rect.width() - padding_left - 8, 14
        )
        subtitle = sub_metrics.elidedText(
            self.data.subtitle, Qt.TextElideMode.ElideRight, int(subtitle_rect.width())
        )
        if self.data.today_count > 0:
            # 今天记过：在副标题左边点一个小绿点，扫一眼就知道哪些今天动过
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(theme.TODAY_DOT)))
            painter.drawEllipse(
                QRectF(
                    rect.left() + padding_left - 6,
                    subtitle_rect.top() + 4.5,
                    5.0,
                    5.0,
                )
            )
        painter.setPen(QPen(QColor(theme.TEXT_SUBTLE)))
        painter.drawText(
            subtitle_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            subtitle,
        )

        if self.data.pinned:
            painter.setFont(self._title_font)
            painter.setPen(QPen(QColor("#9a6700")))
            painter.drawText(
                QRectF(rect.right() - 24, rect.top() + 7, 16, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                "★",
            )

    # ------------------------------------------------------------ 交互
    def mousePressEvent(self, event) -> None:  # pragma: no cover - 需要 GUI
        # 必须显式接受按下事件：QGraphicsItem 的默认实现会忽略它，
        # 那样 Qt 不会把后续的抬起事件继续发给这张卡片，单击就会被吞掉。
        if event.button() == Qt.MouseButton.MiddleButton:
            # 中键单击 = 看这个节点的大热力图。
            # 这里不能直接弹窗口：在事件处理函数里 exec() 会嵌套事件循环、把这次点击的状态卡住，
            # 手感上就变成"要点两下才开"。推迟到当前事件处理结束之后再弹。
            node_id = self.data.node_id
            event.accept()
            QTimer.singleShot(0, lambda: self._view.nodeHeatmapRequested.emit(node_id))
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            event.accept()
            return
        super().mousePressEvent(event)

    def hoverEnterEvent(self, event) -> None:  # pragma: no cover - 需要 GUI
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:  # pragma: no cover - 需要 GUI
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # pragma: no cover - 需要 GUI
        if event.button() == Qt.MouseButton.MiddleButton:
            # 吃掉中键的抬起，免得它落到画布上被当成"开始平移"
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton and self._pressed:
            self._pressed = False
            if self.contains(event.pos()):
                node_id = self.data.node_id
                # 同理：记录窗口也推迟到事件处理结束后再弹
                log_cursor("点击卡片")
                QTimer.singleShot(0, lambda: self._view.nodeActivated.emit(node_id))
            event.accept()
            return
        super().mouseReleaseEvent(event)


class MindMapView(QGraphicsView):
    """承载整张思维导图的画布。"""

    nodeActivated = Signal(str)
    nodeMenuRequested = Signal(str, QPoint)
    nodeHeatmapRequested = Signal(str)

    MIN_SCALE = 0.35
    MAX_SCALE = 2.2
    # 「适应窗口」的可读下限：节点多到一屏放不下时，宁可让用户滚动，
    # 也不要把字缩成看不清的一团。
    READABLE_SCALE = 0.8
    # 内容四周留出的可自由拖动余量（XMind 那种随手挪动画布的手感）
    MARGIN_RATIO = 0.6
    MIN_MARGIN = 280.0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing
        )
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setBackgroundBrush(QBrush(QColor(theme.PAGE_BG)))
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self._cards: dict[str, MindMapCard] = {}
        self._parent_of: dict[str, str | None] = {}
        self._panning = False
        self._pan_origin = QPoint()
        self._pan_distance = 0
        self._suppress_menu = False
        self._content_size = (0.0, 0.0)
        self._content_rect = QRectF()
        # 是否跟随窗口大小自动重新适应（用户手动缩放/平移后关闭）
        self._auto_fit = True

    # ------------------------------------------------------------ 构建
    def rebuild(self, cards: list[CardData], layout: Layout) -> None:
        """重建整张图，保留当前的缩放与滚动位置。"""
        scale = self.transform().m11()
        h_value = self.horizontalScrollBar().value()
        v_value = self.verticalScrollBar().value()

        self._scene.clear()
        self._cards = {}
        for data in cards:
            placement = layout.placements.get(data.node_id)
            if placement is None:
                continue
            card = MindMapCard(data, placement, self)
            self._scene.addItem(card)
            self._cards[data.node_id] = card

        palette = {data.node_id: data.color for data in cards}
        for child_id, placement in layout.placements.items():
            parent_id = self._parent_of.get(child_id)
            if not parent_id:
                continue
            parent = layout.placements.get(parent_id)
            if parent is None:
                continue
            self._scene.addItem(self._edge_item(parent, placement, palette.get(parent_id, theme.BORDER)))

        self._content_size = (layout.width, layout.height)
        self._content_rect = QRectF(0, 0, layout.width, layout.height)
        margin_x = max(self.MIN_MARGIN, layout.width * self.MARGIN_RATIO)
        margin_y = max(self.MIN_MARGIN, layout.height * self.MARGIN_RATIO)
        self._scene.setSceneRect(
            -margin_x, -margin_y, layout.width + margin_x * 2, layout.height + margin_y * 2
        )
        self.horizontalScrollBar().setValue(h_value)
        self.verticalScrollBar().setValue(v_value)
        if scale > 0:
            self.resetTransform()
            self.scale(scale, scale)

    def set_parent_map(self, parents: dict[str, str | None]) -> None:
        self._parent_of = parents

    def _edge_item(self, parent: Placement, child: Placement, color: str) -> QGraphicsPathItem:
        start = QPointF(parent.right, parent.center_y)
        end = QPointF(child.x, child.center_y)
        mid_x = start.x() + (end.x() - start.x()) * 0.5
        # 圆角折线（XMind 逻辑图那种），半径给足才看得出是圆角
        radius = min(18.0, abs(end.y() - start.y()) / 2 if end.y() != start.y() else 18.0)

        path = QPainterPath(start)
        if abs(end.y() - start.y()) < 1.0:
            path.lineTo(end)
        else:
            direction = 1.0 if end.y() > start.y() else -1.0
            path.lineTo(QPointF(mid_x, start.y()))
            path.quadTo(QPointF(mid_x, start.y()), QPointF(mid_x, start.y() + radius * direction))
            path.lineTo(QPointF(mid_x, end.y() - radius * direction))
            path.quadTo(QPointF(mid_x, end.y()), QPointF(mid_x + radius, end.y()))
            path.lineTo(end)
        item = QGraphicsPathItem(path)
        edge_color = QColor(color)
        edge_color.setAlpha(120)
        pen = QPen(edge_color)
        pen.setWidthF(1.4)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        item.setPen(pen)
        item.setZValue(1)
        return item

    # ------------------------------------------------------------ 视图
    def fit_to_window(self) -> None:
        if not self._cards:
            return
        self._auto_fit = True
        viewport = self.viewport().size()
        if viewport.width() <= 2 or viewport.height() <= 2:
            # 控件还没显示或尺寸无效时不做缩放，等真正显示后再适应。
            self.resetTransform()
            return
        self.resetTransform()
        target = self._content_rect.adjusted(-24.0, -24.0, 24.0, 24.0)
        self.fitInView(target, Qt.AspectRatioMode.KeepAspectRatio)
        # 内容比窗口小的时候允许适度放大，最多 1.25 倍，避免整屏留白。
        if self.transform().m11() > 1.25:
            self.resetTransform()
            self.scale(1.25, 1.25)
            self.centerOn(self._content_rect.center())
        elif self.transform().m11() < self.READABLE_SCALE:
            factor = self.READABLE_SCALE / self.transform().m11()
            self.scale(factor, factor)
            # 缩到下限后：横向居中，纵向从最上面一个领域开始，剩下的靠拖动/滚动查看。
            half_h = viewport.height() / (2 * self.READABLE_SCALE)
            self.centerOn(self._content_rect.center().x(), target.top() + half_h)

    def zoom_by(self, factor: float) -> None:
        self._auto_fit = False
        current = self.transform().m11()
        target = max(self.MIN_SCALE, min(self.MAX_SCALE, current * factor))
        if abs(target - current) < 1e-6:
            return
        self.scale(target / current, target / current)

    def wheelEvent(self, event) -> None:  # pragma: no cover - 需要 GUI
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom_by(1.12 if event.angleDelta().y() > 0 else 1 / 1.12)
            event.accept()
            return
        super().wheelEvent(event)

    def mousePressEvent(self, event) -> None:  # pragma: no cover - 需要 GUI
        button = event.button()
        if button == Qt.MouseButton.MiddleButton:
            # 中键只用来"看大热力图"（卡片自己处理）：
            # 落在卡片上交给图元，落在空白处什么也不做 —— 中键不再用于拖动画布。
            if self.card_at(event.position().toPoint()) is not None:
                super().mousePressEvent(event)
            else:
                event.accept()
            return
        if button == Qt.MouseButton.RightButton or (
            button == Qt.MouseButton.LeftButton
            and self.card_at(event.position().toPoint()) is None
        ):
            # 右键 / 中键 / 空白处左键拖动 = 自由平移（XMind 手感）
            self._auto_fit = False
            self._panning = True
            self._pan_distance = 0
            self._pan_origin = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # pragma: no cover - 需要 GUI
        if self._panning:
            current = event.position().toPoint()
            delta = current - self._pan_origin
            self._pan_origin = current
            self._pan_distance += abs(delta.x()) + abs(delta.y())
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # pragma: no cover - 需要 GUI
        if self._panning:
            self._panning = False
            self.unsetCursor()
            if event.button() == Qt.MouseButton.RightButton and self._pan_distance > 6:
                # 右键是拖动平移，不是"点开菜单"
                self._suppress_menu = True
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:  # pragma: no cover - 需要 GUI
        if self._suppress_menu:
            self._suppress_menu = False
            event.accept()
            return
        card = self.card_at(event.pos())
        if card is not None:
            self.nodeMenuRequested.emit(card.data.node_id, event.globalPos())
            event.accept()
            return
        super().contextMenuEvent(event)

    def card_at(self, pos: QPoint) -> MindMapCard | None:
        """视口坐标处的卡片（连线等其它图元不算）。"""
        item = self.itemAt(pos)
        while item is not None and not isinstance(item, MindMapCard):
            item = item.parentItem() if item.parentItem() is not None else None
        return item if isinstance(item, MindMapCard) else None

    def resizeEvent(self, event) -> None:  # pragma: no cover - 需要 GUI
        # 窗口尺寸变化时重新适应，保证画布四周始终留出可拖动的余量。
        super().resizeEvent(event)
        if self._auto_fit and self._cards:
            self.fit_to_window()
