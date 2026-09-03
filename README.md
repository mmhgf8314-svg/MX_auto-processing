# MX_auto-processing

`taku_yamashita@mxvideo.jp` に届いたメールを仕分けし、**返信の下書き**と、
必要に応じて**もう一方の相手への下書き**を Gmail の下書きとして作成する
ワークフローです。**送信は行いません。**

## 仕様

受信したメールについて、まず内容とスレッド全体を参照したうえで:

1. **Matrox 本社からのメール（英語）**
   → これまでのやりとりを踏まえた**英語の返信下書き**を作成。
   あわせて、必要に応じてそのメールに関連した**お客様向けの日本語下書き**も作成。

2. **Matrox 本社以外からのメール（日本語）**
   → これまでのやりとりを踏まえた**日本語の返信下書き**を作成。
   あわせて、必要に応じて **Matrox への報告用の英語下書き**も作成。

**例外**: お客様から英語でメールが届いた場合は、そのスレッドは英語で統一する。
返信も、Matrox への報告も英語。

判定を表にすると:

| 差出人 | 返信の言語 | もう一方への下書き |
|---|---|---|
| Matrox 本社（英語） | 英語 | 日本語 → お客様（必要に応じて） |
| お客様・パートナー（日本語） | 日本語 | 英語 → Matrox（必要に応じて） |
| お客様・パートナー（英語） | 英語 | 英語 → Matrox（スレッド全体を英語で統一） |

ニュースレター、no-reply、カレンダー通知、業務外の私信は下書きを作成しません。

## スレッド間の突き合わせ

このメールボックスでは、同じ案件について**日本語スレッド（お客様・代理店）**と
**英語スレッド（Matrox のサポートケース）**が並行して動きます。両者をつないで
いるのは山下さんの手作業だけで、実際にここで情報が落ちます。

> お客様が日本語スレッドで「ベータ版で再現しました、ログは取得済みです」と回答
> → 誰も英語側へ渡さない → Matrox は英語スレッドで催促を続ける → ケースが止まる

1通ずつ見る仕分けでは、これは検出できません。どのスレッドも単体では「返信済み」
に見えるためです。そこで、案件ごとにスレッドを束ねて**未転送**を検出します。

```bash
python3 -m mxmail.cli linkage /tmp/threads/*.json --format text
```

出力例:

```
[case:00092203]  JP  ->  MATROX   17 days old
  news    : 2026-08-07T12:25:03Z  engineer@example-enduser.co.jp
  subject : Re: 【TBS統合FB】ConvertIP DSSのST2022-7の動作に関する問合せ
  waiting : 2 message(s), latest 2026-08-08T07:42:37Z
  relayed : 2026-08-06T13:07:00Z
```

方向ごとに、**相手側が言ったことのうち、まだ渡していない最も古いもの**を起点に
日数を数えます。新しい催促が来ても、古い未転送が「新しく」見えることはありません。

〇スレッドの束ね方
PO番号やケース番号が両側に出ていれば自動で束ねます。ただし日本語側の件名は
【TBS統合FB】、英語側は Case 00092203 のように**共通の識別子がない**ことが多く、
その場合は `config/routing.toml` の `[[cases]]` に別名を1度だけ登録します。

```toml
[[cases]]
id      = "00092203"
name    = "NEC/TBS CIP-DSS SDI-OUT interruption after switch power-on"
aliases = ["00092203", "BHov16dNMeW43s5KmUyu2js", "TBS統合FB"]
```

## 返信待ちの巡回

朝の巡回で、**こちらが送って返事が来ていないスレッド**を見つけ、
`00_返信待ち` ラベルを最新の状態に保ち、3営業日を超えたものには催促の下書きを作ります。
手順は `.claude/skills/mx-followup/SKILL.md`、設計の意図は `docs/followup.md` にあります。

```bash
python3 -m mxmail.cli followup --dir /tmp/threads \
    --sent /tmp/sent/*.json \
    --chased <催促済みの threadId ...> \
    --drafted <下書きが既にある threadId ...> \
    --now 2026-09-04T08:00:00+09:00
```

出力例:

```
3 threads checked. 1 waiting on the other side, 4 announcement copies excluded.

[  6 business days]  Re: InterBEE 2026 での展示のご相談
  thread  : t-mitomo
  waiting : m_kawagishi@mitomo.co.jp
  sent    : 2026-08-27T07:39:05Z
  send as : taku_yamashita@mxvideo.jp
  note    : last inbound looks like an acknowledgement, not an answer

chase now (1):
    6d  Re: InterBEE 2026 での展示のご相談  [send as taku_yamashita@mxvideo.jp]
```

