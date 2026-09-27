/**
 * policy-harvest 승인 시트 스크립트
 *
 * 부서 계정 소유의 승인 시트에 붙여 쓴다(확장 프로그램 → Apps Script).
 * - doPost: GitHub Actions 수집기가 보낸 행을 inbox 탭에 추가한다(중복 제외)
 * - deliverApproved: 승인 칸이 체크된 행의 원본 파일을 받아 정책문서 폴더에 파일명 규칙대로 저장한다
 *   (매일 01:00 트리거. Policy Fit 색인은 03:00)
 *
 * 설정 절차: docs/setup-apps-script.md
 * 이 파일의 원본은 GitHub 레포 apps-script/Code.gs 다. 시트에서 고치지 말고 레포를 고쳐 다시 붙여 넣는다.
 */

var FOLDER_ID = '1-VLB42YhmZZIMxoR48J2qeIYgMYMdAK5'; // Policy Fit 정책문서 폴더
var SHEET_NAME = 'inbox';
var MAX_BYTES = 50 * 1024 * 1024; // UrlFetchApp 응답 한도
var INDEXED_EXT = ['pdf', 'hwpx', 'hwp']; // Policy Fit 색인이 읽는 형식
var CATEGORIES = ['부처', '공공기관', '교육청', '협의체'];

// [열 이름, 수집기가 보내는 키]. 키가 없는 열은 담당자·스크립트가 채운다
var COLUMNS = [
  ['수집일', 'collected_at'],
  ['글 키', 'post_key'],
  ['분류', 'category'],
  ['기관', 'org'],
  ['게시판', 'board'],
  ['제목', 'title'],
  ['원문 링크', 'post_url'],
  ['게시일', 'posted_at'],
  ['첨부 이름', 'att_name'],
  ['첨부 URL', 'att_url'],
  ['추천', 'recommend'],
  ['문서 유형', 'doc_type'],
  ['주제', 'topics'],
  ['추천 이유', 'reason'],
  ['문서명', 'doc_name'],
  ['구분', 'kind'],
  ['연도', 'year'],
  ['승인', null],
  ['상태', null],
  ['파일명', null],
  ['드라이브 링크', null],
];

// ── 파일명 규칙 (harvest/naming.py 와 같다) ─────────────────────────────

function cleanPart(text) {
  return String(text == null ? '' : text)
    .replace(/[_\\/:*?"<>|\n\r\t]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function extOf(name) {
  var m = /\.([A-Za-z0-9]+)$/.exec(String(name || '').split('?')[0]);
  return m ? m[1].toLowerCase() : '';
}

function buildName(number, category, org, title, year, ext, kind) {
  if (CATEGORIES.indexOf(category) < 0) throw new Error('분류가 규칙에 없습니다: ' + category);
  if (!/^\d+(-\d+)*$/.test(number)) throw new Error('번호 형식이 아닙니다: ' + number);
  if (!/^(19|20)\d{2}$/.test(String(year))) throw new Error('연도 형식이 아닙니다: ' + year);
  var parts = [number, category, cleanPart(org), cleanPart(title)];
  if (kind) parts.push(cleanPart(kind));
  parts.push(String(year));
  for (var i = 0; i < parts.length; i++) if (!parts[i]) throw new Error('빈 칸이 있습니다: ' + parts.join('_'));
  return parts.join('_') + '.' + String(ext).toLowerCase().replace(/^\./, '');
}

function groupNumber(name) {
  var m = /^(\d+)/.exec(String(name));
  return m ? parseInt(m[1], 10) : null;
}

function nextGroupNumber(names) {
  var max = 0;
  names.forEach(function (n) {
    var g = groupNumber(n);
    if (g !== null && g > max) max = g;
  });
  return max + 1;
}

/** 승인 행을 글 키별로 묶어 번호를 준다. 한 글에서 두 개 이상이면 12-1, 12-2 */
function assignNumbers(postKeys, startGroup) {
  var groups = {}, order = [];
  postKeys.forEach(function (k, i) {
    if (!(k in groups)) { groups[k] = []; order.push(k); }
    groups[k].push(i);
  });
  var out = new Array(postKeys.length), g = startGroup;
  order.forEach(function (k) {
    var idx = groups[k];
    idx.forEach(function (rowIdx, j) { out[rowIdx] = idx.length > 1 ? g + '-' + (j + 1) : String(g); });
    g++;
  });
  return out;
}

// ── 시트 ──────────────────────────────────────────────────────────────

function sheet_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(SHEET_NAME) || ss.insertSheet(SHEET_NAME);
  if (sh.getLastRow() === 0) {
    sh.appendRow(COLUMNS.map(function (c) { return c[0]; }));
    sh.setFrozenRows(1);
  }
  return sh;
}

function col_(label) {
  for (var i = 0; i < COLUMNS.length; i++) if (COLUMNS[i][0] === label) return i + 1;
  throw new Error('열 없음: ' + label);
}

/** 처음 한 번 실행: 탭·머리행·승인 체크박스·매일 01시 트리거를 만든다 */
function setup() {
  var sh = sheet_();
  var rule = SpreadsheetApp.newDataValidation().requireCheckbox().build();
  sh.getRange(2, col_('승인'), sh.getMaxRows() - 1, 1).setDataValidation(rule);
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'deliverApproved') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('deliverApproved').timeBased().everyDays(1).atHour(1).create();
  if (!PropertiesService.getScriptProperties().getProperty('TOKEN')) {
    PropertiesService.getScriptProperties().setProperty('TOKEN', Utilities.getUuid());
  }
  Logger.log('설정 완료. 수집기용 TOKEN: ' + PropertiesService.getScriptProperties().getProperty('TOKEN'));
}

