// Pull the pure payload-building functions straight out of the dashboard HTML and
// run the REAL buildSolveRequest, so payload.py is validated against the shipped
// code rather than against a reading of it.
//
// Everything needed is pure (no DOM): the constants block, COMMUNITIES, ADMIN,
// SOLVER, the proportional model, buildStreams, chebyshevTLower, whoFor, slackFor
// and buildSolveRequest itself. We slice the <script> body from the first `const
// BANDS` to the end of slackFor and eval it.
const fs = require('fs');
const path = require('path');

const HTML = fs.readFileSync(
  path.join(__dirname, '..', '..', '5x5_realtime_solver', 'uam-dashboard-NEXT-5x5_v2.html'),
  'utf8');

const startMark = 'const BANDS = {45:';
const endMark = 'function slackFor(conf){';
const i = HTML.indexOf(startMark);
if (i < 0) throw new Error('start marker not found');
let j = HTML.indexOf(endMark, i);
if (j < 0) throw new Error('end marker not found');
// include slackFor's whole body
j = HTML.indexOf('\n}', j) + 2;

let src = HTML.slice(i, j);

// pathLen/energyAdd/computeChanges pull in helpers we do not need and that touch
// other globals; buildSolveRequest does not call them, so drop the one function in
// the slice that does (`function communityChanges`/`pathLen` region) only if it
// fails to parse. Simplest robust approach: strip functions we know are unused and
// that reference undefined globals.
for (const fn of ['function communityChanges', 'function exposureFor']) {
  const a = src.indexOf(fn);
  if (a >= 0) {
    const b = src.indexOf('\n}', a) + 2;
    src = src.slice(0, a) + src.slice(b);
  }
}

const sandbox = {};
const runner = new Function('exports', src + '\n; return {buildSolveRequest, buildStreams, chebyshevTLower, whoFor, slackFor, proportionalModel, buildAdjacency, COMMUNITIES, ADMIN, SOLVER, POPW, propFactorScores};');
let api;
try {
  api = runner(sandbox);
} catch (e) {
  console.error('EVAL FAILED:', e.message);
  process.exit(2);
}

const configs = [
  {principle:'equal',           limit:10, who:'communities', protected:[]},
  {principle:'equal',           limit:5,  who:'people',      protected:[]},
  {principle:'sufficientarian', limit:10, who:'communities', protected:[]},
  {principle:'sufficientarian', limit:5,  who:'people',      protected:[]},
  {principle:'prioritarian',    limit:10, who:'communities', protected:[15,19,24]},
  {principle:'prioritarian',    limit:10, who:'people',      protected:[15,19,24]},
  {principle:'utilitarian',     limit:10, who:'communities', protected:[]},
  {principle:'utilitarian',     limit:10, who:'people',      protected:[]},
  {principle:'proportional',    limit:10, who:'communities', protected:[],
   propOrder:['income','ambient','distance','population'], propPopulation:true},
  {principle:'proportional',    limit:10, who:'communities', protected:[],
   propOrder:['distance','population','income','ambient'], propPopulation:false},
];

const out = {};
for (const c of configs) {
  const conf = Object.assign({propOrder:['income','ambient','distance','population'],
                              propPopulation:true, pattern:'average'}, c);
  const key = `${c.principle}|${c.who}|${c.limit}|${(c.propOrder||[]).join('-')}|${c.propPopulation!==false}`;
  out[key] = api.buildSolveRequest(conf, 1);
}
fs.writeFileSync(path.join(__dirname, 'js_payloads.json'), JSON.stringify(out, null, 1));
console.log('wrote', Object.keys(out).length, 'payloads');
