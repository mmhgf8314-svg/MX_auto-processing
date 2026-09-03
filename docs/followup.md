# Reply-waiting notes

## What this pass is for

Triage asks "what do I draft for this message". Linkage asks "what fell
between the two conversations". Both start from a message. This pass starts
from the absence of one:

> The owner asked for something. Nothing came back. How long has that been
> true, and is it long enough to say something?

It is the cheapest of the three to get roughly right and the easiest to get
subtly wrong, because every mistake it makes is *written into the mailbox* —
as a label the owner has to remove, or a draft the owner has to delete.

## The state lives in labels, not in the run

```
00_返信待ち (Label_16)   the other side owes a reply
00_催促済み (Label_17)   a chase draft already exists
```

A morning routine has no memory. Everything it knows about yesterday it has to
read back out of the mailbox, so the mailbox has to carry the state. Holding it
anywhere else — a file in the repo, the previous session's transcript — breaks
the moment two runs overlap or a run dies halfway.

`00_催促済み` exists only because of that. Without it the routine cannot tell
"three business days, nobody replied" from "three business days, nobody
replied, and I already said so yesterday" — and it writes the chase again every
morning until someone answers.

## Three guards, because they fail differently

On 2026-09-03 this pass produced **eleven duplicate chase drafts across seven
threads** in a single morning. Three separate runs overlapped; each found the
same seven stalled threads; none could see the others' work.

The fix is three guards, and it is worth being clear why one is not enough:

1. **The `00_催促済み` label.** Durable, survives between runs, visible to the
   owner. Blind to anything happening *right now*, because a concurrent run has
   not labelled anything yet.
2. **An open draft on the same `threadId`.** Catches exactly that: the
   concurrent run has already written its draft. This is the guard that would
   have stopped all eleven.
3. **The per-run cap.** Neither of the above helps on day one, when a backlog
   of seven threads is over the threshold at once. A mailbox that fills with
   drafts gets its automation switched off by lunch, so the backlog is spread
   over mornings, oldest first.

There is a fourth, in sequencing rather than logic: **label immediately after
each draft, not in a batch at the end.** Draft-draft-draft-label-label-label
leaves a window in which a concurrent run sees no marker.

## Counting days

Two mistakes, both made on the first run:

**The clock.** The container reported 2026-08-31 when it was 2026-09-03. Every
elapsed figure in that morning's report was two days short, and four threads
were reported as "not yet due" when they were. Take `now` from the session
context, cross-check it against the newest message in the mailbox — which is
never in the future — and pass it in explicitly. `business_days_elapsed()` takes
`now` as an argument for this reason and never calls the clock itself.

**The zone.** The routine fires at 23:00 UTC. That is 08:00 the *next* morning
in Tokyo. Counting in UTC is a day short on every single run, so a chase due
Thursday goes out Friday. All counting is JST.

Business days, not calendar days, and Japanese public holidays come out of
`[followup] holidays`. Without them a chase due Tuesday lands on a day nobody
is at a desk and the count drifts for the rest of the week.

## Announcements are a shape, not a vocabulary

The first run put fourteen IBC 2026 invitations into the waiting list. They
were written once and posted to fourteen people, and each one asked, in as many
words:

> 三澤様は今年のIBCにご参加のご予定はございますでしょうか。

That is a direct question to a named person. No keyword test separates it from
a genuine request, and the original rule — "exclude 案内" — cannot be applied
by reading one mail, because the mail does not look like an announcement until
you have seen the other thirteen.

What separates them is shape. **A request is written to one person; an
announcement is written once and addressed to a list.** `find_bulk()` strips the
lines carrying an honorific — which is exactly the personalised part of a mail
merge, both the addressee line and the name spliced into the question — hashes
what is left, and groups. Fourteen mails collapse onto one fingerprint; two
threads that merely share boilerplate do not reach the threshold.

The owner still wants to know who replied about IBC. That is a different
question from "am I blocked", and it does not belong in a list whose purpose is
to produce chase mail.

## An acknowledgement is not an answer

The blunt rule for `waiting` is "the newest message is the owner's". It has one
systematic failure: head office replies *"we will get back to you as soon as
possible"*, the newest message is now inbound, the label comes off, and a case
that is still entirely stalled on Matrox disappears from the list. It surfaced
again three weeks later because the distributor chased.

`ack_only_signal` marks these — the same status keyword signals get in triage: a
hint that raises the question, never a verdict. The agent has the thread and
decides. Getting it wrong in the two directions costs differently: a label left
on produces one unnecessary chase; a label dropped produces silence for a
month.

## Which address a chase goes out from

This mailbox wears several hats — `taku_yamashita@mxvideo.jp` for Matrox and
GlobalM, `taku_yamashita@madokatech.co.jp` for MADOKA and Sansan,
`hello@madoka-surf.com` for the surf school. A chase leaving from the wrong one
is worse than a late chase.

`create_draft` has no `from` parameter, so the routine cannot set it. What it
can do is *say* which address is right, per draft, and it should read that off
the thread rather than a lookup table: the owner already chose an identity when
the thread started, and the correct answer is to keep using it.
`owner_send_address()` returns the sender of the newest message the owner
already sent there. `[followup.from_map]` is the fallback for a thread the
owner has not written in yet.

## Running it

```bash
python3 -m mxmail.cli followup --dir /tmp/threads \
    --sent /tmp/sent/*.json \
    --chased t-abc t-def \
    --drafted t-ghi \
    --now 2026-09-04T08:00:00+09:00
```

Pass full `get_thread` output. Search results preview only the *oldest*
messages of a thread, so a thread fetched by search alone looks stalled when
its newest message is an answer that arrived yesterday. This is the same trap
linkage documents, and it bites harder here: the consequence is a chase mail to
somebody who already replied.

`--now` is not optional in practice. Pass it.

## Extending it

- **Threshold or cap** → `[followup]` in `config/routing.toml`. Not the prompt,
  and not the Python.
- **A new public holiday** → `[followup] holidays`. Top up once a year.
- **A new sending identity** → `[followup.from_map]`, and add the alias to
  `[owner] aliases` so `is_owner()` recognises it. Miss the second half and
  every thread on that identity reads as "inbound", which inverts the whole
  assessment.
- **Chase wording** → `.claude/skills/mx-followup/SKILL.md`, and the shared
  voice in `mx-mail-draft/references/style-guide.md`. The Python has no opinion
  about wording, by design.
