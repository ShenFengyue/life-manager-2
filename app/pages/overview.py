"""页面 A：总览 Overview。

展示当前重点、快速记录入口、三个 Area 的热力图与最近活动。
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import (
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .. import heatmap as heatmap_stats
from .. import theme
from ..appconfig import AppConfig
from ..models import Node, Status, today_str
from ..services import LifeManagerService, ValidationError
from ..widgets.common import (
    ActivityTable,
    BeijingClock,
    Card,
    Muted,
    NodeComboBox,
    open_activity_dialog,
    QuickRecordDialog,
    SectionHeader,
    StatusChip,
    Subtle,
    clear_layout,
    hline,
    qdate_to_str,
    str_to_qdate,
    warn,
)
from ..widgets.heatmap_calendar import HeatmapCalendar, HeatmapLegend


class FocusCard(Card):
    """一个重点：名称、主要归属、状态、下一步行动。

    卡片本身可以按住拖动 —— 只调整它在总览里的显示顺序，不改任何数据。
    """

    recordRequested = Signal(str)
    detailRequested = Signal(str)
    dragMoved = Signal(str, QPoint)
    dragFinished = Signal(str)

    DRAG_THRESHOLD = 6

    def __init__(self, service: LifeManagerService, node_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent, name="FocusCard")
        self.service = service
        self.node_id = node_id
        self._drag_origin: QPoint | None = None
        self._dragging = False
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        self._title = QLabel()
        self._title.setStyleSheet("font-size: 14px; font-weight: 600;")
        title_row.addWidget(self._title)
        title_row.addStretch(1)
        self._chip = StatusChip(Status.DOING)
        title_row.addWidget(self._chip)
        self.body.addLayout(title_row)

        self._path = Muted()
        self.body.addWidget(self._path)

        self._action = QLabel()
        self._action.setWordWrap(True)
        self.body.addWidget(self._action)
        self.body.addStretch(1)

        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        record = QPushButton("记录活动")
        record.setObjectName("Primary")
        record.clicked.connect(lambda: self.recordRequested.emit(self.node_id))
        detail = QPushButton("详情")
        detail.setObjectName("Ghost")
        detail.clicked.connect(lambda: self.detailRequested.emit(self.node_id))
        buttons.addWidget(record)
        buttons.addWidget(detail)
        buttons.addStretch(1)
        self.body.addLayout(buttons)
        self.update_content()

    # ------------------------------------------------------------ 拖动换位
    def mousePressEvent(self, event) -> None:  # pragma: no cover - 需要 GUI
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = event.position().toPoint()
            self._dragging = False
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # pragma: no cover - 需要 GUI
        if self._drag_origin is None:
            return
        if not self._dragging:
            offset = event.position().toPoint() - self._drag_origin
            if offset.manhattanLength() < self.DRAG_THRESHOLD:
                return
            self._dragging = True
            self._set_dragging_style(True)
        self.dragMoved.emit(self.node_id, event.globalPosition().toPoint())
        event.accept()

    def mouseReleaseEvent(self, event) -> None:  # pragma: no cover - 需要 GUI
        if self._drag_origin is not None:
            was_dragging = self._dragging
            self._drag_origin = None
            self._dragging = False
            if was_dragging:
                self._set_dragging_style(False)
                self.dragFinished.emit(self.node_id)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _set_dragging_style(self, active: bool) -> None:
        if active:
            self.setStyleSheet(f"#FocusCard {{ border: 1px solid {theme.ACCENT}; }}")
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        else:
            self.setStyleSheet("")
            self.setCursor(Qt.CursorShape.OpenHandCursor)

    def update_content(self) -> None:
        """只更新文字，不重建控件（避免总览在记录活动后闪烁）。"""
        node = self.service.require_node(self.node_id)
        next_action = node.next_action.strip()
        self._title.setText(node.name)
        self._chip.set_status(node.status)
        self._path.setText(self.service.path_text(self.node_id))
        self._action.setText(f"下一步：{next_action}" if next_action else "下一步：尚未设置")
        self._action.setStyleSheet(
            f"color: {theme.TEXT if next_action else theme.TEXT_SUBTLE}; font-size: 12px;"
        )


class OverviewHeatmapCard(Card):
    """总览里的一张热力图：area_id 为 None 时表示「全部领域与进程」的总热力图。"""

    def __init__(
        self,
        service: LifeManagerService,
        area_id: str | None = None,
        parent: QWidget | None = None,
        *,
        scale: float = 1.0,
        on_changed=None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.area_id = area_id
        self.total = area_id is None
        self._on_changed = on_changed

        header = QHBoxLayout()
        header.setSpacing(8)
        title = "总热力图 · 全部领域与进程" if self.total else service.require_node(area_id).name
        name = QLabel(title)
        name.setStyleSheet(f"font-size: {'18px' if self.total else '13px'}; font-weight: {'700' if self.total else '600'};")
        header.addWidget(name)
        if self.total:
            header.addWidget(Subtle("全部领域与进程汇总，每条只算一次"))
        header.addStretch(1)
        self.stats_label = Muted("") if self.total else Subtle("")
        self.stats_label.setWordWrap(False)
        header.addWidget(self.stats_label)
        self.body.addLayout(header)
        if self.total:
            self.body.addSpacing(2)

        self.calendar = HeatmapCalendar(scale=scale)
        self.calendar.dateClicked.connect(self._on_date_clicked)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.calendar)
        if self.total:
            # 时钟放在"热力图右边缘"与"卡片右边缘"之间的中间位置
            self.clock_widget = BeijingClock()
            row.addStretch(1)
            row.addWidget(self.clock_widget, 0, Qt.AlignmentFlag.AlignVCenter)
            row.addStretch(1)
        else:
            row.addStretch(1)
        self.body.addLayout(row)

        # 图例只在总热力图上留一个：下面每张领域热力图是同一套配色，不必重复
        if self.total:
            legend_row = QHBoxLayout()
            legend_row.addStretch(1)
            legend_row.addWidget(HeatmapLegend(scale=scale))
            self.body.addLayout(legend_row)

    def refresh(self) -> None:
        # 一直开着跨过午夜时，把窗口挪到今天
        self.calendar.refresh_window()
        grid = self.calendar.grid  # 与控件使用同一窗口
        conn = self.service.db.conn
        if self.total:
            counts = heatmap_stats.counts_all(conn, grid.date_from, grid.date_to)
            summaries = heatmap_stats.summaries_all(conn, grid.date_from, grid.date_to)
        else:
            counts = heatmap_stats.counts_for_area(
                conn, self.area_id, grid.date_from, grid.date_to
            )
            summaries = heatmap_stats.summaries(
                conn, "area_id", self.area_id, grid.date_from, grid.date_to
            )
        self.calendar.set_data(counts, summaries)
        total, active_days = heatmap_stats.window_totals(counts)
        self.stats_label.setText(f"近 {grid.weeks} 周 {total} 次 · {active_days} 天有记录")

    def _on_date_clicked(self, day: str) -> None:
        if self.total:
            open_activity_dialog(
                self.service,
                self,
                title=f"{day} · 全部领域与进程",
                subtitle="这一天的全部活动记录（每条只算一次）",
                loader=lambda: self.service.list_activities(date_from=day, date_to=day),
                empty_text="这一天没有任何记录。",
                on_changed=self._on_changed,
            )
            return
        area = self.service.require_node(self.area_id)
        open_activity_dialog(
            self.service,
            self,
            title=f"{day} · {area.name}",
            subtitle=f"{area.name} 领域当天的活动记录（按发生时的归属快照统计）",
            loader=lambda: self.service.list_activities(
                area_id=self.area_id, date_from=day, date_to=day
            ),
            on_changed=self._on_changed,
        )


class OverviewPage(QWidget):
    changed = Signal()
    openNodeRequested = Signal(str)
    openPageRequested = Signal(str)

    def __init__(
        self,
        service: LifeManagerService,
        parent: QWidget | None = None,
        *,
        config: AppConfig | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.config = config
        self._area_cards: list[OverviewHeatmapCard] = []
        self._focus_cards: list[FocusCard] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 18, 20, 24)
        layout.setSpacing(16)

        # ---------------------------------------------------------- 当前重点
        # 总热力图放在最上面，并且明显比下面的领域热力图更大
        self._total_card = OverviewHeatmapCard(
            # 总热力图保持放大尺寸（1.25 倍），时钟放在卡片最右侧
            self.service, None, scale=1.25, on_changed=self._on_activities_changed
        )
        layout.addWidget(self._total_card)

        layout.addWidget(hline())

        # ---------------------------------------------------------- 当前重点
        focus_header = QHBoxLayout()
        focus_header.addWidget(SectionHeader("当前重点"))
        hue = Subtle("最多 3 个置顶节点；按住卡片拖动可调整顺序")
        focus_header.addWidget(hue)
        focus_header.addStretch(1)
        layout.addLayout(focus_header)

        self.focus_row = QHBoxLayout()
        self.focus_row.setSpacing(12)
        layout.addLayout(self.focus_row)

        self.focus_empty = Muted(
            "还没有置顶的重点。到「进程树」里把正在推进的进程或线程置顶，这里就会显示它的状态与下一步行动。"
        )
        layout.addWidget(self.focus_empty)

        layout.addWidget(hline())

        # ---------------------------------------------------------- 快速记录
        layout.addWidget(SectionHeader("快速记录"))
        quick_card = Card()
        quick_row = QHBoxLayout()
        quick_row.setSpacing(10)
        self.quick_combo = NodeComboBox()
        quick_row.addWidget(self.quick_combo, 2)
        self.quick_date = QDateEdit()
        self.quick_date.setCalendarPopup(True)
        self.quick_date.setDisplayFormat("yyyy-MM-dd")
        self.quick_date.setDate(str_to_qdate(today_str()))
        quick_row.addWidget(self.quick_date)
        self.quick_note = QLineEdit()
        self.quick_note.setPlaceholderText("备注（可留空）")
        self.quick_note.returnPressed.connect(self._on_quick_record)
        quick_row.addWidget(self.quick_note, 3)
        self.quick_button = QPushButton("记录")
        self.quick_button.setObjectName("Primary")
        self.quick_button.clicked.connect(self._on_quick_record)
        quick_row.addWidget(self.quick_button)
        quick_card.body.addLayout(quick_row)
        quick_card.body.addWidget(
            Subtle("每次独立进展记为一次活动，热力图按次数而非字数着色。")
        )
        layout.addWidget(quick_card)

        layout.addWidget(hline())

        # -------------------------------------------------------- 领域热力图
        heatmap_header = QHBoxLayout()
        heatmap_header.addWidget(SectionHeader("领域热力图"))
        heatmap_header.addStretch(1)
        more = QPushButton("到热力图页面查看全部进程")
        more.setObjectName("Ghost")
        more.clicked.connect(lambda: self.openPageRequested.emit("heatmaps"))
        heatmap_header.addWidget(more)
        layout.addLayout(heatmap_header)

        self.heatmap_container = QVBoxLayout()
        self.heatmap_container.setSpacing(14)
        layout.addLayout(self.heatmap_container)

        layout.addWidget(hline())

        # ---------------------------------------------------------- 最近活动
        recent_header = QHBoxLayout()
        recent_header.addWidget(SectionHeader("最近活动"))
        recent_header.addStretch(1)
        self.recent_count = Subtle("")
        recent_header.addWidget(self.recent_count)
        layout.addLayout(recent_header)
        self.recent_table = ActivityTable()
        self.recent_table.load([], compact=True)
        self.recent_table.setMinimumHeight(220)
        layout.addWidget(self.recent_table)

        layout.addStretch(1)
        self.refresh()

    # ---------------------------------------------------------------- 刷新
    def refresh(self) -> None:
        self._refresh_focus()
        self._refresh_quick()
        self._refresh_heatmaps()
        self._refresh_recent()

    def _refresh_focus(self) -> None:
        focused = self._ordered_focus_nodes()
        if [card.node_id for card in self._focus_cards] != [node.id for node in focused]:
            clear_layout(self.focus_row)
            self._focus_cards = []
            for node in focused:
                card = FocusCard(self.service, node.id)
                card.recordRequested.connect(self._record_for_node)
                card.detailRequested.connect(self.openNodeRequested.emit)
                card.dragMoved.connect(self._on_focus_card_moved)
                card.dragFinished.connect(self._on_focus_drag_finished)
                self._focus_cards.append(card)
                self.focus_row.addWidget(card, 1)
            if len(focused) < 3:
                self.focus_row.addStretch(1)
        else:
            for card in self._focus_cards:
                card.update_content()
        self.focus_empty.setVisible(not focused)

    # ------------------------------------------------- 当前重点的显示顺序
    def _focus_order(self) -> list[str]:
        """配置里记下的显示顺序（只认还在置顶列表里的节点）。"""
        if self.config is None:
            return []
        order = self.config.get("focus_order") or []
        return [str(item) for item in order] if isinstance(order, list) else []

    def _ordered_focus_nodes(self) -> list[Node]:
        focused = self.service.focused_nodes()
        order = self._focus_order()
        if not order:
            return focused
        by_id = {node.id: node for node in focused}
        ordered = [by_id[node_id] for node_id in order if node_id in by_id]
        known = set(order)
        ordered.extend(node for node in focused if node.id not in known)
        return ordered

    def _on_focus_card_moved(self, node_id: str, global_pos: QPoint) -> None:
        """拖动中的卡片：按鼠标横向位置算出它该排到第几个。"""
        if not self._focus_cards:
            return
        position = self.mapFromGlobal(global_pos)
        target = len(self._focus_cards) - 1
        for index, card in enumerate(self._focus_cards):
            center_x = card.mapTo(self, card.rect().center()).x()
            if position.x() < center_x:
                target = index
                break
        self._move_focus_card(node_id, target, save=False)

    def _move_focus_card(
        self, node_id: str, target_index: int, *, save: bool = True
    ) -> None:
        """把某张重点卡片挪到第 target_index 位：只改显示顺序，不碰任何数据。"""
        ids = [card.node_id for card in self._focus_cards]
        if node_id not in ids:
            return
        current = ids.index(node_id)
        target = max(0, min(target_index, len(ids) - 1))
        if current == target:
            return
        ids.pop(current)
        ids.insert(target, node_id)
        by_id = {card.node_id: card for card in self._focus_cards}
        self._focus_cards = [by_id[item] for item in ids]
        for card in self._focus_cards:
            self.focus_row.removeWidget(card)
        for index, card in enumerate(self._focus_cards):
            self.focus_row.insertWidget(index, card, 1)
        if save:
            self._save_focus_order()

    def _on_focus_drag_finished(self, _node_id: str) -> None:
        """松手时才写配置：拖动过程中不反复写文件。"""
        self._save_focus_order()

    def _save_focus_order(self) -> None:
        if self.config is None:
            return
        self.config.set("focus_order", [card.node_id for card in self._focus_cards])
        self.config.save()

    def _refresh_quick(self) -> None:
        current = self.quick_combo.current_node_id()
        self.quick_combo.populate(self.service, selected_id=current)

    def _refresh_heatmaps(self) -> None:
        areas = self.service.areas()
        self._total_card.refresh()
        if [card.area_id for card in self._area_cards] != [area.id for area in areas]:
            clear_layout(self.heatmap_container)
            self._area_cards = []
            for area in areas:
                card = OverviewHeatmapCard(
                    self.service, area.id, on_changed=self._on_activities_changed
                )
                self._area_cards.append(card)
                self.heatmap_container.addWidget(card)
        for card in self._area_cards:
            card.refresh()

    def _refresh_recent(self) -> None:
        activities = self.service.list_activities(limit=12)
        self.recent_table.load(activities, compact=True)
        total = self.service.db.counts()["activities"]
        self.recent_count.setText(f"共 {total} 条活动记录")

    def _on_activities_changed(self) -> None:
        """弹窗里改了/删了活动：立刻重画总览，并通知主窗口。"""
        self.refresh()
        self.changed.emit()

    # ---------------------------------------------------------------- 交互
    def _on_quick_record(self) -> None:
        node_id = self.quick_combo.current_node_id()
        if not node_id:
            warn(self, "无法记录", "请先选择一个进程或线程。新建节点请到「进程树」页面。")
            return
        try:
            self.service.record_activity(
                node_id, self.quick_note.text(), qdate_to_str(self.quick_date.date())
            )
        except ValidationError as exc:
            warn(self, "无法记录", str(exc))
            return
        self.quick_note.clear()
        self.changed.emit()

    def _record_for_node(self, node_id: str) -> None:
        dialog = QuickRecordDialog(self.service, self, preset_node_id=node_id)
        if dialog.exec() and dialog.recorded is not None:
            self.changed.emit()
