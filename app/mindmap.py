"""思维导图布局：纯计算，不依赖 Qt，便于单独测试。

采用 XMind「逻辑图」的横向布局：领域在左，向右依次是进程、线程。
子树在垂直方向依次排列，父节点在自己子节点块中垂直居中。
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace


@dataclass(frozen=True)
class LayoutNode:
    """布局输入：只需要层级与子节点。"""

    id: str
    depth: int
    children: tuple["LayoutNode", ...] = ()


@dataclass(frozen=True)
class Placement:
    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def center_y(self) -> float:
        return self.y + self.height / 2


@dataclass(frozen=True)
class Layout:
    placements: dict[str, Placement] = field(default_factory=dict)
    width: float = 0.0
    height: float = 0.0

    def bounds_of(self, node_ids: list[str]) -> tuple[float, float, float, float]:
        """一组节点的整体包围盒 (left, top, right, bottom)。"""
        left = min(self.placements[node].x for node in node_ids)
        top = min(self.placements[node].y for node in node_ids)
        right = max(self.placements[node].right for node in node_ids)
        bottom = max(self.placements[node].y + self.placements[node].height for node in node_ids)
        return left, top, right, bottom


def layout_forest(
    roots: list[LayoutNode],
    *,
    level_widths: list[float],
    card_height: float = 48.0,
    vertical_gap: float = 12.0,
    horizontal_gap: float = 64.0,
    root_gap: float = 26.0,
) -> Layout:
    """把若干棵树排成横向逻辑图，返回每个节点的位置与整体尺寸。"""
    if not roots:
        return Layout()
    if not level_widths:
        raise ValueError("level_widths 不能为空")

    x_offsets: list[float] = []
    cursor_x = 0.0
    for width in level_widths:
        x_offsets.append(cursor_x)
        cursor_x += width + horizontal_gap
    total_width = cursor_x - horizontal_gap

    placements: dict[str, Placement] = {}

    def _width_at(depth: int) -> float:
        return level_widths[min(depth, len(level_widths) - 1)]

    def _x_at(depth: int) -> float:
        return x_offsets[min(depth, len(x_offsets) - 1)]

    def subtree_height(node: LayoutNode) -> float:
        if not node.children:
            return card_height
        children_height = sum(subtree_height(child) for child in node.children)
        children_height += vertical_gap * (len(node.children) - 1)
        return max(card_height, children_height)

    def place(node: LayoutNode, top: float) -> None:
        placements[node.id] = Placement(
            x=_x_at(node.depth),
            y=top,
            width=_width_at(node.depth),
            height=card_height,
        )
        if not node.children:
            # 叶子节点就待在自己的块里
            return
        child_top = top
        for child in node.children:
            place(child, child_top)
            child_top += subtree_height(child) + vertical_gap
        # XMind 的做法：父节点对齐到「第一个子节点中心」与「最后一个子节点中心」的中点
        first_center = placements[node.children[0].id].center_y
        last_center = placements[node.children[-1].id].center_y
        center = (first_center + last_center) / 2
        placements[node.id] = replace(placements[node.id], y=center - card_height / 2)

    top_cursor = 0.0
    for index, root in enumerate(roots):
        place(root, top_cursor)
        top_cursor += subtree_height(root)
        if index != len(roots) - 1:
            top_cursor += root_gap

    total_height = top_cursor
    return Layout(placements=placements, width=total_width, height=total_height)


def connector_path(parent: Placement, child: Placement, radius: float = 12.0) -> list[tuple[float, float]]:
    """父子之间的连线控制点：两段横向线 + 中间竖线（XMind 逻辑图风格）。"""
    start_x = parent.right
    start_y = parent.center_y
    end_x = child.x
    end_y = child.center_y
    mid_x = start_x + (end_x - start_x) * 0.5
    radius = min(radius, abs(end_y - start_y) / 2, abs(mid_x - start_x))
    return [
        (start_x, start_y),
        (mid_x, start_y),
        (mid_x, end_y),
        (end_x, end_y),
    ]
