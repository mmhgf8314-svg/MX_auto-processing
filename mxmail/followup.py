"""Reply-waiting bookkeeping for the taku_yamashita@mxvideo.jp mailbox.

Triage answers "what do I draft for this message". Linkage answers "what fell
between the two conversations". This module answers the third question:

    which threads are stalled on the other side, and for how long?

The answer drives two things -- the `00_返信待ち` label, and whether a chase
mail is due -- and both have to be stable across runs. A morning routine that
re-derives "how long has this been waiting" from scratch every day will
disagree with itself the moment the clock, the timezone or the message set
shifts slightly, and the visible symptom is duplicate chase drafts in the
owner's mailbox. So everything here is deterministic, takes `now` as an
argument, and is tested.

Three things are computed:

  * `assess()`    -- per thread: who holds the ball, since when, in how many
                     business days, from which of the owner's addresses a
                     chase would have to go out.
  * `find_bulk()` -- which of the owner's own sent messages are one mail
                     written once and posted to thirty people. Those are
                     announcements, not requests, and must never enter the
                     waiting list.
  * `chase_plan()`-- given the assessments and the labels already on the
                     threads, the list of chases actually due, capped.

What is deliberately *not* here: whether a given reply is a real answer or
just "確認します、後ほど回答します". That reading needs the thread, and the
agent does it. This module surfaces the acknowledgement signals and leaves the
verdict alone, the same way triage treats `companion_signals`.
"""

from __future__ import annotations

import hashlib
import re
import tomllib
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Sequence

from .triage import DEFAULT_CONFIG_PATH, Config, Message, strip_quoted

__all__ = [
    "Assessment",
    "BulkGroup",
    "Chase",
    "FollowupSettings",
    "assess",
    "business_days_elapsed",
    "chase_plan",
    "find_bulk",
    "load_followup_settings",
    "owner_send_address",
]

JST = timezone(timedelta(hours=9))

# Replies that acknowledge without answering. Presented as a signal, never as
# a verdict -- see the module docstring.
_ACK_PATTERNS = (
    "確認します",
    "確認いたします",
    "確認中",
    "後ほど",
    "追ってご連絡",
    "折り返し",
    "少々お待ち",
    "しばらくお待ち",
    "get back to you",
    "will check",
    "looking into",
    "once i have",
    "as soon as possible",
)

# Lines carrying a personal honorific are the personalised part of a mail
# merge. Dropping them is what lets thirty otherwise-identical announcements
# collapse onto one fingerprint.
_HONORIFIC_RE = re.compile(r"(様|さん|御中|Dear\s|Hi\s|Hello\s)")
_WS_RE = re.compile(r"\s+")


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FollowupSettings:
    """The `[followup]` table of config/routing.toml."""

    waiting_label: str = "00_返信待ち"
    waiting_label_id: str = "Label_16"
    chased_label: str = "00_催促済み"
    chased_label_id: str = "Label_17"
    chase_after_business_days: int = 3
    max_chases_per_run: int = 5
    bulk_min_recipients: int = 3
    bulk_window_hours: int = 24
    holidays: frozenset[date] = frozenset()
    default_from: str = "taku_yamashita@mxvideo.jp"
    # domain of the counterparty -> address the owner should send as
    from_map: dict[str, str] = field(default_factory=dict)


def load_followup_settings(path: str | Path | None = None) -> FollowupSettings:
    """Read the `[followup]` table of routing.toml.

    Read straight from the file rather than off :class:`Config`. `Config` is
    frozen and does not carry the raw TOML, and widening it for one consumer
    would put triage at risk for no gain here.
    """
    path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    try:
        with open(path, "rb") as fh:
            raw = tomllib.load(fh)
    except FileNotFoundError:
        raw = {}
    table = raw.get("followup", {})
    holidays = frozenset(
        date.fromisoformat(d) for d in table.get("holidays", []) if isinstance(d, str)
    )
    defaults = FollowupSettings()
    return FollowupSettings(
        waiting_label=table.get("waiting_label", defaults.waiting_label),
        waiting_label_id=table.get("waiting_label_id", defaults.waiting_label_id),
        chased_label=table.get("chased_label", defaults.chased_label),
        chased_label_id=table.get("chased_label_id", defaults.chased_label_id),
        chase_after_business_days=int(
            table.get("chase_after_business_days", defaults.chase_after_business_days)
        ),
        max_chases_per_run=int(
            table.get("max_chases_per_run", defaults.max_chases_per_run)
        ),
        bulk_min_recipients=int(
            table.get("bulk_min_recipients", defaults.bulk_min_recipients)
        ),
        bulk_window_hours=int(table.get("bulk_window_hours", defaults.bulk_window_hours)),
        holidays=holidays,
        default_from=table.get("default_from", defaults.default_from),
        from_map=dict(table.get("from_map", {})),
    )


