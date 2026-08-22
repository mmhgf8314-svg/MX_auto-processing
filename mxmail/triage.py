"""Deterministic triage for mail arriving at taku_yamashita@mxvideo.jp.

The workflow this supports is:

    1. Read the incoming message and the thread it belongs to.
    2. Decide which side it came from -- Matrox head office, or a Japanese
       customer/partner.
    3. Draft the reply in the language the sender actually wrote in.
    4. Where the message cannot be closed out on one side alone, also draft a
       companion mail to the other side: a Japanese note to the customer when
       Matrox wrote in, an English report to Matrox when a customer wrote in.

Everything here is deterministic and testable. The judgement calls that need
an actual reading of the thread -- what to say, and whether the companion mail
is really warranted -- are left to the drafting agent; this module narrows the
decision and hands over the facts.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable, Sequence

__all__ = [
    "Companion",
    "Config",
    "Message",
    "Party",
    "Triage",
    "classify",
    "counterparty_language",
    "detect_language",
    "load_config",
    "strip_quoted",
]

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "routing.toml"

JA = "ja"
EN = "en"

# Hiragana, katakana, CJK ideographs and the fullwidth forms that come with
# Japanese business mail. Kanji alone is not enough to call a mail Japanese --
# an English mail can quote a Japanese name -- so kana carries extra weight.
_KANA_RE = re.compile(r"[぀-ヿ]")
_CJK_RE = re.compile(r"[㐀-䶿一-鿿＀-￯]")
_LATIN_RE = re.compile(r"[A-Za-z]")

_ADDRESS_RE = re.compile(r"[\w.+-]+@[\w.-]+")

# Lines that begin the quoted history of a reply.
_QUOTE_MARKERS = (
    re.compile(r"^\s*>"),
    re.compile(r"^\s*-{2,}\s*Original Message\s*-{2,}", re.I),
    re.compile(r"^\s*-{2,}\s*Forwarded message\s*-{2,}", re.I),
    re.compile(r"^\s*_{5,}\s*$"),
    re.compile(r"^\s*On .{5,80}\bwrote:\s*$", re.I),
    re.compile(r"^\s*\*?From:\*?\s", re.I),
    re.compile(r"^\s*\d{4}年\d{1,2}月\d{1,2}日.*:\s*$"),
    re.compile(r"^\s*\d{4}/\d{1,2}/\d{1,2}.*のメール\s*:?\s*$"),
)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Party:
    """A known counterparty, keyed by mail domain."""

    domain: str
    name_en: str
    name_ja: str
    kind: str
    default_language: str = JA
    notes: str = ""


@dataclass(frozen=True)
class Config:
    owner_mailbox: str
    owner_aliases: tuple[str, ...]
    owner: dict[str, Any]
    matrox_domains: tuple[str, ...]
    ignore_addresses: tuple[str, ...]
    ignore_localpart_patterns: tuple[str, ...]
    ignore_domains: tuple[str, ...]
    ignore_subject_patterns: tuple[str, ...]
    parties: tuple[Party, ...]
    handoff_signals: tuple[str, ...]
    low_signals: tuple[str, ...]

    def party_for(self, address: str) -> Party | None:
        domain = domain_of(address)
        for party in self.parties:
            if domain == party.domain or domain.endswith("." + party.domain):
                return party
        return None

    def is_matrox(self, address: str) -> bool:
        domain = domain_of(address)
        return any(
            domain == d or domain.endswith("." + d) for d in self.matrox_domains
        )

    def is_owner(self, address: str) -> bool:
        addr = normalize_address(address)
        return addr == self.owner_mailbox or addr in self.owner_aliases


def load_config(path: str | Path | None = None) -> Config:
    """Read routing.toml into a :class:`Config`."""
    path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    with open(path, "rb") as fh:
        raw = tomllib.load(fh)

    owner = raw.get("owner", {})
    sides = raw.get("sides", {})
    ignore = raw.get("ignore", {})
    signals = raw.get("companion_signals", {})

    parties = tuple(
        Party(
            domain=p["domain"].lower(),
            name_en=p.get("name_en", p["domain"]),
            name_ja=p.get("name_ja", p["domain"]),
            kind=p.get("kind", "customer"),
            default_language=p.get("default_language", JA),
            notes=p.get("notes", ""),
        )
        for p in raw.get("parties", [])
    )

    return Config(
        owner_mailbox=owner.get("mailbox", "").lower(),
        owner_aliases=tuple(a.lower() for a in owner.get("aliases", [])),
        owner=owner,
        matrox_domains=tuple(d.lower() for d in sides.get("matrox", [])),
        ignore_addresses=tuple(a.lower() for a in ignore.get("addresses", [])),
        ignore_localpart_patterns=tuple(
            p.lower() for p in ignore.get("localpart_patterns", [])
        ),
        ignore_domains=tuple(d.lower() for d in ignore.get("domains", [])),
        ignore_subject_patterns=tuple(ignore.get("subject_patterns", [])),
        parties=parties,
        handoff_signals=tuple(signals.get("handoff", [])),
        low_signals=tuple(signals.get("low_signal", [])),
    )


# ---------------------------------------------------------------------------
# Address helpers
# ---------------------------------------------------------------------------


def normalize_address(address: str) -> str:
    """Pull a bare address out of ``"Name <a@b.com>"`` and lowercase it."""
    if not address:
        return ""
    match = _ADDRESS_RE.search(address)
    return match.group(0).lower() if match else address.strip().lower()


def domain_of(address: str) -> str:
    addr = normalize_address(address)
    _, _, domain = addr.partition("@")
    return domain


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------


def strip_quoted(body: str) -> str:
    """Drop quoted history so language detection sees only what was written now.

    A Japanese customer replying in English still quotes the Japanese thread
    below their signature; counting that would flip the verdict.
    """
    kept: list[str] = []
    for line in body.splitlines():
        if any(marker.search(line) for marker in _QUOTE_MARKERS):
            break
        kept.append(line)
    text = "\n".join(kept).strip()
    # A reply that is nothing but quoted text: fall back to the whole body
    # rather than deciding the language from an empty string.
    return text if text else body.strip()


def detect_language(text: str, *, ignore_quotes: bool = True) -> str:
    """Return ``"ja"`` or ``"en"`` for a block of mail text.

    Kana is the strongest signal for Japanese: a single kana run means the
    author is writing Japanese. Kanji-only text (product codes, quoted names)
    is weighed against the Latin letter count instead.
    """
    body = strip_quoted(text) if ignore_quotes else text
    if not body.strip():
        return EN

    kana = len(_KANA_RE.findall(body))
    cjk = len(_CJK_RE.findall(body))
    latin = len(_LATIN_RE.findall(body))

    if kana == 0 and cjk == 0:
        return EN
    # Kana is decisive once there is more than an incidental character or two.
    if kana >= 3:
        return JA
    # Otherwise compare bulk: CJK characters carry far more meaning per glyph
    # than Latin letters, so weigh them accordingly.
    return JA if (kana + cjk) * 6 >= latin else EN


# ---------------------------------------------------------------------------
# Messages and triage results
# ---------------------------------------------------------------------------


@dataclass
class Message:
    """One mail, normalized from whatever source fetched it."""

    sender: str = ""
    subject: str = ""
    body: str = ""
    to: list[str] = field(default_factory=list)
    cc: list[str] = field(default_factory=list)
    date: str = ""
    message_id: str = ""
    thread_id: str = ""
    labels: list[str] = field(default_factory=list)

    @classmethod
    def from_gmail(cls, payload: dict[str, Any]) -> "Message":
        """Build from a Gmail ``get_message`` / ``get_thread`` message object."""
        return cls(
            sender=payload.get("sender", ""),
            subject=payload.get("subject", ""),
            body=payload.get("plaintextBody") or payload.get("snippet") or "",
            to=list(payload.get("toRecipients", []) or []),
            cc=list(payload.get("ccRecipients", []) or []),
            date=payload.get("date", ""),
            message_id=payload.get("id", ""),
            thread_id=payload.get("threadId", ""),
            labels=list(payload.get("labelIds", []) or []),
        )

    def searchable(self) -> str:
        return f"{self.subject}\n{self.body}"


@dataclass
class Companion:
    """The second draft: a note to the side that did not write in."""

    audience: str  # "customer" | "matrox"
    language: str  # "ja" | "en"
    confidence: str  # "suggested" | "unlikely"
    reason: str
    matched_signals: list[str] = field(default_factory=list)


@dataclass
class Triage:
    action: str  # "draft" | "skip"
    side: str = ""  # "matrox" | "external"
    party: Party | None = None
    incoming_language: str = ""
    reply_language: str = ""
    companion: Companion | None = None
    skip_reason: str = ""
    unified_english: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.party is None:
            data["party"] = None
        return data


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def _should_ignore(message: Message, cfg: Config) -> str:
    addr = normalize_address(message.sender)
    if not addr:
        return "sender address could not be parsed"
    if cfg.is_owner(addr):
        return "message was sent by the mailbox owner"
    if addr in cfg.ignore_addresses:
        return f"{addr} is a bulk/notification sender"

    local = addr.partition("@")[0]
    for pattern in cfg.ignore_localpart_patterns:
        if pattern in local:
            return f"sender local part matches no-reply pattern '{pattern}'"

    domain = domain_of(addr)
    for ignored in cfg.ignore_domains:
        if domain == ignored or domain.endswith("." + ignored):
            return f"{domain} is out of scope for business drafting"

    subject = message.subject or ""
    for pattern in cfg.ignore_subject_patterns:
        if pattern.lower() in subject.lower():
            return f"subject matches automated pattern '{pattern}'"

    return ""


def counterparty_language(
    thread: Sequence[Message], cfg: Config, *, default: str = JA
) -> str:
    """Language the non-Matrox side of a thread is actually writing in.

    This is what implements the stated exception -- 「時折お客様のメールが英語で
    来る時がある。その場合は英語で統一」. When the customer writes English, the
    whole thread, including the customer-facing companion draft, goes English.
    """
    for message in reversed(list(thread)):
        addr = normalize_address(message.sender)
        if not addr or cfg.is_matrox(addr) or cfg.is_owner(addr):
            continue
        return detect_language(message.searchable())
    return default


def _signal_matcher(signal: str) -> re.Pattern[str]:
    """Compile one signal into a matcher that does not fire on fragments.

    Short ASCII acronyms have to match as whole words -- otherwise "PO" hits
    every "point" and "shipping point" looks like a purchase order. Longer
    ASCII words match at a word start so "ship" still catches "shipment", and
    Japanese signals stay plain substrings because Japanese has no word
    boundaries for ``\\b`` to find.
    """
    escaped = re.escape(signal.strip())
    if not _LATIN_RE.search(signal):
        return re.compile(escaped)
    if len(signal.strip()) <= 3:
        return re.compile(rf"\b{escaped}\b", re.I)
    return re.compile(rf"\b{escaped}", re.I)


def _match_signals(haystack: str, signals: Iterable[str]) -> list[str]:
    return [s for s in signals if _signal_matcher(s).search(haystack)]


def _companion_signals(message: Message, cfg: Config) -> tuple[list[str], list[str]]:
    haystack = message.searchable()
    hits = _match_signals(haystack, cfg.handoff_signals)
    lows = _match_signals(haystack, cfg.low_signals)
    return hits, lows


def classify(
    message: Message,
    cfg: Config,
    *,
    thread: Iterable[Message] | None = None,
) -> Triage:
    """Decide what to draft for one incoming message.

    ``thread`` is the full conversation the message belongs to; it is used to
    work out which language the customer side of the thread is using.
    """
    skip_reason = _should_ignore(message, cfg)
    if skip_reason:
        return Triage(action="skip", skip_reason=skip_reason)

    sender = normalize_address(message.sender)
    party = cfg.party_for(sender)
    side = "matrox" if cfg.is_matrox(sender) else "external"

    incoming = detect_language(message.searchable())
    # Rule 1 and rule 2 agree on this: answer in the language you were written
    # in. It is also what makes the English-customer exception fall out for
    # free rather than needing a special case.
    reply_language = incoming

    thread_messages = list(thread) if thread is not None else [message]
    party_default = party.default_language if party else JA
    customer_language = counterparty_language(
        thread_messages, cfg, default=party_default
    )
    unified_english = customer_language == EN

    hits, lows = _companion_signals(message, cfg)
    notes: list[str] = []

    if side == "matrox":
        audience = "customer"
        # Normally Japanese, but English when the customer themselves is
        # writing English -- keep one language across the whole thread.
        language = EN if unified_english else JA
        if unified_english:
            notes.append(
                "Customer side of this thread writes in English; unify the "
                "customer-facing draft in English."
            )
    else:
        audience = "matrox"
        # Reports to head office are always English.
        language = EN

    if hits:
        confidence = "suggested"
        reason = (
            "The message raises something the other side has to act on or "
            "answer, so a companion draft is likely needed."
        )
    elif lows:
        confidence = "unlikely"
        reason = (
            "Reads as scheduling or informational traffic that closes out on "
            "one side; only draft the companion if the thread says otherwise."
        )
    else:
        confidence = "unlikely"
        reason = (
            "No handoff signal found. Read the thread before deciding -- draft "
            "the companion only if the other side genuinely needs it."
        )

    companion = Companion(
        audience=audience,
        language=language,
        confidence=confidence,
        reason=reason,
        matched_signals=hits or lows,
    )

    if side == "external" and party is None:
        notes.append(
            f"Unknown domain '{domain_of(sender)}'. Confirm who the "
            "counterparty is before drafting, and add them to "
            "config/routing.toml."
        )
    if side == "external" and incoming == EN:
        notes.append(
            "Customer wrote in English -- reply in English and keep the whole "
            "thread in English."
        )

    return Triage(
        action="draft",
        side=side,
        party=party,
        incoming_language=incoming,
        reply_language=reply_language,
        companion=companion,
        unified_english=unified_english,
        notes=notes,
    )
