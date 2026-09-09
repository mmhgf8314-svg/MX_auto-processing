---
name: mx-response-table
description: Build a single response table (published as an Artifact) covering every case in the taku_yamashita@mxvideo.jp mailbox that needs the owner's attention — new inbound mail, threads waiting on a reply, and threads overdue for a chase. Summary and background only; no draft text, no sends. Use for the daily mailbox review, when asked to check the mailbox, or when asked what needs a reply.
---

# mxvideo.jp mailbox response table

This replaces the old two-skill split (auto-draft on new mail, separate
follow-up chases). Both produced text the owner still had to read against the
thread before trusting it, which made the draft itself the bottleneck. This
skill produces one artifact instead: a table of every case that needs a
decision, each row carrying a summary, the background, and a proposed
direction — never finished draft text. The actual mail gets written later,
in conversation, once the owner has looked at the case.

The downstream flow, every time:

1. This skill builds/updates the table.
2. The owner reviews it and picks cases to talk through.
3. Only for those, draft the mail together — that's where
   `references/style-guide.md` and `references/parties.md` come in.
4. The owner sends. This skill, and this conversation, never do.

## Step 0 — fix the date before anything else

Get today's date from the session context, not from `date` — the container
clock can run behind. Cross-check against the mailbox: the newest message in
the inbox is never in the future. If the shell clock and the newest message
disagree by more than a day, trust the mailbox and say so in the report.

All day counting is **JST**. A run that fires late at night UTC is already the
next morning in Tokyo — counting in UTC undercounts by a day.

## Step 1 — collect candidates

### 1a. New inbound mail

```
mcp__Gmail__search_threads  query="to:taku_yamashita@mxvideo.jp is:unread in:inbox"
```

Widen as asked (`newer_than:3d`, a specific sender, `is:starred`). Search
results only preview the *oldest* messages of a thread — call `get_thread`
with `messageFormat="PLAIN_TEXT"` on every candidate before judging it. The
newest message is the one to summarise; the rest is the background.

### 1b. Threads stalled on the other side

Two labels carry this state between runs:

| Label | id | Meaning |
|---|---|---|
| `00_返信待ち` | `Label_16` | The other side owes a reply |
| `00_催促済み` | `Label_17` | A chase has actually been **sent** on this thread |

`00_催促済み` no longer means "a chase draft exists" — this skill never
writes one. It is set by hand, later, at the point a chase mail actually goes
out. Do not set it here; only read it, as context for the row's proposal.

Label what went out yesterday:

```
mcp__Gmail__search_threads  query="in:sent newer_than:1d"
```

Call `get_thread` on every candidate — a search preview only shows a thread's
oldest messages, so a thread that looks stalled in the preview may already
have a same-day reply. A thread joins the list when the owner asked for
something and the answer has not arrived. It does not join when the mail only
answers or reports asking nothing, is a thank-you/greeting/automated notice,
is one copy of a mail merge, or the newest message is inbound (then it belongs
in Step 1a, not here). Confirm the shape rather than guessing:

```bash
python3 -m mxmail.cli followup --sent /tmp/sent/*.json --format text
```

`state: bulk` in the output means an announcement, however direct the
question inside it reads — keep it off the list. `ack_only_signal: true`
means the newest inbound message looks like "確認します" and nothing more —
that thread is still stalled; do not release it on an acknowledgement alone.

Label the ones that qualify:

```
mcp__Gmail__label_thread  threadId=<id>  labelIds=["Label_16"]
```

Then walk `label:00_返信待ち` and release what has actually been answered
(remove **both** labels — a stale `00_催促済み` would misinform next run's
proposal even though this skill no longer uses it as a guard):

```
mcp__Gmail__unlabel_thread  threadId=<id>  labelIds=["Label_16", "Label_17"]
```

