"""Find news that arrived on one side of a case and never crossed to the other.

The mailbox runs two parallel conversations about the same piece of work: a
Japanese thread with the customer and the distributor, and an English thread
with Matrox head office, usually a support case. Nothing joins them except the
owner, by hand.

That is where things go missing. A customer answers on the Japanese thread --
"we reproduced it on the beta, we have the logs, where do we send them?" --
and unless someone carries it across, head office never learns it, keeps
asking, and the case sits. Triage cannot see this: it looks at one message at
a time, and each message on its own looks answered.

This module groups threads by the identifiers that actually appear in the mail
(support case numbers, Salesforce thread tokens, PO numbers, the bracketed
project tags Japanese threads use in the subject), works out which side of the
conversation each thread belongs to, and reports where one side has newer news
than the owner has relayed to the other.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Sequence

from .triage import Config, Message, normalize_address

__all__ = [
    "CaseKey",
    "canonical_key",
    "Gap",
    "ThreadRef",
    "extract_keys",
    "find_gaps",
    "group_by_key",
    "thread_has_matrox",
]

# ---------------------------------------------------------------------------
# Case identifiers
# ---------------------------------------------------------------------------

# "Case 00092203", "case #00092203"
_CASE_RE = re.compile(r"\bcase\s*#?\s*(\d{6,8})\b", re.I)
# A bare Salesforce case number, which is what people paste in a hurry.
_BARE_CASE_RE = re.compile(r"\b(00\d{6})\b")
# The token Matrox's ticketing system carries in every subject line.
_SF_THREAD_RE = re.compile(r"thread::([A-Za-z0-9_\-]+)::")
# Japan Material purchase orders.
_PO_RE = re.compile(r"\b(JMGS\d{4,6})\b", re.I)
# The 【...】 project tag Japanese subjects use, e.g. 【TBS統合FB】.
_TAG_RE = re.compile(r"【([^】]{2,30})】")

# 【...】 is also used for ordinary decoration. These never identify a case.
_TAG_STOPLIST = {
    "重要", "秘密", "再送", "至急", "社内", "確認", "お知らせ", "ご案内",
    "緊急", "注意", "参考", "転送", "返信不要", "無料", "PR", "広告",
}


@dataclass(frozen=True, order=True)
class CaseKey:
    """One identifier two threads can share."""

    kind: str  # "case" | "sf_thread" | "po" | "tag"
    value: str

    def __str__(self) -> str:
        return f"{self.kind}:{self.value}"


def _tag_is_meaningful(tag: str) -> bool:
    tag = tag.strip()
    if not tag or tag in _TAG_STOPLIST:
        return False
    # A tag that merely repeats a stoplist word plus punctuation is still noise.
    return not any(tag == f"{word}！" or tag == f"{word}!" for word in _TAG_STOPLIST)


def extract_keys(message: Message, *, subject_only_tags: bool = True) -> set[CaseKey]:
    """Pull every case identifier out of one message.

    Bracketed tags are read from the subject only. In a body they are far more
    often decoration (【要確認：…】, 【IBC 2026 展示概要】) than an identifier.
    """
    keys: set[CaseKey] = set()
    subject = message.subject or ""
    haystack = f"{subject}\n{message.body or ''}"

    for match in _CASE_RE.finditer(haystack):
        keys.add(CaseKey("case", match.group(1)))
    for match in _BARE_CASE_RE.finditer(haystack):
        keys.add(CaseKey("case", match.group(1)))
    for match in _SF_THREAD_RE.finditer(haystack):
        keys.add(CaseKey("sf_thread", match.group(1)))
    for match in _PO_RE.finditer(haystack):
        keys.add(CaseKey("po", match.group(1).upper()))

    tag_source = subject if subject_only_tags else haystack
    for match in _TAG_RE.finditer(tag_source):
        tag = match.group(1).strip()
        if _tag_is_meaningful(tag):
            keys.add(CaseKey("tag", tag))

    return keys


# ---------------------------------------------------------------------------
# Threads
# ---------------------------------------------------------------------------


@dataclass
class ThreadRef:
    """A thread, reduced to what gap detection needs."""

    thread_id: str
    subject: str
    messages: list[Message]
    keys: set[CaseKey] = field(default_factory=set)

    @classmethod
    def build(cls, thread_id: str, messages: Sequence[Message]) -> "ThreadRef":
        keys: set[CaseKey] = set()
        for message in messages:
            keys |= extract_keys(message)
        subject = messages[0].subject if messages else ""
        return cls(
            thread_id=thread_id,
            subject=subject,
            messages=list(messages),
            keys=keys,
        )


def thread_has_matrox(thread: ThreadRef, cfg: Config) -> bool:
    """True when head office is actually on the thread.

    Sender *and* recipients count: a case thread where the owner writes to
    support and support has not replied yet is still an English-side thread.
    The owner's own addresses do not count -- they are on both sides.
    """
    for message in thread.messages:
        for address in [message.sender, *message.to, *message.cc]:
            addr = normalize_address(address)
            if not addr or cfg.is_owner(addr):
                continue
            if cfg.is_matrox(addr):
                return True
    return False


def _parse_date(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _collect(
    threads: Iterable[ThreadRef],
    predicate,
) -> list[tuple[Message, ThreadRef, datetime]]:
    """Every message across `threads` matching `predicate`, oldest first."""
    found: list[tuple[Message, ThreadRef, datetime]] = []
    for thread in threads:
        for message in thread.messages:
            if not predicate(message):
                continue
            when = _parse_date(message.date)
            if when is not None:
                found.append((message, thread, when))
    found.sort(key=lambda item: item[2])
    return found


def _newest(
    threads: Iterable[ThreadRef],
    predicate,
) -> tuple[Message, ThreadRef, datetime] | None:
    """The most recent message across `threads` for which `predicate` holds."""
    found = _collect(threads, predicate)
    return found[-1] if found else None


# ---------------------------------------------------------------------------
# Grouping and gap detection
# ---------------------------------------------------------------------------


def canonical_key(key: CaseKey, cfg: Config) -> CaseKey:
    """Fold a raw identifier onto the case it belongs to.

    The two sides of a case usually carry different identifiers -- a project
    tag in Japanese, a case number and a Salesforce token in English -- so the
    register in routing.toml says which ones mean the same case. An identifier
    with no register entry is its own key, which still matches threads that
    quote the same PO or case number on both sides.
    """
    case_id = cfg.case_for_alias(key.value)
    return CaseKey("case", case_id) if case_id else key


def group_by_key(
    threads: Sequence[ThreadRef], cfg: Config
) -> dict[CaseKey, list[ThreadRef]]:
    """Index threads by every case they belong to, one entry per case."""
    groups: dict[CaseKey, list[ThreadRef]] = {}
    for thread in threads:
        for key in {canonical_key(k, cfg) for k in thread.keys}:
            groups.setdefault(key, []).append(thread)
    return groups


@dataclass
class Gap:
    """News on one side that the owner has not carried to the other."""

    key: CaseKey
    direction: str  # "jp_to_matrox" | "matrox_to_jp"
    news_date: str
    news_sender: str
    news_subject: str
    news_thread_id: str
    news_snippet: str
    last_relay_date: str | None
    latest_date: str
    unrelayed_count: int
    age_days: int
    summary: str

    def to_dict(self) -> dict[str, object]:
        return {
            "key": str(self.key),
            "direction": self.direction,
            "news": {
                "date": self.news_date,
                "sender": self.news_sender,
                "subject": self.news_subject,
                "threadId": self.news_thread_id,
                "snippet": self.news_snippet,
            },
            "lastRelay": self.last_relay_date,
            "latestUnrelayed": self.latest_date,
            "unrelayedCount": self.unrelayed_count,
            "ageDays": self.age_days,
            "summary": self.summary,
        }


_DIRECTION_TEXT = {
    "jp_to_matrox": (
        "The Japanese side has answered since you last wrote to Matrox about "
        "this. Head office does not have it yet."
    ),
    "matrox_to_jp": (
        "Matrox has answered since you last wrote to the Japanese side about "
        "this. The customer or distributor does not have it yet."
    ),
}


def _gap_for_direction(
    key: CaseKey,
    direction: str,
    news_side: Sequence[ThreadRef],
    relay_side: Sequence[ThreadRef],
    cfg: Config,
    now: datetime,
    min_age_days: int,
) -> Gap | None:
    relay = _newest(relay_side, lambda m: cfg.is_owner(m.sender))
    relay_at = relay[2] if relay else None

    # Everything the other side has said since the owner last carried news
    # across. A fresh chaser does not close a gap that opened weeks ago, so
    # the whole backlog matters, not just the newest message.
    unrelayed = [
        item
        for item in _collect(news_side, lambda m: not cfg.is_owner(m.sender))
        if relay_at is None or item[2] > relay_at
    ]
    if not unrelayed:
        return None

    # Age the gap from when it opened, not from the most recent reminder.
    message, thread, when = unrelayed[0]
    age = (now - when).days
    if age < min_age_days:
        return None

    snippet = " ".join((message.body or "").split())[:180]
    return Gap(
        key=key,
        direction=direction,
        news_date=message.date,
        news_sender=normalize_address(message.sender),
        news_subject=message.subject,
        news_thread_id=thread.thread_id,
        news_snippet=snippet,
        last_relay_date=relay[0].date if relay else None,
        latest_date=unrelayed[-1][0].date,
        unrelayed_count=len(unrelayed),
        age_days=age,
        summary=_DIRECTION_TEXT[direction],
    )


def find_gaps(
    threads: Sequence[ThreadRef],
    cfg: Config,
    *,
    now: datetime | None = None,
    min_age_days: int = 2,
) -> list[Gap]:
    """Report every case where one side's news has not reached the other.

    `min_age_days` keeps same-day traffic out of the report -- a customer who
    wrote this morning is not a dropped handoff, just mail waiting its turn.
    """
    now = now or datetime.now(timezone.utc)
    gaps: list[Gap] = []
    seen: set[tuple[str, str, str]] = set()

    for key, group in sorted(group_by_key(threads, cfg).items()):
        if len(group) < 2:
            continue
        matrox_side = [t for t in group if thread_has_matrox(t, cfg)]
        jp_side = [t for t in group if not thread_has_matrox(t, cfg)]
        if not matrox_side or not jp_side:
            continue

        for direction, news_side, relay_side in (
            ("jp_to_matrox", jp_side, matrox_side),
            ("matrox_to_jp", matrox_side, jp_side),
        ):
            gap = _gap_for_direction(
                key, direction, news_side, relay_side, cfg, now, min_age_days
            )
            if gap is None:
                continue
            # One case carries several keys; report each real gap once.
            fingerprint = (direction, gap.news_thread_id, gap.news_date)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            gaps.append(gap)

    gaps.sort(key=lambda g: g.age_days, reverse=True)
    return gaps
