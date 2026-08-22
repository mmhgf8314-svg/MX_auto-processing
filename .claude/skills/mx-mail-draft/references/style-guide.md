# Style guide

Both languages below are modelled on mail the owner has actually sent. Match
that register; do not import a generic template voice.

---

## Japanese — to customers, the distributor and partners

Plain, warm keigo. No over-decoration, no long self-introduction on a running
thread.

**Skeleton**

```
<相手の姓>様            ← 複数名なら「○○様 △△様」と並べる

お世話になっております。
Matroxの山下です。

<本題：結論を先に、そのあと理由・条件>

<次のアクション、または確認事項>

よろしくお願い申し上げます。

Matrox・山下
```

**Openings**

- Ongoing thread: `お世話になっております。` / `いつもお世話になっております。`
- After a gap: `ご無沙汰しております。`
- Answering a question: `ご連絡ありがとうございました。` then the answer.
- Apologising for a delay: `ご返信が遅くなり申し訳ございません。`

**Closings**

- Standard: `よろしくお願い申し上げます。`
- Asking for something: `ご多忙中恐れ入りますが、ご検討のほどよろしくお願い申し上げます。`
- Waiting on them: `お忙しいところ恐縮ですが、ご確認のほどよろしくお願い申し上げます。`

**Signature** — `Matrox・山下`, or `山下` on a fast-moving internal thread.

**Habits to keep**

- Structured facts go in a `【 】` block with `〇` sub-headings and `・` bullets.
- Product names stay in Latin script: `X.mio5`, `ConvertIP`, `Monarch EDGE`,
  `Matrox ORIGIN`, `Avio 2`, `Vion`, `Maevex MGX`.
- Say `弊社` for Matrox, `御社`/`貴社` for the customer.
- Never machine-translate an English mail into Japanese wholesale. Restate it:
  head office phrasing and Japanese customer phrasing are not the same shape.

---

## English — to Matrox head office

Direct, short, first-name. Head office reads dozens of these a day.

**Skeleton**

```
Hi <First name>,          ← several: "Hi Lan, Marwan, and Mingkai,"

<the ask or the update, in the first sentence>

<supporting detail as short bullets>

<what you need back, and by when>

Best regards,

Taku
```

**Habits to keep**

- Lead with the ask. Context second.
- Bullets for anything with more than two facts (part numbers, quantities,
  dates, configurations).
- Name the customer and the case: `Nikko Telecom`, `PO JMGS…`, `Case 001…`.
- Give head office what they need to act: quantity, part number, requested
  date, ship-from preference, firmware/driver version, OS build.
- `Thanks` / `Best regards` then `Taku`. No formal sign-off block.

---

## Worked example — Matrox writes in

Incoming (from head office): stock is available in Canada, or Hong Kong in
10–12 business days; which shipping point does the customer want?

**Reply to Matrox (EN)**

```
Hi Lan,

Thanks for checking. I am confirming the preferred shipping point with the
customer now and will come back to you within a day.

One thing to confirm in the meantime: if they choose Hong Kong, does the
10-12 business day window start from the PO date or from payment received?

Best regards,

Taku
```

**Companion draft to the customer (JA)**

```
田中様

お世話になっております。
Matroxの山下です。

X.mio5 2枚の納期についてご確認いただいた件、本社より回答がございました。

〇出荷元の選択肢
・カナダ本社より出荷：在庫あり
・香港倉庫より出荷：10〜12営業日

いずれの出荷元をご希望か、ご教示いただけますでしょうか。
ご希望をお知らせいただき次第、正式な出荷予定日をご案内いたします。

お忙しいところ恐縮ですが、ご確認のほどよろしくお願い申し上げます。

Matrox・山下
```

Note what the Japanese draft does *not* carry over: the internal question
about when the window starts. That is still open on the Matrox side, so it
does not go to the customer as if it were settled.

---

## Worked example — a customer writes in

Incoming (JA, from a customer): a delivered board shows picture corruption on
one output.

**Reply to the customer (JA)**

```
岡部様

お世話になっております。
Matroxの山下です。

ご連絡ありがとうございました。
映像に乱れが発生している件、本社の技術部門へ確認を依頼いたします。

切り分けのため、以下をご教示いただけますでしょうか。

〇ご確認事項
・ドライバー／ファームウェアのバージョン
・OSのビルド番号
・症状が出る入出力の構成（例：2in10out）
・再現性（常時／間欠）

回答が得られ次第、改めてご連絡申し上げます。

よろしくお願い申し上げます。

Matrox・山下
```

**Companion report to Matrox (EN)**

```
Hi Qing,

Nikko Telecom is reporting picture corruption on one output of an X.mio5.

  - Board: X.mio5, configured 2in10out
  - Symptom: OUT C is black or shows corruption
  - Driver: 10.5.100.1781
  - Host: HP Z4G6i, Windows 11 25H2

I have asked the customer to confirm the firmware version and whether the
fault is constant or intermittent, and will forward that as soon as I have it.

Is this the same issue as the one fixed in 10.5.103? If so I will ask them to
try the hotfix first.

Thanks,

Taku
```

---

## Placeholders

When a fact is missing, never guess. Leave it visible so it cannot be sent by
accident:

- Japanese: `【要確認：出荷予定日】`
- English: `[TBC: ship date]`

Then list every placeholder in your summary to the owner.
