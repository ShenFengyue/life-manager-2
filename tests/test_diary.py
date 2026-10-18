"""日记文件读写测试（纯 Python，不依赖 Qt）。"""

from __future__ import annotations

import unittest

from app import diary
from tests._support import make_temp_dir, remove_temp_dir


class DiaryFileTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = make_temp_dir()
        self.path = self.tmp / "diary.md"

    def tearDown(self) -> None:
        remove_temp_dir(self.tmp)

    def test_missing_file_is_empty(self) -> None:
        self.assertEqual(diary.read_day("2026-10-15", self.path), "")
        self.assertEqual(diary.entries(self.path), {})
        self.assertEqual(diary.days_with_entries(self.path), [])

    def test_ensure_file_creates_the_diary(self) -> None:
        self.assertFalse(self.path.exists())
        created = diary.ensure_file(self.path)
        self.assertEqual(created, self.path)
        self.assertTrue(self.path.exists())
        self.assertIn("# 日记", self.path.read_text(encoding="utf-8"))
        # 再调一次不会清空已有内容
        diary.write_day("2026-10-15", "已经写过的一天", self.path)
        diary.ensure_file(self.path)
        self.assertEqual(diary.read_day("2026-10-15", self.path), "已经写过的一天")

    def test_legacy_format_is_read_and_migrated(self) -> None:
        """老格式（每天是 ## 日期）要能读出来，并在启动时整理成「月 → 日」。"""
        from app import paths

        self.path.write_text(
            "# 日记\n\n"
            "<!-- 目录开始（由程序自动生成） -->\n"
            "## 目录\n\n"
            "- [2026-10-15 星期四](#2026-10-15-星期四)\n"
            "- [2026-10-13 星期二](#2026-10-13-星期二)\n"
            "<!-- 目录结束 -->\n\n"
            "## 2026-10-15 星期四\n\n下午那天的内容\n\n"
            "## 2026-10-13 星期二\n\n较早那天的内容\n",
            encoding="utf-8",
        )
        # 读取时就能正确解析出两天
        self.assertEqual(diary.read_day("2026-10-15", self.path), "下午那天的内容")
        self.assertEqual(diary.read_day("2026-10-13", self.path), "较早那天的内容")
        self.assertTrue(diary.looks_legacy(self.path.read_text(encoding="utf-8")))

        backups = self.tmp / "backups"
        original_backup_dir = paths.BACKUP_DIR
        paths.BACKUP_DIR = backups
        try:
            diary.ensure_file(self.path)
        finally:
            paths.BACKUP_DIR = original_backup_dir

        text = self.path.read_text(encoding="utf-8")
        self.assertFalse(diary.looks_legacy(text))
        self.assertIn("## 2026年10月", text)
        self.assertIn("### 2026-10-15 星期四", text)
        self.assertIn("### 2026-10-13 星期二", text)
        self.assertIn("- [2026年10月](#2026年10月)", text)
        # 内容一个字都没丢，而且旧文件有备份
        self.assertEqual(diary.read_day("2026-10-15", self.path), "下午那天的内容")
        self.assertEqual(diary.read_day("2026-10-13", self.path), "较早那天的内容")
        self.assertTrue(list(backups.glob("pre-migration-*.diary.md")))

    def test_write_then_read(self) -> None:
        diary.write_day("2026-10-15", "今天写了代码。", self.path)
        self.assertEqual(diary.read_day("2026-10-15", self.path), "今天写了代码。")
        self.assertEqual(diary.days_with_entries(self.path), ["2026-10-15"])

    def test_new_file_gets_a_title(self) -> None:
        diary.write_day("2026-10-15", "第一行", self.path)
        text = self.path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# 日记"))
        # 正文按「月 → 日」分组
        self.assertIn("## 2026年10月", text)
        self.assertIn("### 2026-10-15 星期四", text)

    def test_entries_are_newest_first(self) -> None:
        diary.write_day("2026-10-15", "晚的", self.path)
        diary.write_day("2026-10-12", "早的", self.path)
        diary.write_day("2026-10-13", "中间的", self.path)
        text = self.path.read_text(encoding="utf-8")
        body = text.split("<!-- 目录结束 -->")[1]
        self.assertLess(body.index("2026-10-15"), body.index("2026-10-13"))
        self.assertLess(body.index("2026-10-13"), body.index("2026-10-12"))

    def test_table_of_contents_on_top_with_links(self) -> None:
        diary.write_day("2026-10-13", "第一天", self.path)
        diary.write_day("2026-10-15", "第二天", self.path)
        diary.write_day("2026-09-30", "上个月", self.path)
        text = self.path.read_text(encoding="utf-8")

        # 目录在正文之前，标记包裹，只列到「年 月」，新的月份在前
        self.assertIn("<!-- 目录开始", text)
        self.assertIn("<!-- 目录结束 -->", text)
        toc = text.split("<!-- 目录开始")[1].split("<!-- 目录结束 -->")[0]
        self.assertIn("- [2026年10月](#2026年10月)", toc)
        self.assertIn("- [2026年9月](#2026年9月)", toc)
        self.assertNotIn("2026-10-15", toc, "目录不应该精确到某一天")
        self.assertLess(toc.index("2026年10月"), toc.index("2026年9月"))
        self.assertLess(text.index("<!-- 目录结束 -->"), text.index("## 2026年10月"))

    def test_month_section_holds_its_days_newest_first(self) -> None:
        diary.write_day("2026-10-13", "较早", self.path)
        diary.write_day("2026-10-15", "较晚", self.path)
        text = self.path.read_text(encoding="utf-8")
        month_block = text.split("## 2026年10月")[1]
        self.assertLess(month_block.index("2026-10-15"), month_block.index("2026-10-13"))
        self.assertEqual(text.count("## 2026年10月"), 1)

    def test_toc_is_rebuilt_when_a_month_loses_all_days(self) -> None:
        diary.write_day("2026-10-15", "十月", self.path)
        diary.write_day("2026-09-30", "九月", self.path)
        diary.write_day("2026-09-30", "", self.path)
        text = self.path.read_text(encoding="utf-8")
        toc = text.split("<!-- 目录开始")[1].split("<!-- 目录结束 -->")[0]
        self.assertNotIn("2026年9月", toc)
        self.assertIn("2026年10月", toc)
        self.assertNotIn("## 2026年9月", text)

    def test_toc_disappears_with_the_last_entry(self) -> None:
        diary.write_day("2026-10-15", "只有一天", self.path)
        diary.write_day("2026-10-15", "", self.path)
        text = self.path.read_text(encoding="utf-8")
        self.assertNotIn("目录", text)
        self.assertEqual(diary.entries(self.path), {})

    def test_update_only_touches_that_day(self) -> None:
        diary.write_day("2026-10-12", "第一天的内容", self.path)
        diary.write_day("2026-10-13", "第二天的内容", self.path)
        diary.write_day("2026-10-12", "第一天改过了\n\n第二段", self.path)

        self.assertEqual(diary.read_day("2026-10-12", self.path), "第一天改过了\n\n第二段")
        self.assertEqual(diary.read_day("2026-10-13", self.path), "第二天的内容")
        text = self.path.read_text(encoding="utf-8")
        self.assertEqual(text.count("## 2026-10-12"), 1)

    def test_empty_body_removes_that_day(self) -> None:
        diary.write_day("2026-10-12", "要删掉", self.path)
        diary.write_day("2026-10-13", "留着", self.path)
        diary.write_day("2026-10-12", "   \n  ", self.path)
        self.assertEqual(diary.days_with_entries(self.path), ["2026-10-13"])
        self.assertNotIn("2026-10-12", self.path.read_text(encoding="utf-8"))

    def test_handwritten_content_is_preserved(self) -> None:
        """自己在文件里加的东西（前言、非日期小节）不能被覆盖掉。"""
        self.path.write_text(
            "# 我的日记\n\n这是我自己加的一句说明。\n\n## 随手记\n\n不是按日期的内容\n",
            encoding="utf-8",
        )
        diary.write_day("2026-10-15", "程序写入的内容", self.path)
        text = self.path.read_text(encoding="utf-8")
        self.assertIn("这是我自己加的一句说明。", text)
        self.assertIn("## 随手记", text)
        self.assertIn("不是按日期的内容", text)
        self.assertIn("程序写入的内容", text)

    def test_weekday_label(self) -> None:
        self.assertEqual(diary.weekday_label("2026-10-15"), "星期四")
        self.assertEqual(diary.weekday_label("2026-10-18"), "星期日")


if __name__ == "__main__":
    unittest.main()
