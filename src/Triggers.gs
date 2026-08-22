/**
 * トリガーの設置・確認。setUpTriggers を1回だけ実行すればよい。
 */

var TRIGGER_HANDLERS = ['syncLastContactFromGmail', 'runMonthlyFollowup'];

function setUpTriggers() {
  removeTriggers();

  // 毎朝 7 時台に Gmail から最終接点日を同期
  ScriptApp.newTrigger('syncLastContactFromGmail')
    .timeBased().atHour(7).everyDays(1).inTimezone('Asia/Tokyo').create();

  // 毎月 1 日の 8 時台に月次フォローアップ
  ScriptApp.newTrigger('runMonthlyFollowup')
    .timeBased().onMonthDay(1).atHour(8).inTimezone('Asia/Tokyo').create();

  return 'トリガーを設置しました: 毎日07時に同期 / 毎月1日08時に月次フォローアップ';
}

function removeTriggers() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (TRIGGER_HANDLERS.indexOf(t.getHandlerFunction()) >= 0) {
      ScriptApp.deleteTrigger(t);
    }
  });
}

function listTriggers() {
  var out = ScriptApp.getProjectTriggers().map(function (t) {
    return t.getHandlerFunction() + ' / ' + t.getEventType();
  });
  Logger.log(out.join('\n') || 'トリガーなし');
  return out;
}

/**
 * 初回の動作確認用。Notion に書き込まず、何が更新されるかだけをログに出す。
 */
function dryRunSync() {
  var rows = fetchCrmRows();
  var report = [];
  rows.forEach(function (row) {
    var domain = domainOf_(row.email);
    if (!domain || CONFIG.INTERNAL_DOMAINS.indexOf(domain) >= 0) return;
    var latest = latestMessageForDomain_(domain);
    if (!latest) {
      report.push(row.company + ': Gmail に該当なし（CRM=' + row.lastContact + '）');
      return;
    }
    if (row.lastContact && row.lastContact >= latest.date) {
      report.push(row.company + ': 変更なし（CRM=' + row.lastContact + ' / Gmail=' + latest.date + '）');
    } else {
      report.push(row.company + ': 更新予定 ' + row.lastContact + ' → ' + latest.date + ' / ' + formatAction_(latest));
    }
  });
  Logger.log(report.join('\n'));
  return report;
}
