---
name: mx-followup
description: Track which threads are stalled on the other side in the taku_yamashita@mxvideo.jp mailbox, keep the 00_返信待ち label current, and prepare chase drafts for anything past three business days. Use for the morning reply-waiting pass, when asked which threads are waiting on a reply, or when asked to prepare follow-up mail.
---

# Reply-waiting pass

`mx-mail-draft` answers incoming mail. This skill does the opposite: it finds
the threads where **nobody owes the owner anything and nothing is happening**,
and gets them moving again.

Two labels carry the state between runs:

| Label | id | Meaning |
|---|---|---|
| `00_返信待ち` | `Label_16` | The other side owes a reply |
| `00_催促済み` | `Label_17` | A chase draft already exists for this thread |

**Never sends.** Drafts only, same as `mx-mail-draft`.

## Step 0 — fix the date before anything else

Get today's date from the session context, not from `date`. On 2026-09-03 the
container clock was two days behind, every elapsed-day figure in the report was
wrong, and four threads were reported as not yet due when they were.

Cross-check against the mailbox: the newest message in the inbox is never in
the future. If the shell clock and the newest message disagree by more than a
day, trust the mailbox and say so in the report.

All day counting is **JST**. The routine fires at 23:00 UTC, which is 08:00 the
*next* morning in Tokyo — counting in UTC is short by a day on every run.

## Step 1 — label what went out yesterday

```
mcp__Gmail__search_threads  query="in:sent newer_than:1d"
```

Search previews only carry the oldest messages of a thread, so call
`get_thread` with `messageFormat="PLAIN_TEXT"` on every candidate before
judging it.

A thread joins the waiting list when the owner asked for something and the
answer has not arrived. It does **not** join when:

- the mail only answers or reports, asking nothing;
- it is a thank-you, a greeting or an automated notice;
- it is one copy of a mail merge (see below);
- the newest message is inbound — then the ball is the owner's, and the thread
  belongs to `mx-mail-draft`, not here;
- `00_返信待ち` is already on it.

Run the shape test rather than guessing at the mail merge. Save the sent
messages and:

```bash
python3 -m mxmail.cli followup --sent /tmp/sent/*.json --format text
```

Anything reported as `state: bulk` is an announcement posted to a list, and it
stays out of the waiting list however direct its question looks. The IBC 2026
invitations asked fourteen people "ご参加のご予定はございますでしょうか"
outright; they are still announcements.

One judgement the tool will not make for you: **an acknowledgement is not an
answer.** "確認します" / "we will get back to you as soon as possible" leaves
the thread stalled on the other side. `ack_only_signal: true` marks the
candidates; you decide.

Then label:

```
mcp__Gmail__label_thread  threadId=<id>  labelIds=["Label_16"]
```

## Step 2 — release what has been answered

Walk `label:00_返信待ち`. Where a real reply has arrived, remove **both**
labels:

```
mcp__Gmail__unlabel_thread  threadId=<id>  labelIds=["Label_16", "Label_17"]
```

Dropping `00_催促済み` alongside matters: the thread may stall again next
week, and a stale chase marker would suppress the chase that stall deserves.

## Step 3 — chase what has gone quiet

`chase_plan()` decides. It applies three guards, and all three exist because
one morning produced eleven duplicate drafts across seven threads:

1. **`00_催促済み` on the thread** — survives between runs.
2. **An open draft on the same `threadId`** — catches what the label cannot: a
   second session running *right now*, which has drafted but not yet labelled.
   Call `mcp__Gmail__list_drafts` and check `threadId`; do not skip this
   because the label check passed.
3. **The cap** (`max_chases_per_run`, default 5) — a backlog would otherwise
   produce a burst on the first morning.

Then, for each chase, **in this order**:

```
mcp__Gmail__create_draft   replyToMessageId=<newest message in the thread>
mcp__Gmail__label_thread   threadId=<id>  labelIds=["Label_17"]
```

Label immediately after each draft, before moving to the next thread. A batch
of drafts followed by a batch of labels leaves a window in which a concurrent
run sees no marker and writes the same drafts again.

### Tone

Read `../mx-mail-draft/references/style-guide.md` — the voice is the same
mailbox, and a chase is not a special dialect. On top of it:

- Never imply the recipient is at fault. The mail has usually been sitting on
  both desks.
- Give them an exit: "現時点でご判断が難しいということでしたら、その旨お知ら
  せいただくだけでも結構です" turns silence into a cheap reply.
- Restate what was asked, in one line. Three weeks on, they have forgotten.
- Say why it matters now if there is a real date (a show, a delivery); leave it
  out if there is not, rather than inventing urgency.
- Japanese for Japanese counterparties, English for head office and English
  speakers — same rule as triage.

### The From address

`create_draft` has no `from` parameter, so drafts are created under the
account's default sending address. This mailbox wears several hats —
`taku_yamashita@mxvideo.jp` for Matrox and GlobalM,
`taku_yamashita@madokatech.co.jp` for MADOKA and Sansan — and a chase leaving
from the wrong one is worse than a late chase.

`owner_send_address()` reports the address the owner already used in that
thread. **List it per draft in your report** and tell the owner to check the
alias picker before sending.

## Step 4 — report

In Japanese:

- newly labelled (list every subject, so a wrong call is one click to undo);
- released because a reply arrived;
- the waiting list, longest first: 件名 / 相手 / 経過◯営業日 / 一行要約;
- chase drafts written, with the From address each one needs;
- skipped as already chased, and deferred by the cap;
- any disagreement between the shell clock and the mailbox.

Say "なし" for an empty section. If everything is empty: 相手待ちの案件はあり
ません.

## Boundaries

- Drafts only. Never send.
- Labels are the only mailbox change permitted — `00_返信待ち` and
  `00_催促済み`, and nothing else. Never archive, never trash, never touch
  another label.
- Never write a second chase draft onto a thread that already has one.
