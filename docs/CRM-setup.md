# MX CRM セットアップ

Google Apps Script で Gmail → Notion CRM の自動同期と月次フォローアップを動かす手順。

台帳: Notion の Business > MX > **MX_CRM 顧客・接点管理**
（データベース ID: `dd6c84a357164dd9a7075358a4cff9a5`）

## 1. Notion インテグレーションを作る

1. <https://www.notion.so/my-integrations> で内部インテグレーションを作成し、トークンを控える
2. Notion で `MX_CRM 顧客・接点管理` を開き、`···` > `接続` から作ったインテグレーションを追加する

この接続を忘れると API からデータベースが見えず、404 になる。

## 2. Apps Script プロジェクトを作る

1. <https://script.google.com> で新規プロジェクトを作る
2. `src/` 配下の `.gs` をそれぞれ同名のファイルとして貼り付ける
3. プロジェクトの設定で「マニフェスト ファイルをエディタで表示」をオンにし、
   `appsscript.json` の内容を反映する（OAuth スコープが入っている）

ローカルから一括で上げたい場合は [clasp](https://github.com/google/clasp) を使ってもよい。

## 3. トークンを登録する

プロジェクトの設定 > スクリプト プロパティ に以下を追加する。

| キー | 値 |
| --- | --- |
| `NOTION_TOKEN` | 1 で控えたインテグレーショントークン |

トークンはソースには書かない。

## 4. 動作確認する

1. `dryRunSync` を実行する。Notion には書き込まず、実行ログに
   「どの行がどう更新される予定か」だけを出す
2. 意図どおりなら `syncLastContactFromGmail` を1回手で実行する
3. `sendFollowupDigestOnly` を実行して、ダイジェストメールの体裁を確認する

初回実行時に Gmail と Notion へのアクセス許可を求められる。

## 5. トリガーを設置する

`setUpTriggers` を1回実行する。

| タイミング | 関数 | 内容 |
| --- | --- | --- |
| 毎日 07 時台 | `syncLastContactFromGmail` | Gmail から最終接点日を同期 |
| 毎月 1 日 08 時台 | `runMonthlyFollowup` | ダイジェスト送信＋A/B の下書き作成 |

現在のトリガーは `listTriggers`、外すなら `removeTriggers`。

## 設定を変える

`src/Config.gs` を編集する。

| 項目 | 意味 |
| --- | --- |
| `MY_ADDRESSES` | 送信者判定に使う自分のアドレス。すべて小文字で書く |
| `INTERNAL_DOMAINS` | 接点としてカウントしないドメイン（Matrox 本社など） |
| `LOOKBACK_DAYS` | Gmail を遡る日数 |
| `FOLLOWUP_INTERVAL_DAYS` | 何日接点がなければフォロー対象にするか（既定 30） |
| `DIGEST_TO` | 月次ダイジェストの送信先。空なら実行ユーザー自身 |
| `DRAFT_PRIORITIES` | 下書きを自動作成する優先度（既定 A・B） |
| `PROP` | Notion の列名。Notion 側で列をリネームしたらここも直す |

## トラブルシューティング

| 症状 | 原因 |
| --- | --- |
| `NOTION_TOKEN が未設定です` | スクリプトプロパティの登録もれ |
| Notion API が 404 | データベースにインテグレーションを接続していない |
| Notion API が 429 | レート制限。`Utilities.sleep` の値を増やす |
| ある行だけ更新されない | メール欄が空か、`INTERNAL_DOMAINS` に入っている |
| 日付が戻される | 手入力した日付の方が古い。自動同期は新しい方を採用する |
