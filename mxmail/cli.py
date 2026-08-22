"""Command line front end for the triage rules.

Reads a Gmail message or thread (as JSON, exactly the shape the Gmail tools
return) and prints the drafting plan. Used both by hand and by the
``mx-mail-draft`` skill so that the routing decision is made the same way
every time.

    python3 -m mxmail.cli --thread samples/thread_matrox_po.json
    python3 -m mxmail.cli --message samples/message_customer_ja.json --format text
    cat thread.json | python3 -m mxmail.cli --thread -
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .triage import Config, Message, Triage, classify, load_config


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


def _newest_inbound(messages: list[Message], cfg: Config) -> Message | None:
    """The last message in the thread that someone else sent us."""
    for message in reversed(messages):
        if not cfg.is_owner(message.sender):
            return message
    return None


def _render_text(message: Message, triage: Triage) -> str:
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


def main(argv: list[str] | None = None) -> int:
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
        print(_render_text(target, result))
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


if __name__ == "__main__":
    raise SystemExit(main())