# ---------------------------------------------------------------------------
# Time
# ---------------------------------------------------------------------------


def _to_jst(value: datetime | str) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(JST)


def business_days_elapsed(
    sent: datetime | str,
    now: datetime | str,
    holidays: Iterable[date] = (),
) -> int:
    """Weekdays that have passed since `sent`, counted in JST.

    The day the mail went out does not count -- nobody owes an answer the same
    afternoon -- and the current day does, because by the time the routine runs
    in the morning the recipient has had the whole previous day.

    Counting in JST rather than UTC is not a nicety. The routine fires at 23:00
    UTC, which is 08:00 the *next* day in Tokyo; a UTC count is a day short
    every single run, and a chase that should go out on Thursday goes out on
    Friday.
    """
    holiday_set = set(holidays)
    start = _to_jst(sent).date()
    end = _to_jst(now).date()
    if end <= start:
        return 0
    count = 0
    day = start + timedelta(days=1)
    while day <= end:
        if day.weekday() < 5 and day not in holiday_set:
            count += 1
        day += timedelta(days=1)
    return count


def calendar_days_elapsed(sent: datetime | str, now: datetime | str) -> int:
    return max(0, (_to_jst(now).date() - _to_jst(sent).date()).days)


# ---------------------------------------------------------------------------
# Bulk announcements
# ---------------------------------------------------------------------------


def _fingerprint(message: Message) -> str:
    """A hash of the mail with its personalised lines removed.

    An event announcement is written once and sent to thirty people with the
    addressee line swapped and the recipient's name spliced into one sentence.
    Both of those carry an honorific, so dropping honorific-bearing lines
    leaves the shared body -- and thirty mails land on one fingerprint.
    """
    body = strip_quoted(message.body or "")
    kept = [
        line
        for line in body.splitlines()
        if line.strip() and not _HONORIFIC_RE.search(line)
    ]
    normalised = _WS_RE.sub("", "".join(kept))
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class BulkGroup:
    """One mail merge: the same body posted to several recipients."""

    fingerprint: str
    thread_ids: tuple[str, ...]
    recipients: tuple[str, ...]
    subject: str

    @property
    def size(self) -> int:
        return len(self.thread_ids)


def find_bulk(
    sent: Sequence[Message],
    settings: FollowupSettings | None = None,
) -> dict[str, BulkGroup]:
    """Map thread id -> the mail merge it belongs to.

    Only groups of at least `bulk_min_recipients` count. Two mails that happen
    to share boilerplate are not an announcement; thirty are.

    A bulk announcement asks a real question often enough ("ご参加のご予定は
    ございますでしょうか") that no keyword test will separate it from a genuine
    request. The shape does: a request is written to one person, an
    announcement is written once and addressed to a list.
    """
    settings = settings or FollowupSettings()
    buckets: dict[str, list[Message]] = {}
    for message in sent:
        if not (message.body or "").strip():
            continue
        buckets.setdefault(_fingerprint(message), []).append(message)

    result: dict[str, BulkGroup] = {}
    for fingerprint, group in buckets.items():
        threads = {m.thread_id for m in group if m.thread_id}
        if len(threads) < settings.bulk_min_recipients:
            continue
        recipients = tuple(
            sorted({r for m in group for r in (m.to or [])})
        )
        bulk = BulkGroup(
            fingerprint=fingerprint,
            thread_ids=tuple(sorted(threads)),
            recipients=recipients,
            subject=group[0].subject or "",
        )
        for thread_id in threads:
            result[thread_id] = bulk
    return result


# ---------------------------------------------------------------------------
# Per-thread assessment
# ---------------------------------------------------------------------------


def owner_send_address(messages: Sequence[Message], cfg: Config, default: str) -> str:
    """Which of the owner's addresses a chase on this thread must go out from.

    Read it off the thread rather than off a lookup table. The owner already
    chose an identity when the thread started -- Matrox, MADOKA, the surf
    school -- and the correct answer is simply to keep using it. A table maps
    domains and gets the multi-hat cases wrong.
    """
    for message in reversed(messages):
        if cfg.is_owner(message.sender) and message.sender:
            return message.sender.strip().lower()
    return default


def _has_ack_signal(text: str) -> bool:
    lowered = (text or "").lower()
    return any(p.lower() in lowered for p in _ACK_PATTERNS)


@dataclass
class Assessment:
    """What the routine needs to know about one thread."""

    thread_id: str
    subject: str
    state: str  # "waiting" | "owner_ball" | "bulk" | "empty"
    last_owner_send: str | None = None
    last_inbound: str | None = None
    business_days: int = 0
    calendar_days: int = 0
    counterparty: str | None = None
    from_address: str | None = None
    ack_only_signal: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def is_waiting(self) -> bool:
        return self.state == "waiting"

    def to_dict(self) -> dict:
        return {
            "threadId": self.thread_id,
            "subject": self.subject,
            "state": self.state,
            "lastOwnerSend": self.last_owner_send,
            "lastInbound": self.last_inbound,
            "businessDays": self.business_days,
            "calendarDays": self.calendar_days,
            "counterparty": self.counterparty,
            "fromAddress": self.from_address,
            "ackOnlySignal": self.ack_only_signal,
            "notes": list(self.notes),
        }


