"""快速记录（`Ctrl+N`）的匹配内核：先匹配节点，再写备注。

这里只有纯逻辑，不依赖 Qt，方便直接做单元测试。
界面部分在 `app/widgets/quick_capture.py`。

匹配规则（都不区分大小写）：

1. 关键字按空格拆成多个片段，每个片段都必须命中，才算是候选；
2. 命中名字的分数高于只命中归属路径的（方便输入"领域"缩小范围）；
3. 打分优先级：前缀 > 子串（越靠前越高）> 字符按顺序出现（模糊匹配，
   例如"英单"能匹配到"英语单词"）。
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import NodeType

DEFAULT_LIMIT = 8
RECENT_LIMIT = 6

_PREFIX_SCORE = 1000
_SUBSTRING_SCORE = 700
_SUBSTRING_MAX_PENALTY = 60
_FUZZY_SCORE = 600
_FUZZY_BASE = 180
_NAME_BONUS = 120


@dataclass(frozen=True)
class Candidate:
    """一个可以记录活动的目标：进程或线程。"""

    node_id: str
    name: str
    kind: NodeType
    parent_path: str

    @property
    def type_label(self) -> str:
        return self.kind.label

    @property
    def display(self) -> str:
        """列表里显示的一行文字：名字 · 归属路径。"""
        return f"{self.name} · {self.parent_path}" if self.parent_path else self.name


def build_candidates(service, *, include_archived: bool = False) -> list[Candidate]:
    """按 领域 → 进程 → 线程 的顺序收集可记录的目标。"""
    candidates: list[Candidate] = []
    for area in service.areas():
        if area.is_archived and not include_archived:
            continue
        for process in service.processes(area.id):
            if process.is_archived and not include_archived:
                continue
            candidates.append(
                Candidate(
                    node_id=process.id,
                    name=process.name,
                    kind=NodeType.PROCESS,
                    parent_path=area.name,
                )
            )
            for thread in service.threads(process.id):
                if thread.is_archived and not include_archived:
                    continue
                candidates.append(
                    Candidate(
                        node_id=thread.id,
                        name=thread.name,
                        kind=NodeType.THREAD,
                        parent_path=f"{area.name} → {process.name}",
                    )
                )
    return candidates


def _token_score(text: str, token: str) -> int:
    """单个片段对一个文本的匹配分；0 表示没命中。"""
    if not text or not token:
        return 0
    position = text.find(token)
    if position == 0:
        return _PREFIX_SCORE
    if position > 0:
        return _SUBSTRING_SCORE - min(position, _SUBSTRING_MAX_PENALTY)

    # 模糊匹配：字符按顺序出现即可，连续出现加分（"英单" → "英语单词"）。
    score = 0
    cursor = 0
    streak = 0
    for char in token:
        index = text.find(char, cursor)
        if index < 0:
            return 0
        streak = streak + 1 if index == cursor else 1
        score += 4 * streak + 1
        cursor = index + 1
    return min(_FUZZY_SCORE, _FUZZY_BASE + score)


def score_candidate(candidate: Candidate, tokens: list[str]) -> int:
    """候选的总分；只要有一个片段没命中就返回 0（直接淘汰）。"""
    name = candidate.name.lower()
    parent = candidate.parent_path.lower()
    total = 0
    for token in tokens:
        name_score = _token_score(name, token)
        parent_score = _token_score(parent, token)
        if not name_score and not parent_score:
            return 0
        total += max(name_score, parent_score)
        if name_score:
            total += _NAME_BONUS
    return total


def match(
    candidates: list[Candidate], query: str, limit: int = DEFAULT_LIMIT
) -> list[Candidate]:
    """按关键字挑出最相关的候选。"""
    tokens = [token for token in query.strip().lower().split() if token]
    if not tokens:
        return []
    scored: list[tuple[int, Candidate]] = []
    for candidate in candidates:
        value = score_candidate(candidate, tokens)
        if value:
            scored.append((value, candidate))
    scored.sort(key=lambda item: (-item[0], len(item[1].name), item[1].name))
    return [candidate for _value, candidate in scored[:limit]]


def recent_candidates(
    service, candidates: list[Candidate], limit: int = RECENT_LIMIT
) -> list[Candidate]:
    """最近记录过活动的节点（按时间倒序、去重、跳过已删或已归档的）。"""
    by_id = {candidate.node_id: candidate for candidate in candidates}
    result: list[Candidate] = []
    seen: set[str] = set()
    for activity in service.list_activities(limit=limit * 4):
        if activity.node_id in seen:
            continue
        seen.add(activity.node_id)
        candidate = by_id.get(activity.node_id)
        if candidate is not None:
            result.append(candidate)
        if len(result) >= limit:
            break
    return result
