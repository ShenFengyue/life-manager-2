"""思维导图布局测试（纯计算，无 Qt）。"""

from __future__ import annotations

import unittest

from app.mindmap import LayoutNode, layout_forest


def rectangle_overlaps(a, b) -> bool:
    return not (
        a.x + a.width <= b.x
        or b.x + b.width <= a.x
        or a.y + a.height <= b.y
        or b.y + b.height <= a.y
    )


class LayoutForestTest(unittest.TestCase):
    def setUp(self) -> None:
        self.roots = [
            LayoutNode(
                id="area1",
                depth=0,
                children=(
                    LayoutNode(
                        id="p1",
                        depth=1,
                        children=(
                            LayoutNode(id="t1", depth=2),
                            LayoutNode(id="t2", depth=2),
                            LayoutNode(id="t3", depth=2),
                        ),
                    ),
                    LayoutNode(id="p2", depth=1, children=(LayoutNode(id="t4", depth=2),)),
                ),
            ),
            LayoutNode(
                id="area2",
                depth=0,
                children=(LayoutNode(id="p3", depth=1),),
            ),
        ]
        self.layout = layout_forest(
            self.roots, level_widths=[150.0, 170.0, 200.0], card_height=48.0
        )

    def test_every_node_is_placed(self) -> None:
        self.assertEqual(
            set(self.layout.placements),
            {"area1", "p1", "p2", "t1", "t2", "t3", "t4", "area2", "p3"},
        )

    def test_cards_do_not_overlap(self) -> None:
        placements = list(self.layout.placements.values())
        for index, first in enumerate(placements):
            for second in placements[index + 1 :]:
                self.assertFalse(
                    rectangle_overlaps(first, second),
                    f"卡片重叠：{first} 与 {second}",
                )

    def test_depth_increases_to_the_right(self) -> None:
        self.assertLess(self.layout.placements["area1"].x, self.layout.placements["p1"].x)
        self.assertLess(self.layout.placements["p1"].x, self.layout.placements["t1"].x)
        self.assertEqual(self.layout.placements["t1"].x, self.layout.placements["t4"].x)

    def test_parent_is_centered_on_its_children(self) -> None:
        parent = self.layout.placements["p1"]
        children = [self.layout.placements[key] for key in ("t1", "t2", "t3")]
        top = min(child.y for child in children)
        bottom = max(child.y + child.height for child in children)
        self.assertAlmostEqual(parent.center_y, (top + bottom) / 2, places=4)

    def test_area_is_centered_on_its_processes(self) -> None:
        area = self.layout.placements["area1"]
        processes = [self.layout.placements[key] for key in ("p1", "p2")]
        top = min(child.y for child in processes)
        bottom = max(child.y + child.height for child in processes)
        self.assertAlmostEqual(area.center_y, (top + bottom) / 2, places=4)

    def test_areas_are_stacked_with_gap(self) -> None:
        first_area_block = max(
            placement.y + placement.height
            for key, placement in self.layout.placements.items()
            if key in {"area1", "p1", "p2", "t1", "t2", "t3", "t4"}
        )
        self.assertGreater(self.layout.placements["area2"].y, first_area_block)

    def test_layout_size_covers_everything(self) -> None:
        right = max(item.x + item.width for item in self.layout.placements.values())
        bottom = max(item.y + item.height for item in self.layout.placements.values())
        self.assertGreaterEqual(self.layout.width, right)
        self.assertGreaterEqual(self.layout.height, bottom)

    def test_empty_forest(self) -> None:
        layout = layout_forest([], level_widths=[150.0])
        self.assertEqual(layout.placements, {})
        self.assertEqual((layout.width, layout.height), (0.0, 0.0))

    def test_single_node_is_top_left(self) -> None:
        layout = layout_forest(
            [LayoutNode(id="only", depth=0)], level_widths=[150.0], card_height=48.0
        )
        placement = layout.placements["only"]
        self.assertEqual((placement.x, placement.y), (0.0, 0.0))
        self.assertEqual((layout.width, layout.height), (150.0, 48.0))


if __name__ == "__main__":
    unittest.main()