def assess(
    thread_id: str,
    messages: Sequence[Message],
    cfg: Config,
    now: datetime | str,
    settings: FollowupSettings | None = None,
    bulk: dict[str, BulkGroup] | None = None,
) -> Assessment:
    """Decide who holds the ball on one thread, and for how long.

    `waiting` means the newest message is the owner's. That is the whole test,
    and it is deliberately blunt: any cleverer reading of "did they really
    answer" belongs to the agent, which has the thread in front of it.

    The one hint offered is `ack_only_signal`, raised when the newest inbound
    message looks like "確認します" and nothing else. A thread whose last word
    is an acknowledgement is still stalled, and dropping the label there is how
    a case quietly disappears from the list for three weeks.
    """
    settings = settings or FollowupSettings()
    ordered = sorted(messages, key=lambda m: m.date or "")
    if not ordered:
        return Assessment(thread_id=thread_id, subject="", state="empty")

    subject = ordered[-1].subject or ordered[0].subject or ""

    if bulk and thread_id in bulk:
        group = bulk[thread_id]
        return Assessment(
            thread_id=thread_id,
            subject=subject,
            state="bulk",
            notes=[
                f"one of {group.size} copies of the same announcement "
                f"(fingerprint {group.fingerprint}); not a request"
            ],
        )

    newest = ordered[-1]
    owner_messages = [m for m in ordered if cfg.is_owner(m.sender)]
    inbound = [m for m in ordered if not cfg.is_owner(m.sender)]

    last_owner_send = owner_messages[-1].date if owner_messages else None
    last_inbound = inbound[-1].date if inbound else None
    counterparty = inbound[-1].sender if inbound else (
        (newest.to or [None])[0]
    )

    if not cfg.is_owner(newest.sender):
        return Assessment(
            thread_id=thread_id,
            subject=subject,
            state="owner_ball",
            last_owner_send=last_owner_send,
            last_inbound=last_inbound,
            counterparty=counterparty,
            from_address=owner_send_address(ordered, cfg, settings.default_from),
            ack_only_signal=_has_ack_signal(strip_quoted(newest.body or "")),
            notes=["newest message is inbound; the owner owes the next move"],
        )

    return Assessment(
        thread_id=thread_id,
        subject=subject,
        state="waiting",
        last_owner_send=last_owner_send,
        last_inbound=last_inbound,
        business_days=business_days_elapsed(
            last_owner_send or newest.date, now, settings.holidays
        ),
        calendar_days=calendar_days_elapsed(last_owner_send or newest.date, now),
        counterparty=counterparty,
        from_address=owner_send_address(ordered, cfg, settings.default_from),
        ack_only_signal=(
            _has_ack_signal(strip_quoted(inbound[-1].body or "")) if inbound else False
        ),
    )


# ---------------------------------------------------------------------------
# Chase planning
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Chase:
    thread_id: str
    subject: str
    business_days: int
    from_address: str
    reason: str


def chase_plan(
    assessments: Sequence[Assessment],
    already_chased: Iterable[str] = (),
    has_open_draft: Iterable[str] = (),
    settings: FollowupSettings | None = None,
) -> tuple[list[Chase], list[Chase]]:
    """Split due chases into (to write now, deferred).

    Two independent guards, because they fail differently. The
    `00_催促済み` label is durable and survives the run; the open-draft check
    catches the case the label cannot -- a second session running *at the same
    time* as this one, which is exactly how eleven duplicate drafts appeared in
    this mailbox on 2026-09-03.

    The cap is the third guard. A rule that fires on a backlog will try to send
    thirty chases the first morning it is switched on, and a mailbox that
    produces thirty drafts in one go gets its automation turned off by lunch.
    """
    settings = settings or FollowupSettings()
    chased = set(already_chased)
    drafted = set(has_open_draft)

    due: list[Chase] = []
    for a in assessments:
        if not a.is_waiting:
            continue
        if a.business_days < settings.chase_after_business_days:
            continue
        if a.thread_id in chased:
            continue
        if a.thread_id in drafted:
            continue
        due.append(
            Chase(
                thread_id=a.thread_id,
                subject=a.subject,
                business_days=a.business_days,
                from_address=a.from_address or settings.default_from,
                reason=f"{a.business_days} business days with no reply",
            )
        )

    due.sort(key=lambda c: c.business_days, reverse=True)
    cap = settings.max_chases_per_run
    return due[:cap], due[cap:]
