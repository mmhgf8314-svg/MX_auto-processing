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

## 構成

```
.claude/skills/mx-mail-draft/   下書き作成の手順・文体ガイド（Claude が読む）
  SKILL.md                      ワークフロー本体
  references/style-guide.md     日英それぞれの文体・定型・作例
  references/parties.md         相手先の役割と注意点
config/routing.toml             ドメイン判定・除外リスト・キーワード
mxmail/triage.py                仕分けロジック（言語判定・振り分け）
mxmail/cli.py                   コマンドライン
samples/                        テスト用のサンプルメール（すべて架空）
tests/test_triage.py            テスト
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

> `[sides] matrox` には `matrox.com` と `matrox.jp` の両方を入れてあります。
> 本社からのメールは実際には `@matrox.com` で届くためです。

## テスト

```bash
python3 -m unittest discover -s tests -v
```

依存パッケージはありません（Python 3.11 以上）。

## 制約

- 作るのは**下書きのみ**。送信・アーカイブ・ラベル付けは行いません。
- スレッドに書かれていない納期・価格・不具合の責任範囲は書きません。
  不明な点は `【要確認：…】` / `[TBC: …]` として残し、報告します。
- `samples/` のメールはすべて架空のものです。実際の顧客メールは
  このリポジトリにコミットしません。
