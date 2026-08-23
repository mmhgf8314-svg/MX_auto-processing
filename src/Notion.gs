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

/**
 * 直近に更新された Notion ページを検索する。議事録の取り込みに使う。
 * インテグレーションが接続されているページ・DBだけが返る。
 */
function searchRecentNotionPages(sinceIso, maxPages) {
  var results = [];
  var cursor = null;
  var stop = false;

  do {
    var payload = {
      page_size: 100,
      filter: { property: 'object', value: 'page' },
      sort: { direction: 'descending', timestamp: 'last_edited_time' }
    };
    if (cursor) payload.start_cursor = cursor;

    var res = notionFetch_('/search', 'post', payload);
    for (var i = 0; i < res.results.length; i++) {
      var page = res.results[i];
      if (page.last_edited_time < sinceIso) { stop = true; break; }
      if (page.parent && page.parent.database_id &&
          page.parent.database_id.replace(/-/g, '') === CONFIG.NOTION_DATABASE_ID.replace(/-/g, '')) {
        continue; // CRM 自身の行は対象外
      }
      results.push({
        id: page.id,
        url: page.url,
        title: pageTitle_(page),
        created: (page.created_time || '').slice(0, 10),
        edited: (page.last_edited_time || '').slice(0, 10)
      });
      if (results.length >= (maxPages || 200)) { stop = true; break; }
    }
    cursor = (!stop && res.has_more) ? res.next_cursor : null;
  } while (cursor);

  return results;
}

/** 検索結果のページからタイトル文字列を取り出す。 */
function pageTitle_(page) {
  var props = page.properties || {};
  for (var key in props) {
    var p = props[key];
    if (p && p.type === 'title' && p.title && p.title.length) {
      return p.title.map(function (t) { return t.plain_text; }).join('');
    }
  }
  return '(無題)';
}

/**
 * ページ直下のトグル見出しを集める。
 * MX ページのようにトグルの中へ議事録をぶら下げている場合に使う。
 */
function fetchToggleHeadings(blockId, maxDepth) {
  var out = [];
  collectToggles_(blockId, maxDepth === undefined ? 2 : maxDepth, out);
  return out;
}

function collectToggles_(blockId, depth, out) {
  if (depth < 0) return;
  var cursor = null;
  do {
    var path = '/blocks/' + blockId.replace(/-/g, '') + '/children?page_size=100' +
      (cursor ? '&start_cursor=' + cursor : '');
    var res = notionFetch_(path, 'get', null);

    res.results.forEach(function (block) {
      if (block.type === 'toggle' && block.toggle && block.toggle.rich_text) {
        var text = block.toggle.rich_text.map(function (t) { return t.plain_text; }).join('');
        if (text) {
          out.push({
            id: block.id,
            title: text,
            created: (block.created_time || '').slice(0, 10),
            edited: (block.last_edited_time || '').slice(0, 10),
            url: null
          });
        }
      }
      if (block.has_children && depth > 0 && block.type !== 'toggle') {
        collectToggles_(block.id, depth - 1, out);
      }
    });

    cursor = res.has_more ? res.next_cursor : null;
  } while (cursor);
}
