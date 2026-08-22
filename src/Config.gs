/**
 * MX CRM 自動化 - 設定
 *
 * Notion のインテグレーショントークンは、ソースには書かず
 * スクリプトプロパティ（プロジェクトの設定 > スクリプト プロパティ）に保存する。
 *   キー: NOTION_TOKEN   値: ntn_xxxxxxxx...
 */

var CONFIG = {
  // Notion CRM データベース（MX_CRM 顧客・接点管理）
  NOTION_DATABASE_ID: 'dd6c84a357164dd9a7075358a4cff9a5',
  NOTION_VERSION: '2022-06-28',

  // 自分のメールアドレス（送信者判定に使う。すべて小文字で書く）
  MY_ADDRESSES: [
    'taku_yamashita@mxvideo.jp',
    'mmhgf8314@gmail.com'
  ],

  // 接点として数えない社内・グループ企業のドメイン
  INTERNAL_DOMAINS: [
    'mxvideo.jp',
    'matrox.com',
    'matrox0.onmicrosoft.com',
    'golter.jp'
  ],

  // Gmail を遡って検索する日数
  LOOKBACK_DAYS: 400,

  // 何日接点がなければフォロー対象とするか
  FOLLOWUP_INTERVAL_DAYS: 30,

  // 月次ダイジェストの送信先（空なら実行ユーザー自身に送る）
  DIGEST_TO: '',

  // 下書きを自動作成する優先度（月次フォローアップ時）
  DRAFT_PRIORITIES: ['A', 'B'],

  // Notion のプロパティ名（Notion 側で列名を変えたらここも変える）
  PROP: {
    company: '会社名',
    segment: '区分',
    status: 'ステータス',
    priority: '優先度',
    person: '主担当者',
    email: 'メール',
    lastContact: '最終接点日',
    lastAction: '最終アクション',
    nextAction: '次のアクション',
    nextFollowUp: '次回フォロー予定日',
    channels: '接点チャネル',
    note: 'メモ'
  }
};

/** Notion トークンをスクリプトプロパティから読む。 */
function getNotionToken_() {
  var token = PropertiesService.getScriptProperties().getProperty('NOTION_TOKEN');
  if (!token) {
    throw new Error(
      'NOTION_TOKEN が未設定です。Apps Script の「プロジェクトの設定 > スクリプト プロパティ」に ' +
      'NOTION_TOKEN を追加してください。'
    );
  }
  return token;
}
