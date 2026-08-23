/**
 * MX CRM 自動化 - 設定
 *
 * Notion のインテグレーショントークンは、ソースには書かず
 * スクリプトプロパティ（プロジェクトの設定 > スクリプト プロパティ）に保存する。
 *   キー: NOTION_TOKEN   値: ntn_xxxxxxxx...
 */

var CONFIG = {
  // Notion CRM データベース（MX / VRi CRM 顧客・接点管理）
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

  // Notion の議事録を遡って見る日数
  NOTION_LOOKBACK_DAYS: 120,

  // 議事録トグルがぶら下がっている親ページ（Business > MX）。空にすればトグル取り込みを止める
  NOTION_MEETING_PARENT_PAGE_ID: '18a50a348aa847c68de8a7577c505e8a',

  // 何日接点がなければフォロー対象とするか
  FOLLOWUP_INTERVAL_DAYS: 30,

  // 月次ダイジェストの送信先（空なら実行ユーザー自身に送る）
  DIGEST_TO: '',

  // 下書きを自動作成する優先度（月次フォローアップ時）
  DRAFT_PRIORITIES: ['A', 'B'],

  // Notion のプロパティ名（Notion 側で列名を変えたらここも変える）
  PROP: {
    company: '会社名',
    maker: 'メーカー',          // MX / VRi（別メーカー）
    segment: '顧客区分',        // SI（販社）/ EU（エンドユーザー）/ OEM / JM / メーカー・ベンダー
    market: '市場',             // 放送 / 医療
    tradeFlow: '商流',          // JM→販社→EU / JM→OEM / JM→EU
    productClass: '製品区分',   // MX_OEM向け製品 / MX_EU向け製品 / VRi製品
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
  },

  /**
   * 議事録のタイトルと CRM の行を突き合わせるための別名。
   * 会社名そのものは自動で使われるので、議事録で別の書き方をされる先だけ書けばよい。
   * 一致は「いちばん長い別名が勝つ」ので、Sony Medical は ソニーメディカル に付く。
   */
  MEETING_ALIASES: {
    'ソニー（放送 / SMOJ）': ['ソニー', 'Sony', 'SMOJ', 'ソニーマーケティング'],
    'ソニーメディカル': ['Sony Medical', 'ソニーメディカル', 'ソニー メディカル'],
    'パナソニック（Panasonic Connect）': ['パナソニック', 'Panasonic', 'KAIROS'],
    'ジャパンマテリアル（JM）': ['ジャパンマテリアル', 'Japan Material', 'JM'],
    'QVCジャパン': ['QVC', 'QCV'],
    '伊藤忠ケーブルシステム': ['伊藤忠', 'ICS'],
    '朋栄（FOR-A）': ['朋栄', 'FOR-A', 'For-A', 'FORA'],
    '日本テレビ': ['日本テレビ', '日テレ', 'NTV'],
    '日テレWANDS': ['WANDS'],
    '毎日放送（MBS）': ['MBS', '毎日放送'],
    '三友': ['三友'],
    'アクワイア': ['アクワイア', 'Acquire'],
    'サイバネットシステム': ['サイバネット', 'EndoBRAIN', '内視鏡'],
    'テクノネット': ['テクノネット'],
    'ネクシオン（Nexion）': ['ネクシオン', 'Nexion'],
    'ブロードデザイン': ['ブロードデザイン', 'Broad Design'],
    'メイコーエレクトロニクス（meiko-elec）': ['メイコー'],
    'グラスバレー（Grass Valley）': ['グラスバレー', 'Grass Valley', 'GrassValley'],
    'Taenam（韓国）': ['Taenam', 'テナム'],
    'VRi（Visual Research・韓国）': ['VRi', 'VRI', 'Visual Research', 'Karisma', 'Kビジョン', 'KVISION', 'Kvision'],
    'ティアック（TEAC）': ['TEAC', 'ティアック'],
    'TVS NEXT（tvs.co.jp）': ['TVsNext', 'TVS NEXT', 'TVS'],
    'トラフィックシム': ['トラフィックシム'],
    '7th dimensions': ['7th dimensions', '7th'],
    'デジデリック': ['デジデリック'],
    'スカパーJSAT': ['スカパー', 'JSAT'],
    '東京サウンド・プロダクション（TSP）': ['東京サウンド', 'TSP'],
    'J:COM（ジュピターテレコム）': ['J:COM', 'JCOM', 'ジュピターテレコム'],
    'ヤマハミュージックジャパン': ['ヤマハ', 'Yamaha'],
    'レスターグループ（restargp）': ['レスター'],
    'カリーナシステム': ['カリーナ'],
    'SC-NET（sc-net.ne.jp）': ['SC-NET', 'エスシーネット'],
    'mpeg.co.jp（竹松 様）': [],
    'GlobalM': ['GlobalM', 'Global M']
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