// ── 수집기 → 시트 ─────────────────────────────────────────────────────

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function doPost(e) {
  var body;
  try {
    body = JSON.parse(e.postData.contents);
  } catch (err) {
    return json_({ ok: false, error: 'JSON 아님' });
  }
  var token = PropertiesService.getScriptProperties().getProperty('TOKEN');
  if (!token || body.token !== token) return json_({ ok: false, error: '토큰 불일치' });

  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var sh = sheet_();
    var last = sh.getLastRow();
    var seen = {};
    if (last > 1) {
      var keys = sh.getRange(2, col_('글 키'), last - 1, 1).getValues();
      var urls = sh.getRange(2, col_('첨부 URL'), last - 1, 1).getValues();
      for (var i = 0; i < keys.length; i++) seen[keys[i][0] + '|' + urls[i][0]] = true;
    }
    var added = 0, skipped = 0, rows = [];
    (body.rows || []).forEach(function (r) {
      var k = r.post_key + '|' + (r.att_url || '');
      if (!r.post_key || seen[k]) { skipped++; return; }
      seen[k] = true;
      rows.push(COLUMNS.map(function (c) {
        if (c[0] === '승인') return false;
        if (c[0] === '상태') return '대기';
        return c[1] && r[c[1]] != null ? (Array.isArray(r[c[1]]) ? r[c[1]].join(', ') : r[c[1]]) : '';
      }));
      added++;
    });
    if (rows.length) {
      var start = sh.getLastRow() + 1;
      sh.getRange(start, 1, rows.length, COLUMNS.length).setValues(rows);
      sh.getRange(start, col_('승인'), rows.length, 1)
        .setDataValidation(SpreadsheetApp.newDataValidation().requireCheckbox().build());
    }
    return json_({ ok: true, added: added, skipped: skipped });
  } finally {
    lock.releaseLock();
  }
}

// ── 승인 행 → 드라이브 ─────────────────────────────────────────────────

function deliverApproved() {
  var sh = sheet_();
  var last = sh.getLastRow();
  if (last < 2) return;
  var data = sh.getRange(2, 1, last - 1, COLUMNS.length).getValues();
  var c = function (label) { return col_(label) - 1; };

  var todo = [];
  data.forEach(function (row, i) {
    var status = String(row[c('상태')]);
    if (row[c('승인')] === true && status.indexOf('전송 완료') !== 0) todo.push(i);
  });
  if (!todo.length) return;

  var folder = DriveApp.getFolderById(FOLDER_ID);
  var existing = [];
  var it = folder.getFiles();
  while (it.hasNext()) existing.push(it.next().getName());

  var numbers = assignNumbers(todo.map(function (i) { return data[i][c('글 키')]; }), nextGroupNumber(existing));

  todo.forEach(function (i, n) {
    var row = data[i], r = i + 2;
    var setStatus = function (s) { sh.getRange(r, col_('상태')).setValue(s); };
    try {
      var ext = extOf(row[c('첨부 이름')]) || extOf(row[c('첨부 URL')]);
      if (INDEXED_EXT.indexOf(ext) < 0) { setStatus('실패: 색인되지 않는 형식(' + (ext || '알 수 없음') + ')'); return; }
      var name = buildName(numbers[n], String(row[c('분류')]), row[c('기관')], row[c('문서명')],
                           row[c('연도')], ext, row[c('구분')]);
      if (existing.indexOf(name) >= 0) { setStatus('실패: 같은 이름 있음'); return; }
      var res = UrlFetchApp.fetch(String(row[c('첨부 URL')]), { muteHttpExceptions: true, followRedirects: true });
      if (res.getResponseCode() !== 200) { setStatus('실패: 다운로드 HTTP ' + res.getResponseCode()); return; }
      var blob = res.getBlob();
      var bytes = blob.getBytes().length;
      if (bytes < 1024) { setStatus('실패: 파일이 너무 작음(' + bytes + 'B, 오류 페이지일 수 있음)'); return; }
      var file = folder.createFile(blob.setName(name));
      existing.push(name);
      sh.getRange(r, col_('파일명')).setValue(name);
      sh.getRange(r, col_('드라이브 링크')).setValue(file.getUrl());
      setStatus('전송 완료 ' + Utilities.formatDate(new Date(), 'Asia/Seoul', 'yyyy-MM-dd HH:mm'));
    } catch (err) {
      setStatus('실패: ' + String(err.message || err).slice(0, 200));
    }
  });
}

/** 수동 점검: 폴더 파일명 중 규칙과 다른 것을 로그로 남긴다 */
function checkFolderNames() {
  var it = DriveApp.getFolderById(FOLDER_ID).getFiles();
  while (it.hasNext()) {
    var n = it.next().getName();
    var parts = n.replace(/\.[^.]+$/, '').split('_');
    var ok = /^\d+(-\d+)*$/.test(parts[0]) && CATEGORIES.indexOf(parts[1]) >= 0 &&
             /^(19|20)\d{2}$/.test(parts[parts.length - 1]) && INDEXED_EXT.indexOf(extOf(n)) >= 0;
    if (!ok) Logger.log('규칙과 다름: ' + n);
  }
}
