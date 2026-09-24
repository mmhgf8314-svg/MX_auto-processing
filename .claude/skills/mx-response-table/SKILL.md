---
name: mx-response-table
description: Build the owner's response tables for the taku_yamashita@mxvideo.jp mailbox, published as Artifacts —「MX 朝の対応表」(morning, 08:00 JST) covering every case that needs the owner's attention, and「MX 夕方の対応表」(evening, 17:30 JST) listing what must be handed to Matrox head office tonight, what head office owes, and what head office answered today. Summary and background only; no draft text, no sends. Use for the daily mailbox review, when asked to check the mailbox, or when asked what needs a reply or what to send to head office.
---

# mxvideo.jp mailbox response tables（MX 朝の対応表／MX 夕方の対応表）

This replaces the old two-skill split (auto-draft on new mail, separate
follow-up chases). Both produced text the owner still had to read against the
thread before trusting it, which made the draft itself the bottleneck. This
skill produces one artifact per run instead: a table of every case that needs
a decision, each row carrying a summary, the background, and a proposed
direction — never finished draft text. The actual mail gets written later,
in conversation, once the owner has looked at the case.

The downstream flow, every time:

1. This skill builds/updates the table.
2. The owner reviews it and picks cases to talk through.
3. Only for those, draft the mail together — that's where
   `references/style-guide.md` and `references/parties.md` come in.
4. The owner sends. This skill, and this conversation, never do.

## Editions — the same skill runs twice a day

Japan and Montreal are 13 hours apart (14 in winter). Head office's working
day starts around 22:00 JST and ends around 06:00 JST. Whatever the owner
hands to head office in the Japanese evening gets worked while Japan sleeps,
and the answer is in the mailbox by the morning run. A morning-only table
misses that hand-off, so there are two editions:

| Edition | Routine | Fires (JST) | Page name | State keys in `config/response_table_state.json` |
|---|---|---|---|---|
| Morning | ⚡ MX 朝の対応表 | 08:00 Mon–Fri | 「MX 朝の対応表」 | `artifactUrl`, `lastBuiltJst` |
| Evening | ⚡ MX 夕方の対応表 | 17:30 Mon–Fri | 「MX 夕方の対応表」 | `evening.artifactUrl`, `evening.lastBuiltJst` |

The routine prompt says which edition to build. Steps 0–2 below are shared.
Step 3 (rows) and Step 4 (page name, which artifact URL) differ, and the
evening differences are collected in **"Evening edition"** further down.
Each edition has its own artifact URL: an evening run never republishes the
morning page, and a morning run never republishes the evening page.

## Step 0 — fix the date before anything else

Get today's date from the session context, not from `date` — the container
clock can run behind. Cross-check against the mailbox: the newest message in
the inbox is never in the future. If the shell clock and the newest message
disagree by more than a day, trust the mailbox and say so in the report.

All day counting is **JST**. A run that fires late at night UTC is already the
next morning in Tokyo — counting in UTC undercounts by a day.

## Step 0.5 — unattended runs must never stop on a permission prompt

The routines「⚡ MX 朝の対応表」and「⚡ MX 夕方の対応表」run this skill with
nobody watching. A Bash command that needs approval blocks the whole run: the
routine reports "succeeded" (the wake was delivered) while the session sits
on a permission dialog and the table is never republished. That is exactly
what happened on every run from 2026-09-12 to 2026-09-17 — the pending
command was a `cp` of files from `/root/.claude/projects/.../tool-results/`
plus a heredoc.

Rules for every run, attended or not:

- **Never read, copy or reference anything under `/root/.claude/`.** When a
  Gmail tool result is too large and gets saved there, use the `Read` tool on
  it (or call `get_thread` again with `messageFormat="MINIMAL"` or
  `"METADATA_ONLY"`); do not `cat`, `cp` or `python3` it from Bash.
- **Do not write files with Bash heredocs** (`cat > file << EOF`). Use the
  `Write` tool.
- The only Bash commands this skill may run are: `python3 -m mxmail.cli ...`
  on files that were written with the `Write` tool, and the `git add / commit
  / push` in Step 4. Nothing else.
