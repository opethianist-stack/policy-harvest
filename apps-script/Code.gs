/**
 * policy-harvest 승인 시트 스크립트
 *
 * 부서 계정 소유의 승인 시트에 붙여 쓴다(확장 프로그램 → Apps Script).
 * - doPost: GitHub Actions 수집기가 보낸 행을 inbox 탭에 추가한다(중복 제외)
 * - deliverApproved: 승인 칸이 체크된 행의 원본 파일을 받아 정책문서 폴더에 파일명 규칙대로 저장한다
 *   (매일 01:00 트리거. Policy Fit 색인은 03:00). odt는 구글 문서로 변환해 PDF로 저장하고,
 *   zip은 풀어서 안의 파일을 저장한다
 *   → 편집기 왼쪽 "서비스 +"에서 Drive API(고급 서비스)를 추가해야 한다
 *
 * 설정 절차: docs/setup-apps-script.md
 * 이 파일의 원본은 GitHub 레포 apps-script/Code.gs 다. 시트에서 고치지 말고 레포를 고쳐 다시 붙여 넣는다.
 */

var FOLDER_ID = '1-VLB42YhmZZIMxoR48J2qeIYgMYMdAK5'; // Policy Fit 정책문서 폴더
var SHEET_NAME = 'inbox';
var MAX_BYTES = 50 * 1024 * 1024; // UrlFetchApp 응답 한도
var INDEXED_EXT = ['pdf', 'hwpx', 'hwp']; // Policy Fit 색인이 읽는 형식
var CONVERT_EXT = ['odt']; // PDF로 바꿔 저장하는 형식
var STORE_EXT = ['xlsx', 'xls']; // 색인되지 않지만 데이터 자료라 원본 그대로 저장하는 형식
var UNZIP_EXT = ['zip']; // 풀어서 안의 파일을 저장하는 형식
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
  ['지정 번호', 'file_no'], // 시도교육청처럼 번호가 정해진 문서(19-2 등). 비어 있으면 폴더 번호 다음 값을 쓴다
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

/**
 * zip 안의 파일 이름 목록에서 저장할 것을 고른다. 폴더·이미지 등 저장하지 않는 형식은 빼고,
 * 같은 문서가 여러 형식이면 pdf > hwpx > hwp > odt > xlsx > xls 순으로 하나만 남긴다.
 * label은 파일명의 '구분' 칸에 쓸 원래 이름(20자). 인코딩이 깨진 이름이면 빈 문자열
 */
function zipEntries(names) {
  var order = INDEXED_EXT.concat(CONVERT_EXT, STORE_EXT);
  var best = {}, stems = [];
  names.forEach(function (full, i) {
    full = String(full || '');
    if (/\/$/.test(full)) return;
    var base = full.split('/').pop();
    var ext = extOf(base);
    if (order.indexOf(ext) < 0) return;
    var stem = base.replace(/\.[^.]+$/, '');
    var key = stem.toLowerCase();
    if (!(key in best)) stems.push(key);
    else if (order.indexOf(ext) >= order.indexOf(best[key].ext)) return;
    var readable = !/[\uFFFD\u0080-\u00B6\u00B8-\u00FF]/.test(stem); // 가운뎃점(·)은 허용
    best[key] = { index: i, ext: ext, label: readable ? cleanPart(stem).slice(0, 20).trim() : '' };
  });
  return stems.map(function (k) { return best[k]; });
}

/**
 * 지정 번호가 있는 행의 번호. 같은 글의 행이 시트에 여러 개면 시트 순서대로 -1, -2를 붙인다
 * (승인 시점이 달라도 번호가 바뀌지 않게 시트 전체를 기준으로 센다)
 */
function fixedNumber(fixed, rowIdx, sheetKeys) {
  var key = sheetKeys[rowIdx], siblings = [];
  sheetKeys.forEach(function (k, i) { if (k === key) siblings.push(i); });
  return siblings.length > 1 ? fixed + '-' + (siblings.indexOf(rowIdx) + 1) : String(fixed);
}

// ── 시트 ──────────────────────────────────────────────────────────────

function sheet_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(SHEET_NAME) || ss.insertSheet(SHEET_NAME);
  var head = COLUMNS.map(function (c) { return c[0]; });
  if (sh.getLastRow() === 0) {
    sh.appendRow(head);
    sh.setFrozenRows(1);
  } else if (sh.getRange(1, head.length).getValue() !== head[head.length - 1]) {
    sh.getRange(1, 1, 1, head.length).setValues([head]); // 코드에 새 열이 생기면 머리행을 맞춘다
  }
  return sh;
}

