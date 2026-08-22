---
name: mx-mail-draft
description: Triage mail arriving at taku_yamashita@mxvideo.jp and write reply drafts in the right language, plus the companion draft to the other side. Use when new mail from Matrox head office or a Japanese customer/partner needs a reply prepared, when asked to run the mail draft pass, or when asked to catch up on unanswered mail in that mailbox.
---

# mxvideo.jp mail draft workflow

The mailbox sits between two sides that do not speak to each other directly:

- **Matrox head office** (`@matrox.com`) — English.
- **Japanese customers, the distributor and field partners** — Japanese.

Almost every thread that matters needs *two* mails, not one: an answer to the
person who wrote in, and a note to the other side so the thread can actually
move. This skill prepares both as Gmail drafts. **It never sends.**

## Step 1 — collect what came in

```
mcp__Gmail__search_threads  query="to:taku_yamashita@mxvideo.jp is:unread in:inbox"
```

Widen as asked (`newer_than:3d`, a specific sender, `is:starred`). Search
results only preview the *oldest* messages of a thread, so for every candidate
thread call `mcp__Gmail__get_thread` with `messageFormat="PLAIN_TEXT"` before
deciding anything. The newest message is the one being answered; the rest is
the history the reply has to be consistent with.

## Step 2 — run the triage

Do not eyeball the routing. Save the thread JSON and run it through the rules
so every message is classified the same way:

```bash
python3 -m mxmail.cli --thread /path/to/thread.json --format text
```

It returns: skip or draft, which side wrote in, the reply language, and
whether a companion draft to the other side is warranted. Run it from the
repository root.

`action: skip` means newsletters, calendar notices, no-reply senders and the
owner's private (non-Matrox) mail. Skip them silently.

## Step 3 — decide the two languages

| Who wrote in | Reply to them | Companion draft |
|---|---|---|
| Matrox head office (English) | **English** | Japanese mail to the customer, *if needed* |
| Customer / partner (Japanese) | **Japanese** | English report to Matrox, *if needed* |
| Customer / partner **in English** | **English** | English report to Matrox — keep the whole thread English |

The last row is the standing exception: when a customer writes to you in
English, everything about that thread goes English, including the
customer-facing draft. The triage output reports this as
`unified_english: true`.

## Step 4 — decide whether the companion draft is really needed

"必要に応じて" — write it when the thread cannot move without the other side:

**Write it when** the incoming mail asks something you cannot answer alone
(stock, lead time, pricing, firmware, a defect that needs engineering), when
head office asks for a decision the customer has to make (shipping point,
schedule, spec confirmation), when a customer reports a fault that head office
should know about, or when an order, quotation or RMA changes state.

**Do not write it when** the mail closes out on one side — a thank-you, a
meeting time, a read-receipt, a newsletter, or an internal-only note where
nothing is owed to the other side. When in doubt, write the reply only and say
in your summary why you left the companion out.

The triage `confidence` field is a hint from keyword signals, not a verdict.
Read the thread and overrule it when the thread says otherwise.

## Step 5 — write the drafts

Read `references/style-guide.md` before writing the first one. In short:

- Ground every factual claim in the thread. If a number, date or part number
  is not in the history, do not invent it — leave a bracketed placeholder
  (`【要確認：出荷予定日】` / `[TBC: ship date]`) and flag it in your summary.
- Carry the counterparty's own terms and part numbers through verbatim.
- Keep the customer-facing Japanese mail free of Matrox-internal detail
  (internal case numbers, margins, colleagues' informal remarks).
- Answer every open question in the incoming mail. If one cannot be answered
  yet, say when it will be.

## Step 6 — create the drafts

Reply draft, always threaded onto the message being answered:

```
mcp__Gmail__create_draft
  replyToMessageId = <id of the message being answered>
  to  = <sender of that message>
  cc  = <keep the existing cc list minus the owner's own addresses>
  subject = "Re: <original subject>"
  body = <the draft>
```

Companion draft — a *new* mail to the other side, not a reply on the same
thread, unless a thread with that side already exists (then reply into it):

```
mcp__Gmail__create_draft
  to = <the other side's contact from the thread or config/routing.toml>
  subject = <clear subject naming the customer/case>
  body = <the draft>
```

## Step 7 — report back

For each thread handled, one line: subject, who it is from, what you drafted,
and anything the owner must fill in or verify before sending. List skipped
threads as a count, not individually. Never send, never archive, never label
without being asked.

## Boundaries

- Drafts only. Sending is the owner's decision, every time.
- No commitments on price, delivery date, or defect liability that are not
  already stated in the thread by the party who owns them.
- Anything legal, contractual, or a complaint about money or fault: draft it,
  then say plainly in your summary that it needs a careful read before sending.
- Unknown sender domain: draft, but flag it, and add the party to
  `config/routing.toml` if the owner confirms who they are.

## Reference

- `references/style-guide.md` — tone, openings, closings, signatures, worked examples.
- `references/parties.md` — who is who on each side.
- `../../../config/routing.toml` — domains, ignore list, companion signals.
