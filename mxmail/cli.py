"""Command line front end for the triage and linkage rules.

Two modes:

  triage  -- read one Gmail message or thread and print the drafting plan.
             This is the default, so the original flags still work:

                 python3 -m mxmail.cli --thread samples/thread_matrox_po.json
                 cat thread.json | python3 -m mxmail.cli --thread - --format text

  linkage -- read several threads at once and report cases where one side's
             news never reached the other:

                 python3 -m mxmail.cli linkage samples/linkage_*.json
                 python3 -m mxmail.cli linkage --dir /tmp/threads --format text

Pass full `get_thread` output to linkage. Search results only preview the
oldest messages of a thread, so a thread fetched by search alone will look
stale and produce a gap that is not real.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

from .linkage import Gap, ThreadRef, find_gaps
from .triage import Config, Message, Triage, classify, load_config


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------


def _read_json(source: str) -> Any:
    if source == "-":
        return json.load(sys.stdin)
    with open(source, encoding="utf-8") as fh:
        return json.load(fh)


def _messages_from_thread(payload: Any) -> list[Message]:
    if isinstance(payload, dict):
        raw = payload.get("messages", [payload])
    else:
        raw = payload
    return [Message.from_gmail(m) for m in raw]


def _threads_from_payload(payload: Any) -> list[ThreadRef]:
    """Accept a single thread, a list of threads, or a search-results object."""
    if isinstance(payload, dict):
        raw_threads = payload.get("threads", [payload])
    elif isinstance(payload, list):
        raw_threads = payload
    else:
        return []

    threads: list[ThreadRef] = []
    for raw in raw_threads:
        messages = _messages_from_thread(raw)
        if not messages:
            continue
        thread_id = raw.get("id") or messages[0].thread_id or ""
        threads.append(ThreadRef.build(thread_id, messages))
    return threads


# ---------------------------------------------------------------------------
# triage
# ---------------------------------------------------------------------------


def _newest_inbound(messages: list[Message], cfg: Config) -> Message | None:
    """The last message in the thread that someone else sent us."""
    for message in reversed(messages):
        if not cfg.is_owner(message.sender):
            return message
    return None


def _render_triage(message: Message, triage: Triage) -> str:
    lines = [
        f"subject : {message.subject}",
        f"from    : {message.sender}",
        f"action  : {triage.action}",
    ]
    if triage.action == "skip":
        lines.append(f"reason  : {triage.skip_reason}")
        return "\n".join(lines)

    party = triage.party
    if party is not None:
        who = f" ({party.kind}: {party.name_en})"
    elif triage.side == "matrox":
        who = " (Matrox head office)"
    else:
        who = " (unknown domain)"
    lines += [
        f"side    : {triage.side}{who}",
        f"incoming: {triage.incoming_language}",
        f"reply   : draft a reply in {triage.reply_language.upper()}",
    ]
    companion = triage.companion
    if companion:
        lines.append(
            f"also    : {companion.confidence} companion draft to "
            f"{companion.audience} in {companion.language.upper()}"
        )
        lines.append(f"          {companion.reason}")
        if companion.matched_signals:
            lines.append(f"          signals: {', '.join(companion.matched_signals)}")
    for note in triage.notes:
        lines.append(f"note    : {note}")
    return "\n".join(lines)


def _run_triage(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="mxmail",
        description="Decide what to draft for mail arriving at the mxvideo.jp mailbox.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--thread", metavar="PATH", help="Gmail thread JSON ('-' for stdin)"
    )
    source.add_argument(
        "--message", metavar="PATH", help="Gmail message JSON ('-' for stdin)"
    )
    parser.add_argument(
        "--config", metavar="PATH", default=None, help="override config/routing.toml"
    )
    parser.add_argument(
        "--format", choices=("json", "text"), default="json", help="output format"
    )
    args = parser.parse_args(argv)

    cfg = load_config(args.config)

    if args.thread:
        messages = _messages_from_thread(_read_json(args.thread))
        if not messages:
            parser.error("thread contains no messages")
        target = _newest_inbound(messages, cfg)
        if target is None:
            result = Triage(
                action="skip",
                skip_reason="thread has no inbound message to answer",
            )
            target = messages[-1]
        else:
            result = classify(target, cfg, thread=messages)
    else:
        target = Message.from_gmail(_read_json(args.message))
        result = classify(target, cfg)

    if args.format == "text":
        print(_render_triage(target, result))
    else:
        payload = result.to_dict()
        payload["message"] = {
            "id": target.message_id,
            "threadId": target.thread_id,
            "sender": target.sender,
            "subject": target.subject,
            "date": target.date,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


# ---------------------------------------------------------------------------
# linkage
# ---------------------------------------------------------------------------


_ARROW = {"jp_to_matrox": "JP  ->  MATROX", "matrox_to_jp": "MATROX  ->  JP"}


def _render_gaps(gaps: list[Gap], thread_count: int) -> str:
    if not gaps:
        return f"{thread_count} threads checked. No unrelayed handoffs found."

    lines = [f"{thread_count} threads checked. {len(gaps)} unrelayed handoff(s):", ""]
    for gap in gaps:
        lines += [
            f"[{gap.key}]  {_ARROW[gap.direction]}   {gap.age_days} days old",
            f"  news    : {gap.news_date}  {gap.news_sender}",
            f"  subject : {gap.news_subject}",
            f"  thread  : {gap.news_thread_id}",
            f"  waiting : {gap.unrelayed_count} message(s), latest {gap.latest_date}",
            f"  relayed : {gap.last_relay_date or 'never'}",
            f"  {gap.summary}",
            f"  > {gap.news_snippet}",
            "",
        ]
    return "\n".join(lines).rstrip()


def _run_linkage(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="mxmail linkage",
        description="Report cases where one side's news never reached the other.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="thread JSON files ('-' for stdin); full get_thread output",
    )
    parser.add_argument(
        "--dir", metavar="DIR", default=None, help="read every *.json in DIR"
    )
    parser.add_argument(
        "--config", metavar="PATH", default=None, help="override config/routing.toml"
    )
    parser.add_argument(
        "--min-age-days",
        type=int,
        default=2,
        help="ignore news younger than this (default 2)",
    )
    parser.add_argument(
        "--now",
        metavar="ISO8601",
        default=None,
        help="treat this instant as 'now' (for reproducible runs)",
    )
    parser.add_argument(
        "--format", choices=("json", "text"), default="text", help="output format"
    )
    args = parser.parse_args(argv)

    paths = list(args.paths)
    if args.dir:
        paths += sorted(glob.glob(os.path.join(args.dir, "*.json")))
    if not paths:
        parser.error("no thread files given; pass paths or --dir")

    cfg = load_config(args.config)

    threads: list[ThreadRef] = []
    for path in paths:
        threads += _threads_from_payload(_read_json(path))
    if not threads:
        parser.error("no threads found in the given files")

    now = None
    if args.now:
        now = datetime.fromisoformat(args.now.replace("Z", "+00:00"))
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

    gaps = find_gaps(threads, cfg, now=now, min_age_days=args.min_age_days)

    if args.format == "text":
        print(_render_gaps(gaps, len(threads)))
    else:
        print(
            json.dumps(
                {
                    "threadsChecked": len(threads),
                    "gaps": [g.to_dict() for g in gaps],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "linkage":
        return _run_linkage(argv[1:])
    if argv and argv[0] == "triage":
        return _run_triage(argv[1:])
    # No subcommand: triage, so the original flag-only invocation still works.
    return _run_triage(argv)


if __name__ == "__main__":
    raise SystemExit(main())
