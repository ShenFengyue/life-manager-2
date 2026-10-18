"""快速记录（Ctrl+N）：匹配内核与两段式交互。

对应需求：按快捷键 → 一个输入框 → 先模糊匹配节点 → 回车 → 再写备注 → 回车保存关闭。
"""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

from app import paths  # noqa: E402
from app.models import NodeType, today_str  # noqa: E402
from app.quick_capture import (  # noqa: E402
    build_candidates,
    match,
    recent_candidates,
    score_candidate,
)
from app.services import LifeManagerService  # noqa: E402
from app.storage import Database  # noqa: E402
from app.widgets.quick_capture import QuickCaptureDialog  # noqa: E402
from tests._support import make_temp_dir, remove_temp_dir  # noqa: E402


def _node(node_id: str, name: str, kind: NodeType, archived: bool = False):
    return SimpleNamespace(id=node_id, name=name, type=kind, is_archived=archived)


class _StubService:
    """只提供 build_candidates / recent_candidates 需要的方法。"""

    def __init__(self, areas, activities=()):
        self._areas = areas
        self._activities = list(activities)

    def areas(self):
        return [area for area, _processes in self._areas]

    def processes(self, area_id):
        for area, processes in self._areas:
            if area.id == area_id:
                return [process for process, _threads in processes]
        return []

    def threads(self, process_id):
        for _area, processes in self._areas:
            for process, threads in processes:
                if process.id == process_id:
                    return list(threads)
        return []

    def list_activities(self, limit=None):
        return self._activities[:limit] if limit else list(self._activities)


def _sample_service() -> _StubService:
    """主业 → 英语单词（背单词 / 精听 / 已归档的旧线程）、减脂；副业 → 播客。"""
    main = _node("area-1", "主业", NodeType.AREA)
    side = _node("area-2", "副业", NodeType.AREA)
    english = _node("p-1", "英语单词", NodeType.PROCESS)
    fat = _node("p-2", "减脂", NodeType.PROCESS)
    podcast = _node("p-3", "播客", NodeType.PROCESS)
    words = _node("t-1", "背单词", NodeType.THREAD)
    listen = _node("t-2", "精听", NodeType.THREAD)
    archived = _node("t-3", "旧线程", NodeType.THREAD, archived=True)
    return _StubService(
        [
            (main, [(english, [words, listen, archived]), (fat, [])]),
            (side, [(podcast, [])]),
        ]
    )


class MatchingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = _sample_service()
        self.candidates = build_candidates(self.service)

    def test_build_candidates_orders_and_skips_archived(self) -> None:
        names = [candidate.name for candidate in self.candidates]
        self.assertEqual(names, ["英语单词", "背单词", "精听", "减脂", "播客"])
        self.assertNotIn("旧线程", names)
        podcast = self.candidates[-1]
        self.assertEqual(podcast.parent_path, "副业")
        self.assertEqual(podcast.type_label, NodeType.PROCESS.label)

    def test_prefix_match_ranks_first(self) -> None:
        results = match(self.candidates, "英语")
        self.assertEqual(results[0].name, "英语单词")

    def test_substring_and_fuzzy_match(self) -> None:
        names = [item.name for item in match(self.candidates, "单词")]
        # 「背单词」与「英语单词」名字都命中；位置更靠前的排前面
        self.assertEqual(names[0], "背单词")
        self.assertIn("英语单词", names)
        # 只命中归属路径的候选排在最后（"精听"的归属里有「英语单词」）
        self.assertEqual(names[-1], "精听")
        # 字符按顺序出现即可命中："英单" → "英语单词"
        self.assertEqual(match(self.candidates, "英单")[0].name, "英语单词")

    def test_name_hit_beats_path_hit(self) -> None:
        self.assertEqual(match(self.candidates, "播客")[0].name, "播客")
        # 只命中归属路径的候选也能列出来，但排在名字命中之后
        path_only = match(self.candidates, "主业")
        self.assertTrue(path_only)
        self.assertNotEqual(path_only[0].name, "播客")

    def test_multi_token_requires_every_token(self) -> None:
        self.assertEqual(
            [item.name for item in match(self.candidates, "主业 精听")], ["精听"]
        )
        self.assertEqual(match(self.candidates, "主业 播客"), [])

    def test_no_match_and_blank_query(self) -> None:
        self.assertEqual(match(self.candidates, "不存在的东西"), [])
        self.assertEqual(match(self.candidates, "   "), [])
        self.assertEqual(score_candidate(self.candidates[0], []), 0)

    def test_result_limit(self) -> None:
        self.assertLessEqual(len(match(self.candidates, "业", limit=2)), 2)

    def test_recent_candidates_dedup_and_skip_unknown(self) -> None:
        service = _sample_service()
        service._activities = [
            SimpleNamespace(node_id="t-2"),
            SimpleNamespace(node_id="t-2"),
            SimpleNamespace(node_id="gone"),
            SimpleNamespace(node_id="p-3"),
        ]
        recent = recent_candidates(service, build_candidates(service))
        self.assertEqual([item.name for item in recent], ["精听", "播客"])


