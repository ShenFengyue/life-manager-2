"""日记：所有日记保存在项目内的**一个** Markdown 文件里。

文件结构：顶部是可跳转目录（只列到年、月），正文按「月 → 日」分组，最新的在最上面::

    # 日记

    <!-- 目录开始（由程序自动生成，这一块不用手改） -->
    ## 目录

    - [2026年10月](#2026年10月)
    - [2026年9月](#2026年9月)
    <!-- 目录结束 -->

    ## 2026年10月

    ### 2026-10-15 星期四

    今天写的内容……

    ### 2026-10-13 星期二

    前几天写的内容……

读写的原则是"保守"：只替换、新增或删除指定日期的那一节；目录自动重建；
其它内容（包括你自己在文件里加的文字）原样保留，只是会被排到日记正文之后。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import paths
from . import clock

DEFAULT_TEXT = "# 日记\n"
MONTH_HEADER = re.compile(r"^##\s+(\d{4})年(\d{1,2})月\s*$")
DAY_HEADER = re.compile(r"^###\s+(\d{4}-\d{2}-\d{2})\s*(.*)$")
# 老版本把每一天直接写成二级标题，这里兼容读取
LEGACY_DAY_HEADER = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s*(.*)$")
TOC_START = "<!-- 目录开始"
TOC_END = "<!-- 目录结束 -->"


def weekday_label(day: str) -> str:
    parsed = date.fromisoformat(day)
    return "星期" + "一二三四五六日"[parsed.weekday()]


def month_label(year: int, month: int) -> str:
    return f"{year}年{month}月"


@dataclass
class DayEntry:
    day: str
    body: str = ""


@dataclass
class MonthSection:
    year: int
    month: int
    entries: list[DayEntry] = field(default_factory=list)

    @property
    def label(self) -> str:
        return month_label(self.year, self.month)


@dataclass
class Block:
    """原样保留的内容（手工写的、不是按日期组织的部分）。"""

    header: str = ""
    body: str = ""


@dataclass
class Diary:
    preamble: str = ""
    months: list[MonthSection] = field(default_factory=list)
    others: list[Block] = field(default_factory=list)


def _split_sections(text: str) -> tuple[str, str]:
    """去掉目录块，返回（目录之前的前言, 正文）。"""
    lines = text.splitlines()
    start = next(
        (index for index, line in enumerate(lines) if line.strip().startswith(TOC_START)), None
    )
    end = next(
        (index for index, line in enumerate(lines) if line.strip().startswith(TOC_END)), None
    )
    if start is not None and end is not None and end > start:
        preamble = "\n".join(lines[:start]).strip("\n")
        body = "\n".join(lines[end + 1 :])
        return preamble, body
    # 没有目录标记（老文件或手工改过）：第一个标题之前都算前言
    first_section = next(
        (index for index, line in enumerate(lines) if line.startswith("## ")), None
    )
    if first_section is None:
        return text.strip("\n"), ""
    return "\n".join(lines[:first_section]).strip("\n"), "\n".join(lines[first_section:])


def parse(text: str) -> Diary:
    preamble, body = _split_sections(text)
    diary = Diary(preamble=preamble)
    month: MonthSection | None = None
    day: DayEntry | None = None
    other: Block | None = None

    def close_day() -> None:
        nonlocal day, month
        if day is None:
            return
        day.body = day.body.strip("\n")
        if month is None:
            # 手工写的文件里可能只有 ### 日期（没有月份标题），按日期补一个月份
            parsed = date.fromisoformat(day.day)
            month = MonthSection(year=parsed.year, month=parsed.month)
            diary.months.append(month)
        month.entries.append(day)
        day = None

    def close_other() -> None:
        nonlocal other
        if other is not None:
            other.body = other.body.strip("\n")
            diary.others.append(other)
            other = None

    for line in body.splitlines():
        if line.startswith("### "):
            close_day()
            close_other()
            match = DAY_HEADER.match(line)
            if match:
                day = DayEntry(day=match.group(1))
            else:
                other = Block(header=line.rstrip())
            continue
        if line.startswith("## "):
            close_day()
            close_other()
            match = MONTH_HEADER.match(line)
            if match:
                month = MonthSection(year=int(match.group(1)), month=int(match.group(2)))
                diary.months.append(month)
                continue
            legacy = LEGACY_DAY_HEADER.match(line)
            if legacy:
                parsed = date.fromisoformat(legacy.group(1))
                if month is None or (month.year, month.month) != (parsed.year, parsed.month):
                    month = next(
                        (
                            item
                            for item in diary.months
                            if (item.year, item.month) == (parsed.year, parsed.month)
                        ),
                        None,
                    )
                    if month is None:
                        month = MonthSection(year=parsed.year, month=parsed.month)
                        diary.months.append(month)
                day = DayEntry(day=legacy.group(1))
                continue
            month = None
            other = Block(header=line.rstrip())
            continue
        if day is not None:
            day.body += line + "\n"
        elif other is not None:
            other.body += line + "\n"
        elif line.strip():
            other = Block(body=line + "\n")
    close_day()
    close_other()
    return diary


def render(diary: Diary) -> str:
    months = sorted(diary.months, key=lambda item: (item.year, item.month), reverse=True)
    for month in months:
        month.entries.sort(key=lambda item: item.day, reverse=True)

    sections: list[str] = []
    if months:
        toc = [f"{TOC_START}（由程序自动生成，这一块不用手改） -->", "## 目录", ""]
        toc.extend(f"- [{month.label}](#{month.label})" for month in months)
        toc.append(TOC_END)
        sections.append("\n".join(toc))

    for month in months:
        pieces = [f"## {month.label}"]
        for entry in month.entries:
            piece = f"### {entry.day} {weekday_label(entry.day)}"
            if entry.body.strip():
                piece += "\n\n" + entry.body.strip("\n")
            pieces.append(piece)
        sections.append("\n\n".join(pieces))

    for other in diary.others:
        piece = other.header.strip()
        if other.body.strip():
            piece = f"{piece}\n\n{other.body.strip()}" if piece else other.body.strip()
        if piece.strip():
            sections.append(piece)

    parts: list[str] = []
    if diary.preamble.strip():
        parts.append(diary.preamble.strip("\n"))
    parts.extend(sections)
    return "\n\n".join(parts) + "\n"


def read_text(path: Path | None = None) -> str:
    target = Path(path) if path is not None else paths.DIARY_PATH
    if not target.exists():
        return DEFAULT_TEXT
    return target.read_text(encoding="utf-8")


def ensure_file(path: Path | None = None) -> Path:
    """确保日记文件存在，并把旧格式（每天写成二级标题）整理成新的「月 → 日」结构。

    整理前会把原文件备份到 data/backups/pre-migration-<时间>.diary.md。
    """
    target = Path(path) if path is not None else paths.DIARY_PATH
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        _write_atomic(target, DEFAULT_TEXT)
        return target

    text = target.read_text(encoding="utf-8")
    if looks_legacy(text):
        backup = paths.BACKUP_DIR / f"pre-migration-{_stamp()}.diary.md"
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_text(text, encoding="utf-8")
        _write_atomic(target, render(parse(text)))
    return target


def looks_legacy(text: str) -> bool:
    """是否还是旧格式（正文里直接出现 ## 日期 这种标题）。"""
    return any(
        LEGACY_DAY_HEADER.match(line) for line in text.splitlines() if line.startswith("## ")
    )


