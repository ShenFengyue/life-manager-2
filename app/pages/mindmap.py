"""思维导图：XMind 风格的记录地图。

单击卡片 → 弹出记录窗口（日期默认今天），点了「记录」才生成数据；
右键卡片 → 改名 / 新建 / 移动 / 置顶 / 归档 / 删除（删除只是移入已删除清单）。
所有写入都走与其它页面相同的服务与事务，因此热力图、活动记录、总览会同步变化。
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Signal
from PySide6.QtGui import QAction, QFontMetrics
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QInputDialog,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import clock, heatmap as heatmap_stats
from .. import mindmap as mindmap_layout
from .. import theme
from ..models import Node, NodeType, Status, today_str
from ..services import LifeManagerService, ValidationError
from ..widgets.common import (
    ActivityListDialog,
    QuickRecordDialog,
    Subtle,
    run_delete_node,
    run_move_dialog,
    warn,
)
from ..widgets.mindmap_view import CardData, MindMapView
from ..widgets.common import log_cursor
from .heatmaps import HeatmapDetailDialog


class MindMapPage(QWidget):
    changed = Signal()
    openNodeRequested = Signal(str)

    def __init__(self, service: LifeManagerService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self._fitted = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 14)
        layout.setSpacing(10)
        layout.addWidget(self._build_toolbar())
        layout.addWidget(self._build_hint())

        self.view = MindMapView()
        self.view.nodeActivated.connect(self.record_for_node)
        self.view.nodeMenuRequested.connect(self._show_node_menu)
        self.view.nodeHeatmapRequested.connect(self.open_heatmap_for_node)
        layout.addWidget(self.view, 1)

        self.today_label = Subtle("")
        footer = QHBoxLayout()
        footer.addWidget(self.today_label)
        footer.addStretch(1)
        self.today_button = QPushButton("查看今天的记录")
        self.today_button.clicked.connect(self._show_today)
        footer.addWidget(self.today_button)
        layout.addLayout(footer)
        self.refresh()

    # -------------------------------------------------------------- 工具栏
    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        fit = QPushButton("适应窗口")
        fit.clicked.connect(self._fit)
        zoom_in = QPushButton("放大 +")
        zoom_in.clicked.connect(lambda: self.view.zoom_by(1.15))
        zoom_out = QPushButton("缩小 −")
        zoom_out.clicked.connect(lambda: self.view.zoom_by(1 / 1.15))
        row.addWidget(fit)
        row.addWidget(zoom_in)
        row.addWidget(zoom_out)

        self.archive_toggle = QCheckBox("显示已归档")
        self.archive_toggle.stateChanged.connect(lambda _state: self.refresh())
        row.addWidget(self.archive_toggle)
        row.addStretch(1)
        return bar

    def _build_hint(self) -> QWidget:
        return Subtle(
            "单击卡片 = 记录一次；右键单击卡片 = 改名 / 新建 / 移动 / 置顶 / 归档 / 删除；"
            "中键单击卡片 = 看它自己的大热力图；"
            "按住右键（或空白处左键）拖动 = 自由移动画布；Ctrl+滚轮缩放。"
        )

    def _fit(self) -> None:
        self.view.fit_to_window()

    # ---------------------------------------------------------------- 数据
    def _build_scene(self) -> tuple[list, list[CardData], dict[str, str | None], list]:
        conn = self.service.db.conn
        today = today_str()
        include_archived = self.archive_toggle.isChecked()

        area_today = heatmap_stats.scope_counts(conn, "area_id", today)
        area_total = heatmap_stats.scope_counts(conn, "area_id")
        process_today = heatmap_stats.scope_counts(conn, "process_id", today)
        process_total = heatmap_stats.scope_counts(conn, "process_id")
        thread_today = heatmap_stats.scope_counts(conn, "thread_id", today)
        thread_total = heatmap_stats.scope_counts(conn, "thread_id")
        latest = heatmap_stats.latest_activity_by_node(conn)
        today_activities = self.service.list_activities(date_from=today, date_to=today)

        roots: list[mindmap_layout.LayoutNode] = []
        cards: list[CardData] = []
        parents: dict[str, str | None] = {}

        for index, area in enumerate(self.service.areas()):
            color = theme.map_color(index)
            parents[area.id] = None
            process_nodes: list[mindmap_layout.LayoutNode] = []
            for process in self.service.processes(area.id):
                if process.is_archived and not include_archived:
                    continue
                thread_nodes: list[mindmap_layout.LayoutNode] = []
                for thread in self.service.threads(process.id):
                    if thread.is_archived and not include_archived:
                        continue
                    thread_nodes.append(mindmap_layout.LayoutNode(id=thread.id, depth=2))
                    parents[thread.id] = process.id
                    cards.append(
                        self._card(
                            thread, color, "thread",
                            thread_today.get(thread.id, 0),
                            thread_total.get(thread.id, 0),
                            latest.get(thread.id),
                        )
                    )
                process_nodes.append(
                    mindmap_layout.LayoutNode(
                        id=process.id, depth=1, children=tuple(thread_nodes)
                    )
                )
                parents[process.id] = area.id
                cards.append(
                    self._card(
                        process, color, "process",
                        process_today.get(process.id, 0),
                        process_total.get(process.id, 0),
                        latest.get(process.id),
                    )
                )
            roots.append(
                mindmap_layout.LayoutNode(id=area.id, depth=0, children=tuple(process_nodes))
            )
            cards.append(
                self._card(
                    area, color, "area",
                    area_today.get(area.id, 0),
                    area_total.get(area.id, 0),
                    latest.get(area.id),
                )
            )
        return roots, cards, parents, today_activities

    def _card(
        self,
        node: Node,
        color: str,
        kind: str,
        today_count: int,
        total_count: int,
        latest: tuple[str, str] | None,
    ) -> CardData:
        subtitle = f"今日 {today_count} · 共 {total_count}"
        if node.is_archived:
            subtitle += " · 已归档"
        lines = [
            f"{node.name}（{node.type.label}）",
            f"归属：{self.service.path_text(node.id)}",
            f"状态：{node.status.value}" + ("（已置顶为重点）" if node.pinned else ""),
            f"今日 {today_count} 次 · 共 {total_count} 次",
        ]
        if node.type is not NodeType.AREA and node.next_action:
            lines.append(f"下一步：{node.next_action}")
        if latest:
            note = latest[1] or "（无备注）"
            lines.append(f"最近：{latest[0]} {note}")
        lines.append("左键单击 = 记录一次；右键 = 改名 / 新建 / 移动 / 归档 / 删除")
        lines.append("中键单击 = 看它自己的大热力图")
        return CardData(
            node_id=node.id,
            title=node.name,
            subtitle=subtitle,
            kind=kind,
            color=color,
            pinned=node.pinned,
            archived=node.is_archived,
            tooltip="\n".join(lines),
            today_count=today_count,
        )

    def _level_widths(self, cards: list[CardData]) -> list[float]:
        metrics = QFontMetrics(theme.app_font())
        widths: list[float] = []
        for kind, minimum in (("area", 150.0), ("process", 160.0), ("thread", 200.0)):
            longest = max(
                [metrics.horizontalAdvance(card.title) for card in cards if card.kind == kind]
                or [80]
            )
            widths.append(max(minimum, min(320.0, longest + 96)))
        return widths

    # ---------------------------------------------------------------- 刷新
    def refresh(self) -> None:
        roots, cards, parents, today_activities = self._build_scene()
        layout = mindmap_layout.layout_forest(
            roots, level_widths=self._level_widths(cards)
        )
        self.view.set_parent_map(parents)
        self.view.rebuild(cards, layout)
        if not self._fitted:
            self.view.fit_to_window()
            self._fitted = True
        if today_activities:
            latest = today_activities[0]
            self.today_label.setText(
                f"今天已记录 {len(today_activities)} 次 · 最近：{latest.path_text}"
                + (f"「{latest.note}」" if latest.note else "")
            )
        else:
            self.today_label.setText("今天还没有记录。单击任意进程或线程卡片即可记录一次。")

    # ---------------------------------------------------------------- 操作
    def record_for_node(self, node_id: str) -> None:
        node = self.service.get_node(node_id)
        if node is None:
            return
        if node.type is NodeType.AREA:
            # 领域本身不能记录活动：用状态栏提示，不弹窗打断操作手感。
            self._status(
                f"{node.name}：领域本身不能记录活动，请点它右边的进程卡片或线程卡片。"
            )
            return
        dialog = QuickRecordDialog(
            self.service,
            self,
            preset_node_id=node_id,
            lock_node=True,
            title="记录一次活动",
        )
        log_cursor("准备弹记录窗（窗口还没显示）")
        if dialog.exec() and dialog.recorded is not None:
            self.changed.emit()

    def open_heatmap_for_node(self, node_id: str) -> None:
        """中键单击卡片：打开它自己的大热力图。

        领域 = 含其下全部进程与线程；进程 = 它自己；线程 = 它自己
        （线程那张只统计「当时记在这个线程上」的活动）。
        """
        node = self.service.get_node(node_id)
        if node is None:
            return
        if node.type is NodeType.AREA:
            scope_kind = "area"
        elif node.type is NodeType.PROCESS:
            scope_kind = "process"
        else:
            scope_kind = "thread"
        dialog = HeatmapDetailDialog(
            self.service,
            node,
            scope_kind,
            clock.today(),
            on_changed=self.changed.emit,
            parent=self,
        )
        dialog.showMaximized()
        dialog.exec()

    def _status(self, message: str, timeout: int = 6000) -> None:
        """往主窗口状态栏写一句提示；独立使用这个页面时退回弹窗。"""
        window = self.window()
        status_bar = window.statusBar() if hasattr(window, "statusBar") else None
        if status_bar is not None:
            status_bar.showMessage(message, timeout)
        else:  # pragma: no cover - 独立使用该页面时
            warn(self, "提示", message)

    def _show_node_menu(self, node_id: str, global_pos: QPoint) -> None:
        node = self.service.get_node(node_id)
        if node is None:
            return
        self.build_node_menu(node).exec(global_pos)

    def build_node_menu(self, node: Node) -> QMenu:
        """构造卡片的右键菜单（抽出来是为了能单独测它，不用真的弹出来）。"""
        menu = QMenu(self)

        def add(label: str, handler) -> None:
            action = QAction(label, menu)
            action.triggered.connect(lambda _checked=False, h=handler: h())
            menu.addAction(action)

        if node.type is not NodeType.AREA:
            add("记录一次活动…", lambda: self.record_for_node(node.id))
        add("看大热力图…", lambda: self.open_heatmap_for_node(node.id))
        add("查看它的活动记录", lambda: self._show_activities(node.id))
        if node.type is not NodeType.AREA:
            add("到进程树查看详情与历史", lambda: self.openNodeRequested.emit(node.id))
        menu.addSeparator()
        add("重命名…", lambda: self._rename(node))
        child_type = node.type.child_type
        if child_type is not None:
            label = "新建进程…" if child_type is NodeType.PROCESS else "新建线程…"
            add(label, lambda: self._create_child(node, child_type))
        if node.type is not NodeType.AREA:
            add("移动到…", lambda: self._move(node))
            add("编辑下一步行动…", lambda: self._edit_next_action(node))
            add("取消置顶" if node.pinned else "置顶为重点", lambda: self._toggle_pin(node))
            if node.is_archived:
                add("取消归档（设为进行中）", lambda: self._set_status(node, Status.DOING))
            else:
                add("归档", lambda: self._set_status(node, Status.ARCHIVED))
        menu.addSeparator()
        add("删除（移入已删除清单）…", lambda: self._delete(node))
        return menu

    def _show_activities(self, node_id: str) -> None:
        node = self.service.require_node(node_id)
        dialog = ActivityListDialog(
            self.service,
            self,
            title=f"{node.name} 的活动记录",
            subtitle="这里可以修改备注与日期，也可以彻底删除某条记录。",
            loader=lambda: self.service.list_activities(node_id=node_id),
            empty_text="该节点还没有活动记录。",
        )
        dialog.changed.connect(self._on_activities_changed)
        dialog.exec()

    def _show_today(self) -> None:
        day = today_str()
        dialog = ActivityListDialog(
            self.service,
            self,
            title=f"今天的记录（{day}）",
            subtitle="今天记录的全部活动；可以修改或彻底删除其中任意一条。",
            loader=lambda: self.service.list_activities(date_from=day, date_to=day),
            empty_text="今天还没有记录。",
        )
        dialog.changed.connect(self._on_activities_changed)
        dialog.exec()

    def _on_activities_changed(self) -> None:
        """弹窗里改了/删了活动：立刻重画地图，并通知主窗口。"""
        self.refresh()
        self.changed.emit()

    def _rename(self, node: Node) -> None:
        name, ok = QInputDialog.getText(self, "重命名节点", "新名称", text=node.name)
        if not ok or not name.strip():
            return
        try:
            self.service.rename_node(node.id, name)
        except ValidationError as exc:
            warn(self, "无法重命名", str(exc))
            return
        self.changed.emit()

    def _create_child(self, node: Node, child_type: NodeType) -> None:
        name, ok = QInputDialog.getText(
            self, f"新建{child_type.label}", f"在「{node.name}」下新建{child_type.label}", text=""
        )
        if not ok or not name.strip():
            return
        try:
            self.service.create_node(child_type, name, node.id)
        except ValidationError as exc:
            warn(self, "无法新建", str(exc))
            return
        self.changed.emit()

    def _move(self, node: Node) -> None:
        if run_move_dialog(self.service, self, node):
            self.changed.emit()

    def _delete(self, node: Node) -> None:
        if run_delete_node(self.service, self, node):
            self.changed.emit()

    def _set_status(self, node: Node, status: Status) -> None:
        try:
            self.service.set_status(node.id, status)
        except ValidationError as exc:
            warn(self, "无法修改状态", str(exc))
            return
        self.changed.emit()

    def _toggle_pin(self, node: Node) -> None:
        try:
            self.service.set_pinned(node.id, not node.pinned)
        except ValidationError as exc:
            warn(self, "无法置顶", str(exc))
            return
        self.changed.emit()

    def _edit_next_action(self, node: Node) -> None:
        text, ok = QInputDialog.getText(self, "下一步行动", "行动内容", text=node.next_action)
        if not ok:
            return
        try:
            self.service.set_next_action(node.id, text)
        except ValidationError as exc:
            warn(self, "无法保存", str(exc))
            return
        self.changed.emit()
