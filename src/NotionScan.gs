/**
 * Notion の議事録を走査して、CRM の「最終接点日」「最終アクション」を更新する。
 *
 * メールに残らないオンライン会議・訪問の記録を拾うのが目的。
 * Gmail 同期と同じルールで、CRM 側の日付の方が新しければ上書きしない。
 *
 * 取り込み元は2か所:
 *   1) インテグレーションが接続されている、最近更新されたページ（議事録ページ）
 *   2) MX ページ直下のトグル見出し（MX_251002_QVC_... のような形式）
 */

function syncFromNotionMeetingNotes() {
  var P = CONFIG.PROP;
  var rows = fetchCrmRows();
  var matchers = buildMatchers_(rows);
  var notes = collectMeetingNotes_();
  var today = todayIso_();

  // 会社ごとに、いちばん新しい議事録だけを残す
  var best = {};
  notes.forEach(function (note) {
    var hit = matchNote_(note.title, matchers);
    if (!hit) return;
    var date = meetingDate_(note);
    if (!date || date > today) return;
    if (!best[hit.id] || date > best[hit.id].date) {
      best[hit.id] = { row: hit.row, date: date, note: note, alias: hit.alias };
    }
  });

  var updated = [];
  Object.keys(best).forEach(function (id) {
    var b = best[id];
    if (b.row.lastContact && b.row.lastContact >= b.date) return;

    var fields = {};
    fields[P.lastContact] = b.date;
    fields[P.lastAction] = '[議事録] ' + b.note.title + '（' + b.date + '）';
    if (!b.row.nextFollowUp || b.row.nextFollowUp <= today) {
      fields[P.nextFollowUp] = addDays_(b.date, CONFIG.FOLLOWUP_INTERVAL_DAYS);
    }
    updateCrmRow(b.row.id, fields);
    updated.push(b.row.company + ': ' + b.row.lastContact + ' → ' + b.date + '（' + b.note.title + '）');
    Utilities.sleep(350);
  });

  var msg = '議事録同期: ' + updated.length + ' 件更新 / 議事録 ' + notes.length + ' 件を確認';
  if (updated.length) msg += '\n' + updated.join('\n');
  Logger.log(msg);
  return msg;
}

/** 書き込まずに、何が更新されるかだけをログに出す。 */
function dryRunNotionScan() {
  var rows = fetchCrmRows();
  var matchers = buildMatchers_(rows);
  var notes = collectMeetingNotes_();
  var report = [];

  notes.forEach(function (note) {
    var hit = matchNote_(note.title, matchers);
    var date = meetingDate_(note);
    if (!hit) {
      report.push('（未一致）' + note.title);
      return;
    }
    var mark = (hit.row.lastContact && hit.row.lastContact >= date) ? '変更なし' : '更新予定';
    report.push(mark + ' ' + hit.row.company + ' [' + hit.alias + '] ' +
      hit.row.lastContact + ' / 議事録=' + date + ' : ' + note.title);
  });

  Logger.log(report.join('\n'));
  return report;
}

/** 議事録の候補をまとめて取得する。 */
function collectMeetingNotes_() {
  var since = addDays_(todayIso_(), -CONFIG.NOTION_LOOKBACK_DAYS) + 'T00:00:00.000Z';
  var notes = searchRecentNotionPages(since, 200);

  if (CONFIG.NOTION_MEETING_PARENT_PAGE_ID) {
    try {
      notes = notes.concat(fetchToggleHeadings(CONFIG.NOTION_MEETING_PARENT_PAGE_ID, 1));
    } catch (e) {
      Logger.log('トグル取得をスキップしました: ' + e.message);
    }
  }
  return notes;
}

/**
 * CRM の各行について、議事録タイトルと突き合わせるキーワードを組み立てる。
 * 会社名そのものと、Config の MEETING_ALIASES に書いた別名を使う。
 */
function buildMatchers_(rows) {
  var matchers = [];
  rows.forEach(function (row) {
    if (!row.company) return;
    if (row.status === 'クローズ') return;

    var words = [normalizeCompany_(row.company)];
    var extra = CONFIG.MEETING_ALIASES[row.company];
    if (extra) words = words.concat(extra);

    words.forEach(function (w) {
      w = String(w || '').trim();
      if (w.length < 2) return;
      matchers.push({ id: row.id, row: row, alias: w, key: w.toLowerCase() });
    });
  });
  // 長い別名を先に見るため、長さの降順に並べる（Sony Medical が Sony より優先される）
  matchers.sort(function (a, b) { return b.key.length - a.key.length; });
  return matchers;
}

/** 「ソニー（放送 / SMOJ）」→「ソニー」のように、括弧以降を落とす。 */
function normalizeCompany_(company) {
  return String(company).split(/[（(]/)[0].trim();
}

/** 議事録タイトルに含まれる別名のうち、いちばん長いものにマッチさせる。 */
function matchNote_(title, matchers) {
  var t = String(title || '').toLowerCase();
  if (!t) return null;
  for (var i = 0; i < matchers.length; i++) {
    if (t.indexOf(matchers[i].key) >= 0) return matchers[i];
  }
  return null;
}

/**
 * 議事録の日付を決める。
 * タイトルに日付が入っていればそれを使い、なければページの作成日にする。
 * 例: MX_251002_QVC... / 2025/07/02 / @2026年8月3日 / 250919
 */
function meetingDate_(note) {
  var d = parseDateInTitle_(note.title);
  return d || note.created || note.edited || '';
}

function parseDateInTitle_(title) {
  var t = String(title || '');
  var m;

  // 2026年8月3日
  m = t.match(/(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日/);
  if (m) return iso_(m[1], m[2], m[3]);

  // 2025/07/02 や 2025-07-02
  m = t.match(/(20\d{2})[\/\-](\d{1,2})[\/\-](\d{1,2})/);
  if (m) return iso_(m[1], m[2], m[3]);

  // MX_251002_... や _20250822_ のような区切り付きの数字だけを見る
  m = t.match(/(?:^|[_\s])(\d{8})(?:[_\s]|$)/);
  if (m) return iso_(m[1].slice(0, 4), m[1].slice(4, 6), m[1].slice(6, 8));

  m = t.match(/(?:^|[_\s])(\d{6})(?:[_\s]|$)/);
  if (m) {
    var yy = Number(m[1].slice(0, 2));
    var mm = Number(m[1].slice(2, 4));
    var dd = Number(m[1].slice(4, 6));
    if (mm >= 1 && mm <= 12 && dd >= 1 && dd <= 31) return iso_(2000 + yy, mm, dd);
  }

  return '';
}

function iso_(y, m, d) {
  var mm = ('0' + Number(m)).slice(-2);
  var dd = ('0' + Number(d)).slice(-2);
  return y + '-' + mm + '-' + dd;
}
