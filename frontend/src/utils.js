export function combinedDb(rawDb, nTotal, dbPerCraft) {
  if (nTotal === 0) return rawDb;
  const ambientPower  = Math.pow(10, rawDb / 10);
  const aircraftPower = nTotal * Math.pow(10, dbPerCraft / 10);
  return 10 * Math.log10(ambientPower + aircraftPower);
}

export function resizeAdj(adj, newM) {
  return Array.from({ length: newM }, (_, i) =>
    Array.from({ length: newM }, (_, j) => {
      if (i < adj.length && j < adj[i].length) return adj[i][j];
      return (j === i || j === i + 1) ? 1 : 0;
    })
  );
}

export function resizePos(pos, newN) {
  if (newN <= pos.length) return pos.slice(0, newN);
  return [...pos, ...Array.from({ length: newN - pos.length }, () => 1)];
}

export function aircraftColor(val, maxVal) {
  if (maxVal === 0) return "#f8f6f2";
  const t = val / maxVal;
  return `rgb(${Math.round(248 + t*(30-248))},${Math.round(246 + t*(64-246))},${Math.round(242 + t*(175-242))})`;
}

export function noiseColor(deltaDB) {
  const t = Math.max(0, Math.min(1, deltaDB / 15));
  return `rgb(${Math.round(248 + t*(153-248))},${Math.round(246 + t*(27-246))},${Math.round(242 + t*(27-242))})`;
}

// Encodes solved-state config into a short, filesystem-safe label for Save Results:
// N/M plus abbreviated fairness principles inferred from which constraints/objectives
// were actually in play. D/U below their slider max signal a tightened constraint
// (sufficientarian cap, equal-allocation disparity limit) even though the solver has
// no separate "principle" flag for them.
export function buildResultLabel({ N, M, D, U, optimizeUtil, optimizePrior, proportionalAlloc, useDbSolver }) {
  const dMax = useDbSolver ? 90 : 10;
  const uMax = useDbSolver ? 50 : 10;
  const principles = [];
  if (D != null && D < dMax) principles.push("Suff");
  if (U != null && U < uMax) principles.push("Eq");
  if (optimizeUtil)          principles.push("Util");
  if (optimizePrior)         principles.push("Prior");
  if (proportionalAlloc)     principles.push("PropAlloc");
  const tag = principles.length ? principles.join("+") : "Base";
  return `N${N ?? "?"}-M${M ?? "?"}-${tag}`;
}

export function sanitizeFilename(name) {
  return name.trim().replace(/[^A-Za-z0-9-_+]+/g, "_").slice(0, 80) || "uam-results";
}

// Per-station noise/aircraft summary for CSV export — one row per station, labeled
// "Zone" per the dashboard's terminology (each station is treated as its own zone).
// Uses the same level formula as NoiseMatrix.jsx so the CSV matches what's shown on screen.
export function buildZoneSummaryCSV({ T, M, stationBaselines, dbPerCraft, isDbMode, noiseMatrix, countMatrix }) {
  const aircraftMatrix = countMatrix ?? noiseMatrix;

  const avg = arr => arr.reduce((a, b) => a + b, 0) / arr.length;
  const peak = arr => Math.max(...arr);

  const header = [
    "Zone", "Avg Added dB", "Avg Total dB", "Peak Added dB", "Peak Total dB",
    "Avg Aircraft", "Peak Aircraft",
  ];
  const rows = [];
  for (let m = 0; m < M; m++) {
    const baseline = stationBaselines[m];
    const noiseRow = noiseMatrix[m], countRow = aircraftMatrix[m];
    const addedDb = [], totalDb = [];
    for (let t = 0; t < noiseRow.length; t++) {
      const level = isDbMode ? baseline + noiseRow[t] : combinedDb(baseline, noiseRow[t], dbPerCraft);
      addedDb.push(level - baseline);
      totalDb.push(level);
    }
    rows.push([
      `Zone ${m + 1}`,
      avg(addedDb).toFixed(2), avg(totalDb).toFixed(2),
      peak(addedDb).toFixed(2), peak(totalDb).toFixed(2),
      avg(countRow).toFixed(2), peak(countRow),
    ]);
  }

  return `Time Steps (T),${T}\n\n` + [header, ...rows].map(r => r.join(",")).join("\n");
}

export function computeTransitTime(path, endStation) {
  let firstMove = -1, firstArrival = -1;
  for (let t = 1; t < path.length; t++)
    if (firstMove === -1 && path[t] !== path[t-1]) firstMove = t;
  for (let t = 0; t < path.length; t++)
    if (path[t] === endStation) { firstArrival = t; break; }
  if (firstMove === -1 || firstArrival === -1 || firstMove > firstArrival) return 0;
  return firstArrival - firstMove + 1;
}
