"""「已删除」清单：查看被删除的节点并恢复。

删除节点不会删除任何数据：活动记录、归属快照、热力图统计与历史事件都保留，
节点只是从树、列表、选择器与热力图分组里移出，因此可以随时恢复。
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..services import LifeManagerService, ValidationError
from .common import (
    AppDialog,
    Muted,
    SectionHeader,
    Subtle,
    info,
    open_activity_dialog,
    warn,
)


class DeletedNodesDialog(AppDialog):
    """列出「已删除」清单，支持查看活动与恢复。"""

    changed = Signal()

    HEADERS = ("名称", "类型", "原归属", "删除时间", "包含节点", "活动记录", "状态")

    def __init__(self, service: LifeManagerService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.setWindowTitle("已删除")
        self.resize(940, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        layout.addWidget(SectionHeader("已删除"))
        layout.addWidget(
            Muted(
                "删除只是把节点从这里移出去：它的活动记录、热力图统计和历史事件都还保留着，"
                "所以随时可以恢复。删除后领域热力图里那份数据也照样留在原处。"
            )
        )

        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setShowGrid(False)
        self.table.itemSelectionChanged.connect(self._sync_buttons)
        layout.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        self.restore_button = QPushButton("恢复选中")
        self.restore_button.setObjectName("Primary")
        self.restore_button.clicked.connect(self._restore_selected)
        self.view_button = QPushButton("查看它的活动记录")
        self.view_button.clicked.connect(self._view_activities)
        self.view_heatmap_button = QPushButton("查看它的热力图")
        self.view_heatmap_button.clicked.connect(self._view_heatmap)
        buttons.addWidget(self.restore_button)
        buttons.addWidget(self.view_button)
        buttons.addWidget(self.view_heatmap_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.hint = Subtle("")
        layout.addWidget(self.hint)

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        box.button(QDialogButtonBox.StandardButton.Close).setText("关闭")
        box.rejected.connect(self.reject)
        layout.addWidget(box)
        self.reload()

    # ---------------------------------------------------------------- 数据
    def reload(self) -> None:
        self._entries = self.service.deleted_entries()
        self.table.setRowCount(0)
        for entry in self._entries:
            node = entry["node"]
            row = self.table.rowCount()
            self.table.insertRow(row)
            cells = (
                node.name,
                node.type.label,
                " → ".join(entry["path"][:-1]) or "（顶层）",
                entry["deleted_at"] or "",
                f"{entry['batch_size']} 个",
                f"{entry['subtree_activity_count']} 条",
                "可恢复" if entry["restorable"] else "需先恢复上级：" + "、".join(entry["blockers"]),
            )
            for column, text in enumerate(cells):
                item = QTableWidgetItem(str(text))
                item.setData(Qt.ItemDataRole.UserRole, node.id)
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()
        self.hint.setText(
            "清单为空。" if not self._entries else f"共 {len(self._entries)} 批已删除节点。"
        )
        self._sync_buttons()

    def _current_entry(self) -> dict | None:
        rows = {index.row() for index in self.table.selectedItems()}
        if not rows:
            return None
        row = sorted(rows)[0]
        return self._entries[row] if 0 <= row < len(self._entries) else None

    def _sync_buttons(self) -> None:
        entry = self._current_entry()
        self.restore_button.setEnabled(bool(entry) and entry["restorable"])
        self.view_button.setEnabled(bool(entry))
        self.view_heatmap_button.setEnabled(bool(entry))

    # ---------------------------------------------------------------- 操作
    def _restore_selected(self) -> None:
        entry = self._current_entry()
        if entry is None:
            return
        node = entry["node"]
        try:
            count = self.service.restore_node(node.id)
        except ValidationError as exc:
            warn(self, "无法恢复", str(exc))
            return
        self.reload()
        self.changed.emit()
        info(
            self,
            "已恢复",
            f"「{node.name}」已经回到树里原来的位置（共恢复 {count} 个节点）。\n"
            "它名下的活动记录与热力图本来就一直在，现在看得到入口了。",
        )

    def _view_activities(self) -> None:
        entry = self._current_entry()
        if entry is None:
            return
        node = entry["node"]
        activities = self.service.list_activities(node_id=node.id)
        open_activity_dialog(
            self.service,
            self,
            title=f"{node.name} 的活动记录（已删除，数据保留）",
            subtitle=f"共 {len(activities)} 条。删除节点没有删掉这些记录，热力图里的次数也仍在。",
            loader=lambda: self.service.list_activities(node_id=node.id),
            empty_text="该节点没有活动记录。",
            on_changed=self._on_activities_changed,
        )

    def _on_activities_changed(self) -> None:
        self.reload()
        self.changed.emit()

    def _view_heatmap(self) -> None:
        entry = self._current_entry()
        if entry is None:
            return
        node = entry["node"]
        info(
            self,
            "热力图",
            f"「{node.name}」的热力图在「热力图」页面最下方的「已删除（数据保留）」分组里，"
            "它的记录仍然计入上层领域的热力图。",
        )