A closing message from the owner that asks nothing (a thank-you, "無事完了で
した", nothing left open) also gets released even though the owner sent it
last — `assess()` only knows who sent the newest message, not whether it
actually asked anything. That reading is this skill's job, not the tool's.

## Step 2 — run the engine

Do not eyeball the routing — run every message and every stalled thread
through the same deterministic rules, from the repository root:

```bash
python3 -m mxmail.cli --thread /path/to/thread.json --format text          # new inbound: action/side/language/companion
python3 -m mxmail.cli followup --dir /tmp/threads --now <ISO8601> --format text   # stalled threads: business days, counterparty, from-address
python3 -m mxmail.cli linkage /tmp/threads/*.json --format text            # dropped handoffs between the Matrox and Japan sides of one case
```

`--thread` returns `action: skip` for newsletters, calendar notices,
no-reply senders and the owner's own mail — drop those silently, they never
reach the table. It also flags whether a companion mail to the other side is
likely needed (`companion.confidence`); fold that into the row's proposal
rather than opening a second row.

`followup`'s `business_days_elapsed` is what separates 返信待ち from
催促検討 — the config default is 3 business days
(`config/routing.toml` → `[followup] chase_after_business_days`).

`linkage` catches what per-message triage cannot: a customer answers the
Japanese thread, head office keeps asking on the English case thread, and
neither side has heard from the other. When it reports a gap, that becomes
its own row (種別: 新着) even though nothing new technically arrived — a
handoff the owner is sitting on is exactly the kind of thing this table
exists to surface.

## Step 3 — build the rows

One row per case. Never invent a business-day count, a subject, or a
counterparty — pull every field from the engine output or the thread itself.

| Field | Content |
|---|---|
| 種別 | `新着` (needs a first answer) / `返信待ち` (< 3 business days) / `催促検討` (≥ 3 business days) |
| 件名・相手 | Subject, and who it's with |
| 要約 | One line: what they said, or what's being waited on |
| 背景 | A few lines of thread history — enough that the owner does not have to reopen Gmail to remember what this is |
| 経過 | Business days waiting — 返信待ち／催促検討 only, blank for 新着 |
| 提案 | A direction, never finished mail text. Say if a companion draft to the other side looks warranted, and say if `00_催促済み` shows a chase already went out once before (so the owner knows this would be a second one) |

Sort 催促検討 and 返信待ち together by 経過 descending (longest-waiting
first); 新着 cases sort by how recent they are.

## Step 4 — publish the table as an Artifact

Read `config/response_table_state.json` first.

- **`artifactUrl` is set**: read that artifact (`action: "read"`), then
  republish the updated table to the same `url` so the link stays stable
  across runs. If the read fails (deleted, moved), fall back to a fresh
  publish and update the state file with the new URL.
- **`artifactUrl` is null** (first run): publish fresh.

Follow the `artifact-design` skill's process — this is a scanned/operated
dashboard, not a document, so lead with a summary strip (counts by 種別)
above the case list, encode 種別 as a chip/color, and give elapsed business
days a `tabular-nums` numeric treatment. A working sample of this exact table
shape was already designed and approved by the owner — reuse its token
system and layout rather than redesigning from scratch each run.

After publishing, write the returned URL and file path back into
`config/response_table_state.json`, then commit and push that one file:

```bash
git add config/response_table_state.json
git commit -m "Update response table state"
git push -u origin <current-branch>
```

This is what lets a fresh container next morning find the same link — the
state has to survive on disk *and* in the remote, not just in this session.

## Step 5 — report back in chat

Short. The table is the detail view; the chat message is not a second copy of
it. Give: the artifact link, the counts by 種別, and one line on anything
that changed since the last run worth flagging on its own (a new 催促検討
case, a long-silent thread that finally answered). If the shell clock and the
mailbox disagreed in Step 0, say so here too.

## Boundaries

- No draft is written and nothing is sent by this skill, ever. That happens
  afterward, in conversation, case by case.
- The only mailbox changes this skill makes are `00_返信待ち` labelling and
  release, exactly as described in Step 1b. It never sets `00_催促済み`,
  never archives, never trashes, never touches any other label.
- Don't invent urgency or a business-day count that is not in the engine
  output.

## Drafting a case, once the owner picks one

Not part of the automated run — this is what the follow-up conversation
looks like once a row from the table gets discussed and agreed:

1. Re-read the full thread (`get_thread`, `PLAIN_TEXT`) — the table's 背景 is
   a summary, not the source.
2. Follow `references/style-guide.md` for tone, and `references/parties.md`
   for who needs what from the reply.
3. `mcp__Gmail__create_draft`, threaded with `replyToMessageId`. `create_draft`
   has no `from` parameter — say which alias the draft needs in the sender
   picker (`taku_yamashita@mxvideo.jp` for Matrox/GlobalM,
   `taku_yamashita@madokatech.co.jp` for MADOKA/Sansan).
4. If this was a 催促検討 row and the owner agrees to send the chase, label
   the thread `Label_17` (`00_催促済み`) once the mail actually goes out —
   not before.

## Reference

- `references/style-guide.md` — tone, openings, closings, worked examples.
- `references/parties.md` — who is who on each side.
- `../../../config/routing.toml` — domains, ignore list, companion signals,
  case register, `[followup]` thresholds.
- `../../../config/response_table_state.json` — the published artifact's URL,
  read and updated in Step 4.
