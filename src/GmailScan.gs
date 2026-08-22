/**
 * Gmail を走査して、CRM の「最終接点日」「最終アクション」を自動更新する。
 *
 * 毎日1回のトリガーで動かす想定。手で書いた「次のアクション」やステータスは触らない。
 */

function syncLastContactFromGmail() {
  var P = CONFIG.PROP;
  var rows = fetchCrmRows();
  var today = todayIso_();
  var updated = 0;
  var skipped = [];

  rows.forEach(function (row) {
    var domain = domainOf_(row.email);
    if (!domain) {
      skipped.push(row.company + '（メール未設定）');
      return;
    }
    if (CONFIG.INTERNAL_DOMAINS.indexOf(domain) >= 0) return;

    var latest = latestMessageForDomain_(domain);
    if (!latest) return;

    // Notion 側の方が新しい（手入力で会議などを記録した）場合は上書きしない
    if (row.lastContact && row.lastContact >= latest.date) return;

    var fields = {};
    fields[P.lastContact] = latest.date;
    fields[P.lastAction] = formatAction_(latest);

    // 次回フォロー予定日が過去のままなら、最終接点日 + 間隔 に繰り下げる
    if (!row.nextFollowUp || row.nextFollowUp <= today) {
      fields[P.nextFollowUp] = addDays_(latest.date, CONFIG.FOLLOWUP_INTERVAL_DAYS);
    }

    updateCrmRow(row.id, fields);
    updated++;
    Utilities.sleep(350); // Notion のレート制限（約3req/秒）に配慮
  });

  var msg = 'CRM 同期完了: ' + updated + ' 件更新 / 全 ' + rows.length + ' 件';
  if (skipped.length) msg += '\nメール未設定でスキップ: ' + skipped.join(', ');
  Logger.log(msg);
  return msg;
}

/** メールアドレスからドメインを取り出す。 */
function domainOf_(email) {
  if (!email) return '';
  var m = String(email).toLowerCase().match(/@([\w.\-]+)$/);
  return m ? m[1] : '';
}

/** 指定ドメインとの直近のメールを1通返す。 */
function latestMessageForDomain_(domain) {
  var query = 'newer_than:' + CONFIG.LOOKBACK_DAYS + 'd -in:spam -in:trash ' +
    '{from:' + domain + ' to:' + domain + ' cc:' + domain + '}';

  var threads = GmailApp.search(query, 0, 20);
  if (!threads.length) return null;

  var latest = null;
  threads.forEach(function (thread) {
    thread.getMessages().forEach(function (msg) {
      var involved = [msg.getFrom(), msg.getTo(), msg.getCc()].join(' ').toLowerCase();
      if (involved.indexOf('@' + domain) < 0) return;

      var when = msg.getDate();
      if (!latest || when > latest.when) {
        latest = {
          when: when,
          date: isoDate_(when),
          subject: msg.getSubject(),
          from: msg.getFrom(),
          outbound: isMine_(msg.getFrom())
        };
      }
    });
  });
  return latest;
}

function isMine_(fromHeader) {
  var f = String(fromHeader).toLowerCase();
  return CONFIG.MY_ADDRESSES.some(function (a) { return f.indexOf(a) >= 0; });
}

/** 「最終アクション」欄に入れる文言を組み立てる。 */
function formatAction_(latest) {
  var direction = latest.outbound ? 'こちらから送信' : '先方から受信';
  var subject = String(latest.subject || '(件名なし)').replace(/^((Re|RE|Fwd|FW|FW):\s*)+/, '');
  return '[自動更新] ' + direction + '「' + subject + '」（' + latest.date + '）';
}

function isoDate_(d) {
  return Utilities.formatDate(d, 'Asia/Tokyo', 'yyyy-MM-dd');
}

function todayIso_() {
  return isoDate_(new Date());
}

function addDays_(isoDateStr, days) {
  var parts = String(isoDateStr).split('-');
  var d = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
  d.setDate(d.getDate() + days);
  return isoDate_(d);
}

function daysSince_(isoDateStr) {
  if (!isoDateStr) return 99999;
  var parts = String(isoDateStr).split('-');
  var then = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
  var now = new Date();
  return Math.floor((now - then) / 86400000);
}
