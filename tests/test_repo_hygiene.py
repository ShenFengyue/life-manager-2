"""仓库卫生：私人数据绝不能进 Git。

这条检查直接对应需求：「隐私和数据不要上传，并且保证之后的记录也不会」——
只要 .gitignore 里的规则被误删，测试就会红。
"""

from __future__ import annotations

import subprocess
import unittest

from app import paths

REQUIRED_PATTERNS = ("data/", ".venv/", ".preview/", ".test_tmp/", "__pycache__/")


class RepoHygieneTest(unittest.TestCase):
    def test_gitignore_excludes_private_data(self) -> None:
        ignore_file = paths.ROOT / ".gitignore"
        self.assertTrue(ignore_file.exists(), "缺少 .gitignore，私人数据会被误传")
        text = ignore_file.read_text(encoding="utf-8")
        for pattern in REQUIRED_PATTERNS:
            self.assertIn(pattern, text, f".gitignore 缺少规则：{pattern}")

    def test_no_private_file_is_tracked_by_git(self) -> None:
        if not (paths.ROOT / ".git").exists():
            self.skipTest("当前还不是 Git 仓库")
        result = subprocess.run(
            ["git", "ls-files", "data"],
            cwd=paths.ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.stdout.strip(), "", "data/ 里出现了被 Git 跟踪的文件（私人数据泄露）"
        )


if __name__ == "__main__":
    unittest.main()
