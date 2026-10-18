"""北京时间：唯一时间来源的测试。"""

from __future__ import annotations

import re
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app import clock, models, paths


class BeijingClockTest(unittest.TestCase):
    def test_now_is_fixed_utc8(self) -> None:
        moment = clock.now()
        self.assertEqual(moment.utcoffset(), timedelta(hours=8))
        # 表盘读数必须等于"UTC 现在 + 8 小时"（不受本机时区设置影响）
        expected_wall = (datetime.now(timezone.utc) + timedelta(hours=8)).replace(tzinfo=None)
        actual_wall = moment.replace(tzinfo=None)
        self.assertLess(
            abs((expected_wall - actual_wall).total_seconds()), 2.0,
            "时钟不是按照 UTC+8 计算的",
        )

    def test_today_and_stamp_use_beijing(self) -> None:
        self.assertEqual(clock.today(), clock.now().date())
        self.assertEqual(clock.today_str(), clock.now().date().isoformat())
        stamp = clock.stamp()
        self.assertRegex(stamp, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
        parsed = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S")
        self.assertLess(abs((clock.now().replace(tzinfo=None) - parsed).total_seconds()), 2.0)

    def test_display_lines(self) -> None:
        moment, day = clock.display()
        self.assertRegex(moment, r"^\d{2}:\d{2}:\d{2}$")
        self.assertRegex(day, r"^\d{4}年\d{1,2}月\d{1,2}日 星期[一二三四五六日]$")

    def test_models_timestamps_are_beijing(self) -> None:
        """数据库写入用的时间戳走的是同一个北京时间来源。"""
        self.assertEqual(models.now_stamp(), clock.stamp())
        self.assertEqual(models.today_str(), clock.today_str())

    def test_only_clock_module_reads_system_time(self) -> None:
        """扫描源码：除 clock.py 外，不允许直接读系统时间或本地时区时间。"""
        banned = (
            re.compile(r"datetime\.now\(\s*\)"),
            re.compile(r"date\.today\(\s*\)"),
            re.compile(r"datetime\.utcnow\("),
            re.compile(r"time\.localtime\("),
            re.compile(r"datetime\.fromtimestamp\((?![^)]*tz=)"),
        )
        offenders: list[str] = []
        roots = [paths.ROOT / "app", paths.ROOT / "tools"]
        for root in roots:
            for file in root.rglob("*.py"):
                if file.name == "clock.py":
                    continue
                for number, line in enumerate(file.read_text(encoding="utf-8").splitlines(), 1):
                    if line.lstrip().startswith("#"):
                        continue
                    for pattern in banned:
                        if pattern.search(line):
                            offenders.append(f"{file.relative_to(paths.ROOT)}:{number}: {line.strip()}")
        self.assertEqual(offenders, [], "这些地方没有使用北京时间来源")


if __name__ == "__main__":
    unittest.main()