class QuickCaptureDialogTest(unittest.TestCase):
    app: QApplication

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tmp = make_temp_dir()
        self._saved = {
            "BACKUP_DIR": paths.BACKUP_DIR,
            "EXPORT_DIR": paths.EXPORT_DIR,
            "DIARY_PATH": paths.DIARY_PATH,
        }
        paths.BACKUP_DIR = self.tmp / "backups"
        paths.EXPORT_DIR = self.tmp / "exports"
        paths.DIARY_PATH = self.tmp / "diary.md"
        self.db = Database(self.tmp / "quick.sqlite3")
        self.db.initialize()
        self.service = LifeManagerService(self.db)

    def tearDown(self) -> None:
        self.db.close()
        for key, value in self._saved.items():
            setattr(paths, key, value)
        remove_temp_dir(self.tmp)

    def _dialog(self) -> QuickCaptureDialog:
        return QuickCaptureDialog(self.service, None)

    def test_two_enter_flow_records_activity(self) -> None:
        process = self.service.processes(self.service.areas()[0].id)[0]
        dialog = self._dialog()

        dialog.input.setText(process.name)
        self.assertTrue(dialog.matches)
        self.assertEqual(dialog.matches[0].node_id, process.id)

        dialog.input.returnPressed.emit()  # 第一次回车：选中节点
        self.assertEqual(dialog.stage, "note")
        self.assertFalse(dialog.result_list.isVisibleTo(dialog))
        self.assertIn(process.name, dialog.target_label.text())
        self.assertIn(today_str(), dialog.target_label.text())
        self.assertEqual(self.service.list_activities(), [])  # 还没写数据

        dialog.input.setText("推进了一步")
        dialog.input.returnPressed.emit()  # 第二次回车：保存并关闭
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertIsNotNone(dialog.recorded)

        records = self.service.list_activities(node_id=process.id)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].note, "推进了一步")
        self.assertEqual(records[0].activity_date, today_str())

    def test_blank_query_shows_recent_nodes(self) -> None:
        process = self.service.processes(self.service.areas()[0].id)[0]
        self.assertEqual(self._dialog().matches, [])

        self.service.record_activity(process.id, "一次")
        self.assertEqual(
            [item.node_id for item in self._dialog().matches], [process.id]
        )

    def test_escape_before_second_enter_writes_nothing(self) -> None:
        process = self.service.processes(self.service.areas()[0].id)[0]
        dialog = self._dialog()
        dialog.input.setText(process.name)
        dialog.input.returnPressed.emit()
        dialog.input.setText("写了但没保存")
        dialog.reject()  # 相当于按 Esc
        self.assertIsNone(dialog.recorded)
        self.assertEqual(self.service.list_activities(), [])

    def test_enter_without_selection_keeps_matching_stage(self) -> None:
        dialog = self._dialog()
        dialog.input.setText("绝对不存在的节点")
        dialog.input.returnPressed.emit()
        self.assertEqual(dialog.stage, "match")
        self.assertIsNone(dialog.recorded)

    def test_deleted_target_reports_error(self) -> None:
        process = self.service.processes(self.service.areas()[0].id)[0]
        dialog = self._dialog()
        dialog.input.setText(process.name)
        dialog.input.returnPressed.emit()
        self.service.delete_node(process.id)  # 选中之后目标被删掉
        dialog.input.setText("还是会失败")
        dialog.input.returnPressed.emit()
        self.assertEqual(dialog.stage, "note")
        self.assertIsNone(dialog.recorded)
        self.assertIn("删除", dialog.status_label.text())


if __name__ == "__main__":
    unittest.main()
