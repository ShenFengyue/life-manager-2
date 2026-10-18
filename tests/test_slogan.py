"""左栏标语：改一次留一条历史，存在数据库里。"""

from __future__ import annotations

import unittest

from app import paths
from app.models import Slogan
from app.services import SLOGAN_MAX_LENGTH, LifeManagerService, ValidationError
from app.storage import SCHEMA_VERSION, Database
from tests._support import make_temp_dir, remove_temp_dir


class SloganServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = make_temp_dir()
        self._saved = {"BACKUP_DIR": paths.BACKUP_DIR, "EXPORT_DIR": paths.EXPORT_DIR}
        paths.BACKUP_DIR = self.tmp / "backups"
        paths.EXPORT_DIR = self.tmp / "exports"
        self.db = Database(self.tmp / "slogan.sqlite3")
        self.db.initialize()
        self.service = LifeManagerService(self.db)

    def tearDown(self) -> None:
        self.db.close()
        for key, value in self._saved.items():
            setattr(paths, key, value)
        remove_temp_dir(self.tmp)

    def test_empty_database_has_no_slogan(self) -> None:
        self.assertIsNone(self.service.current_slogan())
        self.assertEqual(self.service.slogan_history(), [])

    def test_each_change_keeps_a_history_entry(self) -> None:
        first = self.service.set_slogan("先把今天过明白")
        self.assertIsInstance(first, Slogan)
        self.assertEqual(self.service.current_slogan().text, "先把今天过明白")

        self.service.set_slogan("一次只推进一件事")
        history = self.service.slogan_history()
        self.assertEqual([item.text for item in history], ["一次只推进一件事", "先把今天过明白"])
        self.assertEqual(self.service.current_slogan().id, history[0].id)

    def test_same_text_is_not_recorded_twice(self) -> None:
        self.service.set_slogan("不变的这句话")
        self.service.set_slogan("不变的这句话")
        self.assertEqual(len(self.service.slogan_history()), 1)

    def test_blank_text_clears_the_slogan_but_keeps_history(self) -> None:
        self.service.set_slogan("先写一句")
        cleared = self.service.set_slogan("   ")
        self.assertEqual(cleared.text, "")
        self.assertEqual(self.service.current_slogan().text, "")
        self.assertEqual(cleared.display_text, "（已清空）")
        self.assertEqual(len(self.service.slogan_history()), 2)

    def test_text_is_trimmed(self) -> None:
        self.service.set_slogan("  两侧有空格  ")
        self.assertEqual(self.service.current_slogan().text, "两侧有空格")

    def test_too_long_text_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            self.service.set_slogan("字" * (SLOGAN_MAX_LENGTH + 1))
        self.assertEqual(self.service.slogan_history(), [])

    def test_old_database_gains_the_slogans_table(self) -> None:
        """老库（v3）升级时会自动补上标语表，并把结构版本推到最新。"""
        path = self.tmp / "old.sqlite3"
        db = Database(path)
        db.initialize()
        with db.transaction() as tx:
            tx.execute("DROP TABLE slogans")
            tx.execute("UPDATE meta SET value = '3' WHERE key = 'schema_version'")
        db.close()

        upgraded = Database(path)
        upgraded.initialize()
        tables = {
            row["name"]
            for row in upgraded.conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        self.assertIn("slogans", tables)
        version = upgraded.conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()["value"]
        self.assertEqual(version, str(SCHEMA_VERSION))
        upgraded.close()


if __name__ == "__main__":
    unittest.main()
