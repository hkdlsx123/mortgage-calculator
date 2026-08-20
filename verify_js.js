// 提取 index.html 中的核心 JS 函数并在 node 中运行，验证 JS 与 Python 结果一致
const fs = require('fs');
const html = fs.readFileSync('index.html', 'utf8');

// 提取 <script> 中从 "use strict" 到 window 事件绑定之前的核心函数部分
const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/);
if (!scriptMatch) { console.error('NO SCRIPT FOUND'); process.exit(1); }
const script = scriptMatch[1];

// 只提取核心计算部分：从 'use strict' 到 '/* ---------- 读写 UI' 之前
// 这部分包含 annuityPmt, round2, recomputeMonths, simulateLoan 等纯函数
const coreStart = script.indexOf('"use strict"');
const coreEnd = script.indexOf('/* ---------- 读写 UI');
if (coreStart < 0 || coreEnd < 0) { console.error('CORE SECTION NOT FOUND', coreStart, coreEnd); process.exit(1); }
const core = script.slice(coreStart, coreEnd);

// 在 node 中执行核心函数（Function 构造器使函数进入全局作用域）
const makeCore = new Function(core + '\nreturn { annuityPmt, round2, recomputeMonths, simulateLoan };');
const { annuityPmt, round2, recomputeMonths, simulateLoan } = makeCore();

// ---- 测试用例 ----
function fmt(x) { return x.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }

const tests = [];
// 场景1: 商贷 515500@3.2% 等额本息213期
tests.push({
  name: '场景1 商贷等额本息',
  opts: { amount: 515500, rate: 0.032, months: 213, method: 'annuity', prepays: [], rateAdjs: [] },
  expect: { months: 213, firstMonth: 3175.38, totalInterest: 160856.43 }
});
// 场景2: 公积金 700000@2.6% 等额本金240期
tests.push({
  name: '场景2 公积金等额本金',
  opts: { amount: 700000, rate: 0.026, months: 240, method: 'equal', prepays: [], rateAdjs: [] },
  expect: { months: 240, firstMonth: 4433.34, totalInterest: null }
});
// 场景3: 提前还款缩期 第36期还5万
tests.push({
  name: '场景3 缩期',
  opts: { amount: 515500, rate: 0.032, months: 213, method: 'annuity',
          prepays: [{ m: 36, amount: 50000, mode: 'shorten' }], rateAdjs: [] },
  expect: { months: 189, totalInterest: 133224.26 }
});
// 场景3b: 提前还款减月供
tests.push({
  name: '场景3b 减月供',
  opts: { amount: 515500, rate: 0.032, months: 213, method: 'annuity',
          prepays: [{ m: 36, amount: 50000, mode: 'reduce' }], rateAdjs: [] },
  expect: { months: 213, totalInterest: 148065.78 }
});
// 场景4: 利率调整 第13期起3.0%
tests.push({
  name: '场景4 利率调整',
  opts: { amount: 515500, rate: 0.032, months: 213, method: 'annuity',
          prepays: [], rateAdjs: [{ m: 13, rate: 0.03 }] },
  expect: { months: 213, totalInterest: 150413.66 }
});
// 场景6: 组合场景
tests.push({
  name: '场景6 多次提前还款+利率调整',
  opts: { amount: 515500, rate: 0.032, months: 213, method: 'annuity',
          prepays: [{ m: 36, amount: 50000, mode: 'shorten' }, { m: 60, amount: 30000, mode: 'reduce' }],
          rateAdjs: [{ m: 13, rate: 0.03 }] },
  expect: { months: 188, totalInterest: 119944.11 }
});

let pass = 0, fail = 0;
for (const t of tests) {
  const r = simulateLoan(t.opts);
  const c = t.expect;
  let ok = r.months === c.months;
  const details = [`期数:${r.months} (期望${c.months})`];
  if (c.firstMonth !== null && c.firstMonth !== undefined) {
    const fm = Math.round((r.firstMonth) * 100) / 100;
    ok = ok && Math.abs(fm - c.firstMonth) < 0.01;
    details.push(`首月:${fmt(fm)} (期望${fmt(c.firstMonth)})`);
  }
  if (c.totalInterest !== null && c.totalInterest !== undefined) {
    const ti = Math.round(r.totalInterest * 100) / 100;
    ok = ok && Math.abs(ti - c.totalInterest) < 0.01;
    details.push(`总利息:${fmt(ti)} (期望${fmt(c.totalInterest)})`);
  }
  details.push(`提前还:${fmt(r.totalPrepay)}`);
  console.log(`${ok ? '✅' : '❌'} ${t.name}: ${details.join(' | ')}`);
  ok ? pass++ : fail++;
}
console.log(`\nJS 结果: ${pass} 通过, ${fail} 失败 (与 Python 交叉验证一致 = ${pass === tests.length})`);
process.exit(fail ? 1 : 0);