/** 마지막 데이터 행. 체크박스(FALSE)만 있는 빈 행은 세지 않고 '글 키' 열로 판단한다 */
function lastDataRow_(sh) {
  var last = sh.getLastRow();
  if (last < 2) return 1;
  var keys = sh.getRange(2, col_('글 키'), last - 1, 1).getValues();
  for (var i = keys.length - 1; i >= 0; i--) if (keys[i][0] !== '') return i + 2;
  return 1;
}

function col_(label) {
  for (var i = 0; i < COLUMNS.length; i++) if (COLUMNS[i][0] === label) return i + 1;
  throw new Error('열 없음: ' + label);
}

/** 처음 한 번 실행: 탭·머리행·매일 01시 트리거·TOKEN을 만든다. 다시 실행해도 된다 */
function setup() {
  var sh = sheet_();
  // 데이터가 없는 행의 승인 체크박스를 지운다(예전 setup이 빈 행 전체에 깔아 새 행이 1001행에 붙던 문제)
  var lastData = lastDataRow_(sh);
  if (sh.getMaxRows() > lastData) {
    sh.getRange(lastData + 1, col_('승인'), sh.getMaxRows() - lastData, 1).clearDataValidations().clearContent();
  }
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

/** 시트에 있는 글 키 목록(중복 제거) */
function postKeys_() {
  var sh = sheet_();
  var last = lastDataRow_(sh);
  if (last < 2) return [];
  var seen = {};
  sh.getRange(2, col_('글 키'), last - 1, 1).getValues().forEach(function (r) { if (r[0]) seen[r[0]] = true; });
  return Object.keys(seen);
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
  if (body.action === 'keys') return json_({ ok: true, keys: postKeys_() });

  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var sh = sheet_();
    var last = lastDataRow_(sh);
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
      var start = lastDataRow_(sh) + 1;
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
  var last = lastDataRow_(sh);
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

  // 지정 번호가 없는 행만 폴더 번호 다음 값부터 묶어서 번호를 준다
  var sheetKeys = data.map(function (row) { return row[c('글 키')]; });
  var free = todo.filter(function (i) { return !String(data[i][c('지정 번호')]).trim(); });
  var freeNumbers = assignNumbers(free.map(function (i) { return sheetKeys[i]; }), nextGroupNumber(existing));
  var numbers = todo.map(function (i) {
    var fixed = String(data[i][c('지정 번호')]).trim();
    return fixed ? fixedNumber(fixed, i, sheetKeys) : freeNumbers[free.indexOf(i)];
  });

  todo.forEach(function (i, n) {
    var row = data[i], r = i + 2;
    var setStatus = function (s) { sh.getRange(r, col_('상태')).setValue(s); };
    try {
      var ext = extOf(row[c('첨부 이름')]) || extOf(row[c('첨부 URL')]);
      var known = INDEXED_EXT.concat(CONVERT_EXT, STORE_EXT, UNZIP_EXT);
      if (known.indexOf(ext) < 0) { setStatus('실패: 저장하지 않는 형식(' + (ext || '알 수 없음') + ')'); return; }
      var res = UrlFetchApp.fetch(String(row[c('첨부 URL')]), { muteHttpExceptions: true, followRedirects: true });
      if (res.getResponseCode() !== 200) { setStatus('실패: 다운로드 HTTP ' + res.getResponseCode()); return; }
      var blob = res.getBlob();
      var bytes = blob.getBytes().length;
      if (bytes < 1024) { setStatus('실패: 파일이 너무 작음(' + bytes + 'B, 오류 페이지일 수 있음)'); return; }

      // 저장할 조각: 보통은 받은 파일 하나, zip이면 안의 파일들
      var parts = [{ blob: blob, ext: ext, label: '' }];
      if (UNZIP_EXT.indexOf(ext) >= 0) {
        var inner = Utilities.unzip(blob.setContentType('application/zip'));
        parts = zipEntries(inner.map(function (b) { return b.getName(); })).map(function (e) {
          return { blob: inner[e.index], ext: e.ext, label: e.label };
        });
        if (!parts.length) { setStatus('실패: 압축 안에 저장할 파일 없음'); return; }
      }

      // 이름을 먼저 모두 정하고 겹치는지 본 뒤에 저장한다(일부만 저장되고 실패하는 일을 막는다)
      var names = parts.map(function (part, j) {
        var number = parts.length > 1 ? numbers[n] + '-' + (j + 1) : numbers[n];
        var kind = [row[c('구분')], part.label || (parts.length > 1 ? '파일' + (j + 1) : '')]
          .filter(function (x) { return x; }).join(' ');
        return buildName(number, String(row[c('분류')]), row[c('기관')], row[c('문서명')], row[c('연도')],
                         CONVERT_EXT.indexOf(part.ext) >= 0 ? 'pdf' : part.ext, kind);
      });
      var dup = names.filter(function (x, k) { return existing.indexOf(x) >= 0 || names.indexOf(x) !== k; });
      if (dup.length) { setStatus('실패: 같은 이름 있음(' + dup[0] + ')'); return; }

      var links = [], notes = [];
      parts.forEach(function (part, j) {
        var convert = CONVERT_EXT.indexOf(part.ext) >= 0;
        var name = names[j];
        var out = convert ? convertToPdf_(part.blob, name) : part.blob;
        var file = folder.createFile(out.setName(name));
        existing.push(name);
        links.push(file.getUrl());
        if (convert) notes.push(part.ext + '→pdf 변환');
        if (STORE_EXT.indexOf(part.ext) >= 0) notes.push(part.ext + ' 원본 저장, 색인 안 됨');
      });
      if (parts.length > 1 || UNZIP_EXT.indexOf(ext) >= 0) notes.unshift('압축 풀어 ' + parts.length + '개');
      sh.getRange(r, col_('파일명')).setValue(names.join('\n'));
      sh.getRange(r, col_('드라이브 링크')).setValue(links.join('\n'));
      setStatus('전송 완료 ' + Utilities.formatDate(new Date(), 'Asia/Seoul', 'yyyy-MM-dd HH:mm') +
                (notes.length ? ' (' + notes.filter(function (x, k) { return notes.indexOf(x) === k; }).join(', ') + ')' : ''));
    } catch (err) {
      setStatus('실패: ' + String(err.message || err).slice(0, 200));
    }
  });
}

/**
 * odt 등을 구글 문서로 올려 변환한 뒤 PDF로 내보낸다. 임시 문서는 휴지통으로 보낸다.
 * 한글 프로그램에서 내보낸 odt는 구글 문서로 변환하면 모든 글자에 취소선이 붙는다.
 * 보도자료에 실제 취소선이 쓰일 일은 거의 없으므로 변환된 문서의 취소선을 모두 지운다
 */
function convertToPdf_(blob, name) {
  if (typeof Drive === 'undefined') throw new Error('편집기 "서비스 +"에서 Drive API를 추가해야 odt를 변환할 수 있습니다');
  var tmp = Drive.Files.create
    ? Drive.Files.create({ name: 'policy-harvest 변환 중 ' + name, mimeType: MimeType.GOOGLE_DOCS }, blob)   // Drive API v3
    : Drive.Files.insert({ title: 'policy-harvest 변환 중 ' + name, mimeType: MimeType.GOOGLE_DOCS }, blob, { convert: true }); // v2
  try {
    var doc = DocumentApp.openById(tmp.id);
    [doc.getBody(), doc.getHeader(), doc.getFooter()].forEach(function (section) {
      if (!section) return;
      var text = section.editAsText();
      if (text.getText().length) text.setStrikethrough(false);
    });
    doc.saveAndClose();
    return DriveApp.getFileById(tmp.id).getAs(MimeType.PDF);
  } finally {
    DriveApp.getFileById(tmp.id).setTrashed(true);
  }
}

/** 수동 점검: 폴더 파일명 중 규칙과 다른 것을 로그로 남긴다 */
function checkFolderNames() {
  var it = DriveApp.getFolderById(FOLDER_ID).getFiles();
  while (it.hasNext()) {
    var n = it.next().getName();
    var parts = n.replace(/\.[^.]+$/, '').split('_');
    var ok = /^\d+(-\d+)*$/.test(parts[0]) && CATEGORIES.indexOf(parts[1]) >= 0 &&
             /^(19|20)\d{2}$/.test(parts[parts.length - 1]) && INDEXED_EXT.concat(STORE_EXT).indexOf(extOf(n)) >= 0;
    if (!ok) Logger.log('규칙과 다름: ' + n);
    else if (STORE_EXT.indexOf(extOf(n)) >= 0) Logger.log('색인 안 되는 형식(원본 보관): ' + n);
  }
}