- **The engine in Step 2 is optional.** If staging the thread JSON with the
  `Write` tool would be impractical (many threads, very long bodies), skip
  the engine entirely: classify the thread by reading it, count business days
  yourself (JST, Monday–Friday, Japanese public holidays excluded, counted
  from the owner's last outbound message), and say in the report that the
  engine was skipped. A table built without the engine is far better than no
  table.
- If any tool call is refused or would need approval, do not wait and do not
  retry the same call. Note it in the report and continue with the steps
  that still work. Publishing the artifact (Step 4) is the one step that
  must not be dropped.

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

Label what went out since the last run. The morning routine runs
Monday–Friday mornings, so on Monday use `newer_than:3d`; otherwise:

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
python3 -m mxmail.cli followup --sent /tmp/sent/*.json --format text   # optional — only on files written with the Write tool
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
proposal even though this skill no longer uses it as a guard).

**Search by the label's display name, never by its id.** The Gmail tool
description says `label:` takes ids, but in this mailbox
`query="label:Label_16"` returns nothing while `query="label:00_返信待ち"`
returns every labelled thread (verified 2026-09-25, when a run searched by
id, got zero results and skipped the whole label inventory). Ids are only
for `label_thread` / `unlabel_thread`. If the name search also returns
nothing, say so in the report; do not conclude the label is empty.

```
mcp__Gmail__unlabel_thread  threadId=<id>  labelIds=["Label_16", "Label_17"]
```

A closing message from the owner that asks nothing (a thank-you, "無事完了で
した", nothing left open) also gets released even though the owner sent it
last — `assess()` only knows who sent the newest message, not whether it
actually asked anything. That reading is this skill's job, not the tool's.

### 1c. Notion meeting notes (議事録)

The owner's calls with head office (the Monday 22:00 JST call with Mingkai,
customer meetings, JM meetings) are recorded by Notion AI as meeting notes.
Decisions made on those calls change rows in this table before any mail
does — "stop the new NDA", "ask Sony three questions", "contact Sakaguchi" —
and a table built from the mailbox alone will keep proposing the opposite of
what was agreed on the call. So every run reads the meeting notes too.

**Which notes.** Morning: notes created since the previous run (Monday:
since Friday morning). Evening: notes created since the morning run.

```
mcp__Notion__notion-query-meeting-notes
  filter = {"operator":"and","filters":[{"property":"created_time",
            "filter":{"operator":"date_is_within",
                      "value":{"type":"relative","value":"custom",
                               "direction":"past","unit":"day","count":<N>}}}]}
```

Then `mcp__Notion__notion-fetch` on each result **without** the transcript
(`include_transcript` omitted or false) — the `<summary>` block with its
Action Items is enough. Skip notes whose summary is plainly not business
(language practice recordings, personal calls, other companies' meetings);
the owner records many things.

**How a note changes the table.** Read the Action Items and each section
against the rows you already have:

- An action item owned by the owner ("Taku to …") that no mail thread yet
  reflects becomes a **新着** row (morning) or a **今夜投げる** row (evening,
  when the counterparty is head office). Cite the note: 「9/21 Mingkai
  定例の議事録より」. 経過 is blank — there is no thread to count from.
- An action item that reverses an existing row (the note says stop, the
  thread still says go) rewrites that row's 提案. Say explicitly that the
  call overrides the thread, and name what the owner has to tell the
  counterparty. Never leave the mailbox reading standing next to a call
  decision that contradicts it.
- A fact from the call that answers an open question in a 返信待ち row
  ("ConvertIP DSH is one stream in, one stream out — Dan confirmed on the
  call") goes into that row's 背景, with the source. The row stays 返信待ち
  if a written answer is still owed; the proposal can say the owner already
  has the answer and may not need to wait.
- Action items owned by head office ("Dan to send …", "Frank to discuss …")
  join the 本社回答待ち picture — as background on an existing row or, if
  nothing in the mailbox carries them yet, as one line in the report so the
  owner knows head office committed to something.

**Rows carried over from an earlier run are re-verified, not copied.** A
minutes-derived row (「議事録から」) stays on the page until the owner has
acted on it, so on every later run check each one against `in:sent` since
the previous run: if the owner's mail covers the action (the three questions
were sent to the customer, the legal team was told to hold the NDA), mark
the row 対応済み with the date and drop its proposal, or remove it. The same
applies to any 返信待ち row whose background says "つなぎ返信済み": if a
substantive reply has since gone out, the background and proposal must say
so. "No new minutes since last run" means the minutes did not change; it
never means the rows are still current.

**Boundaries for this step.** Read only. Never write to Notion from this
skill — no page edits, no comments, no database rows. Never copy the
transcript into the table; summarise. Numbers that head office would not
want a customer to see (Matrox's selling price to JM, margins) stay out of
the table even though they appear in the notes — write 「価格は議事録参照」.

**When Notion is not connected.** The routine may run without the Notion
connector (the tools will simply be absent). Then build the table from the
mailbox as before and put one line in the meta note and in the report:
「Notion 未接続のため議事録は未反映」. Do not silently skip; the owner needs
to know the table is missing that source.

## Step 2 — run the engine (when it can be done without Bash file staging)

Prefer running every message and every stalled thread through the same
deterministic rules, from the repository root. Stage the thread JSON with
the `Write` tool only (see Step 0.5); if that is impractical, skip this step
and classify by hand as described there:

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

## Step 3 — build the rows (morning edition)

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

The page is named **「MX 朝の対応表」** for the morning edition and
**「MX 夕方の対応表」** for the evening edition — use exactly that as the
`<title>` and the `<h1>`, every run. These are the owner's chosen names; do
not rename them to「返信待ち案件表」or anything else, and do not append a
date or a subtitle to the title (the 基準日 belongs in the meta line under
the heading).

Read `config/response_table_state.json` first. The morning edition uses the
top-level `artifactUrl`; the evening edition uses `evening.artifactUrl`.

- **The edition's URL is set**: read that artifact (`action: "read"`), then
  republish the updated table to the same `url` so the link stays stable
  across runs. If the read fails (deleted, moved), fall back to a fresh
  publish and update the state file with the new URL.
- **The edition's URL is null** (first run): publish fresh.

Follow the `artifact-design` skill's process — this is a scanned/operated
dashboard, not a document, so lead with a summary strip (counts by 種別)
above the case list, encode 種別 as a chip/color, and give elapsed business
days a `tabular-nums` numeric treatment. A working sample of this exact table
shape was already designed and approved by the owner — reuse its token
system and layout rather than redesigning from scratch each run. The evening
page uses the same tokens; only the chip labels and section order change.

After publishing, write the returned URL and file path back into the
edition's keys in `config/response_table_state.json`, then commit and push
that one file:

```bash
git add config/response_table_state.json
git commit -m "Update response table state"
git push -u origin <current-branch>
```

This is what lets a fresh container next run find the same link — the
state has to survive on disk *and* in the remote, not just in this session.
If the push is refused or would need approval, skip it and say so in the
report; the artifact URLs are already recorded on the default branch, so a
missed state push is harmless.

## Step 5 — report back in chat

Short. The table is the detail view; the chat message is not a second copy of
it. Give: the artifact link, the counts by 種別, and one line on anything
that changed since the last run worth flagging on its own (a new 催促検討
case, a long-silent thread that finally answered). If the shell clock and the
mailbox disagreed in Step 0, say so here too. If Notion was not connected
(Step 1c), say「Notion 未接続のため議事録は未反映」.

## Evening edition — MX 夕方の対応表

The evening page is a **hand-off list**, not a second copy of the morning
page. Before Montreal's day starts it shows the owner:

1. what must be thrown to head office tonight,
2. what head office already owes and how long it has been waiting,
3. what head office sent today that still has to reach a Japanese
   customer or Japan Material, and
4. what moved on the Japanese side today.

**Window.** Everything since the morning run: `in:inbox newer_than:1d` and
`in:sent newer_than:1d`, read against the morning page (read the morning
`artifactUrl` first so the evening page does not restate rows that have not
moved). A row that is unchanged since the morning does not get a full card;
it appears at most as one line in the 本社回答待ち list. Meeting notes
created since the morning run (Step 1c) are part of the window: a decision
taken on a daytime call with JM or a customer is exactly what head office
needs to hear tonight.

**Who counts as head office.** Matrox sales (Mingkai, Franc, Pardo, Donald,
Kyle, Dan), support (`convertipsupport@`, Kevin, Sandy, Anosh, Marwan, Qing),
legal (`legal@`, Chantal, Jason), logistics (Katia, `slgmgi@`, Lan). Japan
Material, Golter and customers are the Japanese side.

**Row types (種別)** — use these chips instead of the morning ones:

| 種別 | Meaning | Sort |
|---|---|---|
| `今夜投げる` | The owner's ball and the counterparty is head office: something a Japanese party sent today that head office needs (logs, captures, answers to head office's questions), or a decision head office is waiting on the owner for (a go-ahead, a written instruction). These are the rows the owner must act on before bed. | First, most urgent at top |
| `本社回答あり・展開待ち` | Head office answered today and the answer still has to be relayed to the customer or Japan Material. Usually the owner's ball for the next morning; tonight if the customer is waiting on it. | Second |
| `本社回答待ち` | Head office's ball. Show who, sent when, business days elapsed; mark rows at or past the chase threshold. A compact list, not full cards. | Third, longest-waiting first |
| `顧客側の動き` | Inbound from customers or Japan Material today that changes a row: a `00_返信待ち` thread answered (release the labels per Step 1b), or a new ask that will need head office (then it is also a `今夜投げる` row). | Last |

Summary tiles: **今夜投げる / 展開待ち / 本社回答待ち**.

**Meta line.** Give the JST date and the run time, and Montreal's date and
time at that moment (JST − 13 h in summer, − 14 h in winter), plus a link to
the morning page. If the next Japanese business day is not the next calendar
day (weekend, public holiday), say so in a note: head office keeps working,
so the next morning page will carry several days of answers at once, and
anything not thrown tonight waits until the next Japanese working day.

**Labels.** Same rules as Step 1b, applied to today's sent mail; release
threads that were answered during the day. Never set `00_催促済み`.

**Report.** The evening artifact link, the three counts, and the
`今夜投げる` rows as one line each — that list is the owner's checklist for
tonight. Plus the one-line Notion notice from Step 1c if the connector was
missing. Nothing else.

## Boundaries

- No draft is written and nothing is sent by this skill, ever. That happens
  afterward, in conversation, case by case.
- The only mailbox changes this skill makes are `00_返信待ち` labelling and
  release, exactly as described in Step 1b. It never sets `00_催促済み`,
  never archives, never trashes, never touches any other label.
- Notion is read-only for this skill (Step 1c). No page, comment or
  database write, ever.
- Don't invent urgency or a business-day count that is not in the engine
  output.
- Never copy credentials (registry passwords, API keys, download links with
  embedded tokens) from a mail into the table. Write "認証情報はメール参照".

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
- `../../../config/response_table_state.json` — the published artifacts'
  URLs (morning at top level, evening under `evening`), read and updated in
  Step 4.
