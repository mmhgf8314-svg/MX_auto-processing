# MX CRM セットアップ

Google Apps Script で Gmail → Notion CRM の自動同期と月次フォローアップを動かす手順。

台帳: Notion の Business > MX > **MX_CRM 顧客・接点管理**
（データベース ID: `dd6c84a357164dd9a7075358a4cff9a5`）

## 1. Notion インテグレーションを作る

1. <https://www.notion.so/my-integrations> で内部インテグレーションを作成し、トークンを控える
2. Notion で **`Business > MX`** ページを開き、右上の `···` > `接続` > `接続を追加` から
   作ったインテグレーションを選ぶ

接続する場所は **`MX` ページの1か所だけでよい**。CRM データベースは `MX` の子として
置いてあり、インテグレーションの権限は子ページに引き継がれるので、これで CRM と議事録の
両方が読めるようになる。

接続していないページは API から存在しないのと同じ扱いになる。CRM が 404 になる、
議事録が1件も取れない、というときはまずここを疑う。

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

1. `dryRunSync` を実行する。Notion には書き込まず、Gmail から
   「どの行がどう更新される予定か」だけを実行ログに出す
2. `dryRunNotionScan` を実行する。こちらは議事録側の突き合わせ結果を出す。
   「（未一致）」が並ぶ議事録は、`Config.gs` の `MEETING_ALIASES` に別名を足すと拾えるようになる
3. 意図どおりなら `syncDaily` を1回手で実行する（メールと議事録の両方を同期する）
4. `sendFollowupDigestOnly` を実行して、ダイジェストメールの体裁を確認する

初回実行時に Gmail と Notion へのアクセス許可を求められる。

## 5. トリガーを設置する

`setUpTriggers` を1回実行する。

| タイミング | 関数 | 内容 |
| --- | --- | --- |
| 毎日 07 時台 | `syncDaily` | Gmail → Notion 議事録 の順に最終接点日を同期 |
| 毎月 1 日 08 時台 | `runMonthlyFollowup` | ダイジェスト送信＋A/B の下書き作成 |

現在のトリガーは `listTriggers`、外すなら `removeTriggers`。

## 設定を変える

`src/Config.gs` を編集する。

| 項目 | 意味 |
| --- | --- |
| `MY_ADDRESSES` | 送信者判定に使う自分のアドレス。すべて小文字で書く |
| `INTERNAL_DOMAINS` | 接点としてカウントしないドメイン（Matrox 本社など） |
| `LOOKBACK_DAYS` | Gmail を遡る日数 |
| `NOTION_LOOKBACK_DAYS` | Notion の議事録を遡る日数 |
| `NOTION_MEETING_PARENT_PAGE_ID` | 議事録トグルがぶら下がっている親ページ（Business > MX）。空にするとトグル取り込みを止める |
| `MEETING_ALIASES` | 議事録タイトルと CRM の行を突き合わせる別名。会社名は自動で使われるので、議事録で別の書き方をされる先だけ書く |
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
| 議事録が1件も読まれない | `Business > MX` ページにインテグレーションを接続していない。`dryRunNotionScan` で0件なら確実にこれ |
| 議事録が特定の会社に紐づかない | `MEETING_ALIASES` に別名がない。`dryRunNotionScan` の「（未一致）」を見て足す |
| 違う会社の議事録が紐づいた | 別名が短すぎて誤爆している。より長い別名に変える |
| 日付が戻される | 手入力した日付の方が古い。自動同期は新しい方を採用する |
