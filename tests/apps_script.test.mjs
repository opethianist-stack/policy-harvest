// apps-script/Code.gs 의 순수 함수 시험(node --test)
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const ctx = {};
vm.createContext(ctx);
vm.runInContext(readFileSync(new URL('../apps-script/Code.gs', import.meta.url), 'utf8'), ctx);

test('buildName matches the Policy Fit rule', () => {
  assert.equal(
    ctx.buildName('19-12-1', '교육청', '충청남도교육청', '충남교육 주요업무계획', 2026, 'PDF', ''),
    '19-12-1_교육청_충청남도교육청_충남교육 주요업무계획_2026.pdf');
  assert.equal(
    ctx.buildName('20', '부처', '교육부', 'AI_인재/방안', '2026', 'hwpx', '보도'),
    '20_부처_교육부_AI 인재 방안_보도_2026.hwpx');
  assert.throws(() => ctx.buildName('20', '기관', 'NIA', 'x', '2026', 'pdf'));
  assert.throws(() => ctx.buildName('20', '공공기관', 'NIA', '', '2026', 'pdf'));
  assert.throws(() => ctx.buildName('20', '공공기관', 'NIA', 'x', '26', 'pdf'));
});

test('extOf ignores query strings', () => {
  assert.equal(ctx.extOf('계획.HWPX'), 'hwpx');
  assert.equal(ctx.extOf('https://x.kr/a/plan.pdf?x=1'), 'pdf');
  assert.equal(ctx.extOf('https://x.kr/fileDown.do?id=1'), 'do');
  assert.equal(ctx.extOf(''), '');
});

test('nextGroupNumber reads leading numbers only', () => {
  assert.equal(ctx.nextGroupNumber(['01_a', '18-2_b', '19-12-1_c', '_test.txt']), 20);
  assert.equal(ctx.nextGroupNumber([]), 1);
});

test('assignNumbers groups rows of the same post', () => {
  assert.deepEqual(
    Array.from(ctx.assignNumbers(['A', 'B', 'A', 'C'], 20)),
    ['20-1', '21', '20-2', '22']);
});

test('lastDataRow_ ignores checkbox-only rows', () => {
  // 1행 머리, 2~3행 데이터, 4~1000행은 체크박스(FALSE)만 있는 빈 행, 1001행 데이터
  const keyCol = ctx.col_('글 키');
  const rows = { 2: 'A', 3: 'B', 1001: 'C' };
  const fake = (last) => ({
    getLastRow: () => last,
    getRange: (r, c, n) => {
      assert.equal(c, keyCol);
      return { getValues: () => Array.from({ length: n }, (_, i) => [rows[r + i] ?? '']) };
    },
  });
  assert.equal(ctx.lastDataRow_(fake(1001)), 1001);
  delete rows[1001];
  assert.equal(ctx.lastDataRow_(fake(1000)), 3);
  assert.equal(ctx.lastDataRow_(fake(1)), 1);
});

test('zipEntries keeps storable files, one format per document', () => {
  const got = Array.from(ctx.zipEntries([
    '시행계획/', '시행계획/붙임1 시행계획(최종).hwpx', '시행계획/붙임1 시행계획(최종).pdf',
    '표지.jpg', '통계표.xlsx', '보도자료.odt', '업무계획·예산.hwp', 'Ç¥Áö.hwp', 'nested.zip',
  ])).map(e => [e.index, e.ext, e.label]);
  assert.deepEqual(got, [
    [2, 'pdf', '붙임1 시행계획(최종)'], [4, 'xlsx', '통계표'], [5, 'odt', '보도자료'],
    [6, 'hwp', '업무계획·예산'], [7, 'hwp', ''],
  ]);
});

test('fixedNumber adds sub-numbers only when a post has several rows', () => {
  const keys = ['PEN:plan:2026', 'CBE:plan:2026', 'MSIT:press:1', 'CBE:plan:2026'];
  assert.equal(ctx.fixedNumber('19-2', 0, keys), '19-2');
  assert.equal(ctx.fixedNumber('19-11', 1, keys), '19-11-1');
  assert.equal(ctx.fixedNumber('19-11', 3, keys), '19-11-2');
});

test('blobOf_ tolerates malformed content types', () => {
  ctx.Utilities = { newBlob: (bytes, type, name) => ({ bytes, type, name }) };
  const res = (h) => ({ getHeaders: () => h, getContent: () => [1, 2] });
  assert.equal(ctx.blobOf_(res({ 'Content-Type': 'application-download' }), 'hwp').type, 'application/octet-stream');
  assert.equal(ctx.blobOf_(res({ 'content-type': 'application/haansofthwp; charset=UTF-8' }), 'hwp').type, 'application/haansofthwp');
  assert.equal(ctx.blobOf_(res({ 'Content-Type': 'application-download' }), 'pdf').type, 'application/pdf');
  assert.equal(ctx.blobOf_(res({}), 'odt').type, 'application/vnd.oasis.opendocument.text');
});