def _stamp() -> str:
    return clock.compact_stamp()


def read_day(day: str, path: Path | None = None) -> str:
    """读某一天的日记；没有就返回空串。"""
    for month in parse(read_text(path)).months:
        for entry in month.entries:
            if entry.day == day:
                return entry.body
    return ""


def entries(path: Path | None = None) -> dict[str, str]:
    """所有"有内容"的日记：日期 → 正文。"""
    result: dict[str, str] = {}
    for month in parse(read_text(path)).months:
        for entry in month.entries:
            if entry.body.strip():
                result[entry.day] = entry.body
    return result


def days_with_entries(path: Path | None = None) -> list[str]:
    """有日记的日期，按时间倒序（最近写的在最前）。"""
    return sorted(entries(path), reverse=True)


def append_to_day(day: str, text: str, path: Path | None = None) -> str:
    """把一段文字**追加**到某天的日记末尾，返回追加后的完整正文。

    同一天快速记好几次，就多出几段（用空行隔开）。**不会覆盖**那天已有的内容 ——
    所以 Ctrl+M 随手记一句，不会把你在日记页写过的整篇日记抹掉。
    追加的内容为空时什么都不做。
    """
    added = (text or "").strip()
    existing = read_day(day, path).strip("\n")
    if not added:
        return existing
    merged = f"{existing}\n\n{added}" if existing.strip() else added
    write_day(day, merged, path)
    return merged


def write_day(day: str, body: str, path: Path | None = None) -> None:
    """写入或更新某一天的日记；body 为空时删除这一天。"""
    target = Path(path) if path is not None else paths.DIARY_PATH
    date.fromisoformat(day)  # 校验日期格式
    diary = parse(read_text(target))
    body = (body or "").strip("\n")

    holder: tuple[MonthSection, DayEntry] | None = None
    for month in diary.months:
        for entry in month.entries:
            if entry.day == day:
                holder = (month, entry)
                break
        if holder is not None:
            break

    if holder is not None:
        month, entry = holder
        if body.strip():
            entry.body = body
        else:
            month.entries.remove(entry)
            if not month.entries:
                diary.months.remove(month)
    elif body.strip():
        parsed = date.fromisoformat(day)
        month = next(
            (
                item
                for item in diary.months
                if (item.year, item.month) == (parsed.year, parsed.month)
            ),
            None,
        )
        if month is None:
            month = MonthSection(year=parsed.year, month=parsed.month)
            diary.months.append(month)
        month.entries.append(DayEntry(day=day, body=body))

    target.parent.mkdir(parents=True, exist_ok=True)
    _write_atomic(target, render(diary))


def _write_atomic(target: Path, text: str) -> None:
    """先写临时文件再替换，避免写到一半被打断导致文件损坏。"""
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, target)
