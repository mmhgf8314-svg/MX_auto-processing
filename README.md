# MX_auto-processing

`taku_yamashita@mxvideo.jp` を中心にした、MX（Matrox）・VRi（Visual Research）業務の自動化。現在二つの機能が入っている。

| 機能 | 内容 | 実行環境 |
| --- | --- | --- |
| **メール下書きワークフロー** | 受信メールを仕分け、返信ともう一方の相手への下書きを作る | Claude Code + Python |
| **CRM ・ 月次フォローアップ** | 顧客ごとの接点を Notion の台帳で管理し、1ヶ月に一度全件をフォローする | Google Apps Script |

---

# 1. メール下書きワークフロー

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

---

# 2. CRM ・ 月次フォローアップ

MX（Matrox）と VRi（Visual Research）の顧客・パートナーについて「誰に・いつ・
どのようなアクションをしたか・今どうなっているか」を Notion の台帳で一元管理し、
Gmail の実際のやり取りから最終接点日を自動更新して、
**1ヶ月に一度すべての取引先をフォローアップする**。

台帳: Notion の Business > MX > **MX / VRi CRM 顧客・接点管理**

### 前提となる商売の形

**MX と VRi は別メーカー**なので、台帳では `メーカー` 列で区別する（両方扱う先は両方付ける）。

| | MX（Matrox） | VRi（Visual Research） |
| --- | --- | --- |
| 製品 | OEM 向け製品（ORIGIN / ORIGIN Fabric / DSX・LE / Xmio / M264 / SDK）と EU 向け製品（Monarch EDGE / ConvertIP / AVIO2・IPMX / VION）の2種 | Karisma Illuzon / Karisma CG3 / Karisma Studio |
| 市場 | 放送 または 医療 | 放送 |
| 顧客 | SI（販社）/ EU（エンドユーザー）/ OEM | SI（販社）/ EU（エンドユーザー） |
| 商流 | JM→販社→EU、JM→OEM、JM→EU | JM→販社→EU、JM→EU |

いずれも起点は JM（ジャパンマテリアル）。OEM と SI を兼ねる先（朋栄、NEC など）があるため
顧客区分は複数選択。OEM の顧客が EU 向け製品を買うこともあるので、製品区分も複数付く。

### ビュー

| ビュー | 用途 |
| --- | --- |
| 既定のテーブル | 全件一覧 |
| 🔴 要フォロー（30日以上未接触） | 月次フォローアップの作業リスト。放置が長い順 |
| ステータス別ボード | 商談の進み具合を俯瞰する |
| 顧客区分別（SI / EU / OEM） | 商流ごとに誰を抱えているかを見る |
| VRi 案件 | VRi のみを抜き出す |
| フォロー予定カレンダー | 「次回フォロー予定日」を月カレンダーで見る |
| ⭐ 重点顧客（A） | 優先度 A だけを追う |

## 構成

```
src/Config.gs        設定（Notion DB ID、自分のアドレス、社内ドメイン、フォロー間隔）
src/Notion.gs        Notion API の読み書き
src/GmailScan.gs     Gmail を走査して最終接点日・最終アクションを更新
src/NotionScan.gs    Notion の議事録を走査して、会議・訪問の接点を取り込む
src/Followup.gs      月次フォローアップ（ダイジェスト送信＋下書き作成）
src/Triggers.gs      毎日の同期 syncDaily、トリガー設置、書き込みなしの動作確認
src/appsscript.json  マニフェスト
```

## セットアップと運用

- セットアップ手順: [docs/CRM-setup.md](docs/CRM-setup.md)
- 日々の運用ルール: [docs/CRM運用ガイド.md](docs/CRM運用ガイド.md)

### 自動更新の元ネタ

| 元ネタ | 拾うもの | 最終アクションの書き出し |
| --- | --- | --- |
| Gmail | メールのやり取り | `[自動更新]` |
| Notion の議事録 | オンライン会議・訪問の記録 | `[議事録]` |

毎朝 07 時台に Gmail → 議事録 の順で走り、同じ会社に両方あれば**日付が新しい方が残る**。
手で入れた日付の方が新しい場合は、どちらも上書きしない。

自動同期が触るのは **最終接点日 / 最終アクション / 次回フォロー予定日** の3つだけ。
ステータスと「次のアクション」は人が判断して書く欄なので、スクリプトは変更しない。
こちらも作るのは下書きのみで、顧客への自動送信は行わない（月次ダイジェストのみ自分宛に送信）。