- 経過日数は **JST の営業日**で数えます。`--now` にはセッションの日付を必ず渡してください
  （コンテナの時計はずれていることがあります）。祝日は `[followup] holidays` にあります。
- `--sent` に渡した送信済みメールのうち、同じ本文を複数の相手に送ったもの（出展案内など）は
  一斉配信と判定し、返信待ちには入れません。
- 催促の下書きは、`00_催促済み` ラベル・既存の下書き・1回あたりの上限（既定 5 通）の
  3 つで重複を防ぎます。判定は `chase_plan()` が行い、文面は Claude が書きます。
- `create_draft` に差出人を指定する手段がないため、下書きごとに「どのアドレスから送るべきか」を
  報告に明記します。送信前に差出人の確認が必要です。

## 構成

```
.claude/skills/mx-mail-draft/   下書き作成の手順・文体ガイド（Claude が読む）
  SKILL.md                      ワークフロー本体
  references/style-guide.md     日英それぞれの文体・定型・作例
  references/parties.md         相手先の役割と注意点
.claude/skills/mx-followup/     返信待ちの巡回・催促下書きの手順（Claude が読む）
config/routing.toml             ドメイン判定・除外リスト・キーワード・案件登録・返信待ちの設定
docs/followup.md                返信待ちの巡回の設計メモ
mxmail/triage.py                仕分けロジック（言語判定・振り分け）
mxmail/linkage.py               スレッド間の突き合わせ・未転送検出
mxmail/followup.py              返信待ちの判定・一斉配信の検出・催促の計画
mxmail/cli.py                   コマンドライン
samples/                        テスト用のサンプルメール（すべて架空）
tests/                          テスト
```

仕分けの機械的な部分（誰から来たか・何語か・もう一方への下書きが要りそうか）は
Python 側で毎回同じ基準で判定します。文面と「本当に必要か」の最終判断は、
スレッドを読んだうえで Claude が行います。

## 使い方

Claude Code で下記のように依頼すると `mx-mail-draft` スキルが起動します。

```
新着メールの下書きを作成して
taku_yamashita@mxvideo.jp の未読を処理して
```

返信待ちの巡回は `mx-followup` スキルが担当します。

```
返信待ちのスレッドを確認して
催促の下書きを作って
```

仕分けだけを単体で確認する場合:

```bash
# Gmail の thread JSON を渡す
python3 -m mxmail.cli --thread samples/thread_matrox_po.json --format text

# 単一メッセージ / 標準入力も可
python3 -m mxmail.cli --message samples/message_newsletter.json
cat thread.json | python3 -m mxmail.cli --thread - --format text
```

出力例:

```
subject : RE: X.mio5 lead time
from    : ltang@matrox.com
action  : draft
side    : matrox (Matrox head office)
incoming: en
reply   : draft a reply in EN
also    : suggested companion draft to customer in JA
          signals: lead time, stock, ship
```

## 設定

相手先の追加・除外設定は `config/routing.toml` を編集します。Python の
コードを触る必要はありません。

- `[sides] matrox` — Matrox 側とみなすドメイン
- `[ignore]` — 下書きを作らない差出人・ドメイン・件名パターン
- `[[parties]]` — 既知の相手先（会社名・区分・通常の使用言語）
- `[companion_signals]` — もう一方への下書きが必要そうかを示すキーワード
- `[[cases]]` — 日英で名前が違う案件の別名登録（スレッド突き合わせ用）
- `[followup]` — 返信待ちのラベル・催促までの営業日数・1回あたりの上限・祝日・差出人の既定

> `[sides] matrox` には `matrox.com` と `matrox.jp` の両方を入れてあります。
> 本社からのメールは実際には `@matrox.com` で届くためです。

## テスト

```bash
python3 -m unittest discover -s tests -v
```

依存パッケージはありません（Python 3.11 以上）。

## 制約

- 作るのは**下書きのみ**。送信・アーカイブは行いません。
  ラベルの付け外しは返信待ちの巡回に限り、`00_返信待ち` と `00_催促済み` の 2 つだけを扱います。
- スレッドに書かれていない納期・価格・不具合の責任範囲は書きません。
  不明な点は `【要確認：…】` / `[TBC: …]` として残し、報告します。
- `samples/` のメールはすべて架空のものです。実際の顧客メールは
  このリポジトリにコミットしません。
