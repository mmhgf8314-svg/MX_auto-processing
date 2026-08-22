/**
 * Notion API の薄いラッパー。
 * CRM データベースの読み書きだけを担当する。
 */

function notionFetch_(path, method, payload) {
  var options = {
    method: method,
    contentType: 'application/json',
    muteHttpExceptions: true,
    headers: {
      Authorization: 'Bearer ' + getNotionToken_(),
      'Notion-Version': CONFIG.NOTION_VERSION
    }
  };
  if (payload) options.payload = JSON.stringify(payload);

  var res = UrlFetchApp.fetch('https://api.notion.com/v1' + path, options);
  var code = res.getResponseCode();
  var body = res.getContentText();
  if (code < 200 || code >= 300) {
    throw new Error('Notion API ' + method + ' ' + path + ' が ' + code + ' を返しました: ' + body);
  }
  return JSON.parse(body);
}

/** CRM の全レコードを取得する（ページングを含む）。 */
function fetchCrmRows() {
  var rows = [];
  var cursor = null;
  do {
    var payload = { page_size: 100 };
    if (cursor) payload.start_cursor = cursor;
    var res = notionFetch_('/databases/' + CONFIG.NOTION_DATABASE_ID + '/query', 'post', payload);
    res.results.forEach(function (page) {
      rows.push(parseCrmPage_(page));
    });
    cursor = res.has_more ? res.next_cursor : null;
  } while (cursor);
  return rows;
}

function parseCrmPage_(page) {
  var p = page.properties;
  var P = CONFIG.PROP;
  return {
    id: page.id,
    url: page.url,
    company: plainText_(p[P.company]),
    segment: selectName_(p[P.segment]),
    status: selectName_(p[P.status]),
    priority: selectName_(p[P.priority]),
    person: plainText_(p[P.person]),
    email: p[P.email] ? p[P.email].email : '',
    lastContact: dateStart_(p[P.lastContact]),
    lastAction: plainText_(p[P.lastAction]),
    nextAction: plainText_(p[P.nextAction]),
    nextFollowUp: dateStart_(p[P.nextFollowUp]),
    note: plainText_(p[P.note])
  };
}

function plainText_(prop) {
  if (!prop) return '';
  var arr = prop.title || prop.rich_text;
  if (!arr) return '';
  return arr.map(function (t) { return t.plain_text; }).join('');
}

function selectName_(prop) {
  return prop && prop.select ? prop.select.name : '';
}

function dateStart_(prop) {
  return prop && prop.date ? prop.date.start : '';
}

/** CRM の1行を更新する。fields は { 最終接点日: '2026-08-22', 最終アクション: '...' } の形。 */
function updateCrmRow(pageId, fields) {
  var P = CONFIG.PROP;
  var properties = {};

  if (fields[P.lastContact]) {
    properties[P.lastContact] = { date: { start: fields[P.lastContact] } };
  }
  if (fields[P.nextFollowUp]) {
    properties[P.nextFollowUp] = { date: { start: fields[P.nextFollowUp] } };
  }
  if (fields[P.lastAction]) {
    properties[P.lastAction] = { rich_text: [{ text: { content: truncate_(fields[P.lastAction], 1900) } }] };
  }
  if (fields[P.nextAction]) {
    properties[P.nextAction] = { rich_text: [{ text: { content: truncate_(fields[P.nextAction], 1900) } }] };
  }
  if (fields[P.status]) {
    properties[P.status] = { select: { name: fields[P.status] } };
  }

  if (Object.keys(properties).length === 0) return null;
  return notionFetch_('/pages/' + pageId, 'patch', { properties: properties });
}

function truncate_(text, max) {
  text = String(text || '');
  return text.length > max ? text.slice(0, max - 1) + '…' : text;
}
