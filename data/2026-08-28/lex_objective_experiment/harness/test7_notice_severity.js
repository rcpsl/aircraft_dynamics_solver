// Pull notice() straight out of the dashboard and exercise the three banner states
// with the solver's REAL message text, so the severity rule and the summary split are
// tested against what the server actually sends rather than a paraphrase.
const fs = require('fs');
const html = fs.readFileSync(
  'd:/Documents/EECS_199_Shoukry/5x5_realtime_solver/uam-dashboard-NEXT-5x5_v2.html', 'utf8');

const m = html.match(/function notice\(cls, text\)\{[\s\S]*?\n\}/);
if (!m) { console.error('FAIL: could not find notice() in the dashboard'); process.exit(1); }
eval(m[0]);

// The severity rule, copied verbatim from renderSide.
const warnClassFor = res => res.principleImposed === true ? 'solveinfo' : 'solvewarn';

const CASES = [
  { name: 'phase 2 failed, principle DROPPED (Utilitarian)',
    res: { principleImposed: false,
           warning: 'This routing does NOT apply the Utilitarian objective (total noise, weighted by population). Phase-2 optimization failed, so the map shows a plain feasible route that ignores it. It ran out of time after 5s at T=5 without reaching any solution at all; the route shown is phase 1\u2019s at T=5. Raise the time limit in Admin, or tighten D/U, lower T_max, reduce the station weight, or reduce N/aircraft multipliers.' },
    wantClass: 'solvewarn' },

  { name: 'phase 2 failed, NOTHING dropped (Equal)',
    res: { principleImposed: true,
           warning: 'Your noise limit is still enforced, but arrival times were not optimized. No fairness objective was active \u2014 this rule is the hard D/U cap, which phase 1 applied \u2014 so the routing below is valid. It ran out of time after 5s at T=5 without reaching any solution at all; the route shown is phase 1\u2019s at T=5.' },
    wantClass: 'solveinfo' },

  { name: 'partial: objective applied, not proven best',
    res: { principleImposed: true,
           notice: 'This routing DOES apply the Utilitarian objective (total noise, weighted by population), but it is the best found within 60s rather than a proven best. A longer time limit in Admin may turn up a slightly better one; the noise limits are exact either way.' },
    wantClass: 'solveinfo' },

  { name: 'stale cache entry: flag absent, must stay AMBER',
    res: { warning: 'This routing does NOT reflect your fairness choices. Phase-2 optimization ran out of time.' },
    wantClass: 'solvewarn' },

  { name: 'clean solve: no banner at all',
    res: { principleImposed: true, optimality: 'optimal' },
    wantClass: 'solveinfo' },
];

let bad = 0;
for (const c of CASES) {
  const cls = warnClassFor(c.res);
  const warnHtml = notice(cls, c.res.warning);
  const noticeHtml = notice('solveinfo', c.res.notice);
  const html = warnHtml + noticeHtml;

  const problems = [];
  if (c.res.warning && cls !== c.wantClass) problems.push(`class ${cls}, wanted ${c.wantClass}`);
  if (!c.res.warning && !c.res.notice && html.trim() !== '') problems.push('rendered a banner with nothing to say');
  if ((c.res.warning || c.res.notice) && html.trim() === '') problems.push('rendered nothing');

  // The summary must carry the news on its own: someone who never clicks "more"
  // still has to learn whether the map answers their question.
  const sum = /<summary>([\s\S]*?)<\/summary>/.exec(html);
  if (sum) {
    const s = sum[1];
    const carries = /does NOT apply|still enforced|DOES apply|does NOT reflect/.test(s);
    if (!carries) problems.push(`summary buries the news: "${s.slice(0, 70)}"`);
    if (s.length > 160) problems.push(`summary too long (${s.length})`);
  }

  if (problems.length) { bad++; console.log(`FAIL  ${c.name}\n      ${problems.join('\n      ')}`); }
  else {
    console.log(`ok    ${c.name}  [${c.res.warning || c.res.notice ? cls : 'no banner'}]`);
    if (sum) console.log(`        summary: ${sum[1]}`);
  }
}
console.log(bad ? `\n${bad} FAILED` : '\nall passed');
process.exit(bad ? 1 : 0);
