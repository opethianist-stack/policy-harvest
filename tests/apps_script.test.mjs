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
