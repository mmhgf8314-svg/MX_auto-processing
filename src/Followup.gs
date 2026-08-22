/**
 * 月次フォローアップ。
 *
 * 1) 最終接点から FOLLOWUP_INTERVAL_DAYS 日以上たった取引先を洗い出す
 * 2) 一覧をダイジェストメールとして自分に送る
 * 3) 優先度 A / B の分は Gmail の下書きまで作る（送信はしない）
 */

function runMonthlyFollowup() {
  var overdue = listOverdue_();
  sendFollowupDigest_(overdue);
  var drafted = createFollowupDrafts_(overdue);
  var msg = '月次フォローアップ: 対象 ' + overdue.length + ' 件 / 下書き作成 ' + drafted + ' 件';
  Logger.log(msg);
  return msg;
}

/** ダイジェストだけ送りたいときはこちらを実行する。 */
function sendFollowupDigestOnly() {
  var overdue = listOverdue_();
  sendFollowupDigest_(overdue);
  return 'ダイジェスト送信: ' + overdue.length + ' 件';
}

function listOverdue_() {
  var limit = CONFIG.FOLLOWUP_INTERVAL_DAYS;
  return fetchCrmRows()
    .filter(function (row) {
      if (row.status === 'クローズ') return false;
      return daysSince_(row.lastContact) >= limit;
    })
    .map(function (row) {
      row.elapsed = daysSince_(row.lastContact);
      return row;
    })
    .sort(function (a, b) {
      var rank = { A: 0, B: 1, C: 2 };
      var d = (rank[a.priority] === undefined ? 3 : rank[a.priority]) -
              (rank[b.priority] === undefined ? 3 : rank[b.priority]);
      return d !== 0 ? d : b.elapsed - a.elapsed;
    });
}

function sendFollowupDigest_(overdue) {
  var to = CONFIG.DIGEST_TO || Session.getActiveUser().getEmail();
  var today = todayIso_();
  var subject = '[MX CRM] ' + today + ' 月次フォローアップ ' + overdue.length + ' 件';

  var html = '<p>最終接点から ' + CONFIG.FOLLOWUP_INTERVAL_DAYS + ' 日以上たっている取引先です。</p>' +
    '<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-size:13px">' +
    '<tr style="background:#f2f2f2">' +
    '<th>優先度</th><th>会社名</th><th>ステータス</th><th>担当</th>' +
    '<th>最終接点</th><th>経過</th><th>最終アクション</th><th>次のアクション</th></tr>';

  overdue.forEach(function (row) {
    html += '<tr>' +
      '<td align="center">' + esc_(row.priority) + '</td>' +
      '<td><a href="' + row.url + '">' + esc_(row.company) + '</a></td>' +
      '<td>' + esc_(row.status) + '</td>' +
      '<td>' + esc_(row.person) + '</td>' +
      '<td align="center">' + esc_(row.lastContact || '未接触') + '</td>' +
      '<td align="right">' + row.elapsed + '日</td>' +
      '<td>' + esc_(row.lastAction) + '</td>' +
      '<td>' + esc_(row.nextAction) + '</td>' +
      '</tr>';
  });
  html += '</table>' +
    '<p>Notion の CRM: <a href="https://www.notion.so/' + CONFIG.NOTION_DATABASE_ID + '">MX_CRM 顧客・接点管理</a></p>';

  GmailApp.sendEmail(to, subject, '', { htmlBody: html, name: 'MX CRM' });
}

/** 優先度が DRAFT_PRIORITIES に含まれる取引先に、フォローメールの下書きを作る。 */
function createFollowupDrafts_(overdue) {
  var count = 0;
  overdue.forEach(function (row) {
    if (CONFIG.DRAFT_PRIORITIES.indexOf(row.priority) < 0) return;
    if (!row.email) return;

    var subject = 'ご無沙汰しております（Matrox・山下）';
    var body = buildFollowupBody_(row);
    GmailApp.createDraft(row.email, subject, body);
    count++;
  });
  return count;
}

function buildFollowupBody_(row) {
  var person = row.person ? row.person.split(/[、,]/)[0].trim() : 'ご担当者様';
  var lines = [
    person,
    '',
    'いつもお世話になっております。Matrox の山下です。',
    '',
    'その後いかがでしょうか。' + (row.lastContact ? '前回ご連絡させていただいてから ' + row.elapsed + ' 日ほど経ちましたので、' : '') +
      '状況伺いのご連絡を差し上げました。',
    ''
  ];

  lines.push('お忙しいところ恐縮ですが、ご確認のほどよろしくお願い申し上げます。');
  lines.push('');
  lines.push('---');
  lines.push('Matrox Video Japan');
  lines.push('山下 卓');
  lines.push('taku_yamashita@mxvideo.jp');

  // ここから下は社内メモ。送信前に必ず削除する。
  lines.push('');
  lines.push('===== 社内メモ（送信前に削除）=====');
  if (row.nextAction) lines.push('次のアクション: ' + row.nextAction);
  if (row.lastAction) lines.push('前回のやり取り: ' + row.lastAction.replace('[自動更新] ', ''));
  lines.push('ステータス: ' + row.status + ' / 最終接点: ' + (row.lastContact || '未接触'));
  lines.push('CRM: ' + row.url);

  return lines.join('\n');
}

function esc_(s) {
  return String(s === undefined || s === null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
