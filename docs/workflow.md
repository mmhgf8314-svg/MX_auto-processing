# Workflow notes

## The decision, in full

```
incoming mail to taku_yamashita@mxvideo.jp
        │
        ├─ bulk / no-reply / calendar notice / private domain / own sent mail
        │       └─▶ skip
        │
        ├─ sender domain in [sides] matrox
        │       ├─ reply draft ......... language of the incoming mail (EN)
        │       └─ companion draft ..... to the CUSTOMER
        │               ├─ customer side of the thread writes JA ─▶ JA
        │               └─ customer side of the thread writes EN ─▶ EN
        │
        └─ everyone else (customer / distributor / partner)
                ├─ reply draft ......... language of the incoming mail (JA, or EN)
                └─ companion draft ..... to MATROX, always EN
```

Two things fall out of writing the rule this way rather than as four branches:

- The reply language is never a special case. "Answer in the language you were
  written in" already produces English for head office, Japanese for a
  Japanese customer, and English for the customer who writes in English.
- The exception only has to be handled in one place: the *customer-facing*
  companion draft, which follows the customer's own language rather than
  defaulting to Japanese. `counterparty_language()` reads that off the newest
  non-Matrox message in the thread.

## Why the companion draft is a judgement call

`必要に応じて` is doing real work in the specification. A thank-you from head
office needs no Japanese mail; a lead-time answer does. Keyword signals in
`[companion_signals]` are good enough to raise the question and nowhere near
good enough to answer it, so `mxmail` reports `confidence: suggested` or
`unlikely` and the agent decides after reading the thread.

Getting this wrong in the two directions costs different amounts. A missing
companion draft costs a day of latency. A spurious one costs the owner the
time to notice and delete it. Neither is expensive, which is exactly why this
should not be over-engineered into a classifier.

## Language detection

Quoted history is stripped before detection. This matters more than it
sounds: a Japanese customer writing four English sentences will quote fifty
lines of Japanese below their signature, and counting those flips the verdict.
`strip_quoted()` cuts at the first quote marker — `>`, `From:`,
`--- Original Message ---`, `On … wrote:`, and the Japanese `2026年8月21日(金) …:`
form Gmail generates.

Kana is treated as decisive because kana only appears when someone is actually
writing Japanese. Kanji alone is not: English mail from head office routinely
carries Japanese names and part numbers in quoted signatures.

## Running it on a schedule

The workflow is interactive by design — it produces drafts a human then reads.
If you want it to run unattended, schedule a session that invokes the skill:

- **Claude Code Routine** — a scheduled trigger firing a fresh session with the
  prompt `新着メールの下書きを作成して`. Weekday mornings is the natural cadence.
- **`/loop`** — for a single working day of repeated passes.

Either way the output is still drafts, and the owner still sends them. Do not
wire this to anything that sends.

## Extending it

- **New counterparty** → add a `[[parties]]` entry. `kind` and
  `default_language` are what the triage reads; `notes` is for the agent.
- **New bulk sender** → add to `[ignore] addresses`, or to `localpart_patterns`
  if it is a family of senders.
- **Missed handoffs** → add the vocabulary to `[companion_signals] handoff`.
  Short ASCII acronyms are matched as whole words, longer ASCII terms match at
  a word start (`ship` catches `shipment`), Japanese terms are plain
  substrings.
- **Changed voice** → `references/style-guide.md`. That file is the only place
  tone is defined; the Python has no opinion about wording.
