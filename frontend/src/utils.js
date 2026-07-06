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

export function computeTransitTime(path, endStation) {
  let firstMove = -1, firstArrival = -1;
  for (let t = 1; t < path.length; t++)
    if (firstMove === -1 && path[t] !== path[t-1]) firstMove = t;
  for (let t = 0; t < path.length; t++)
    if (path[t] === endStation) { firstArrival = t; break; }
  if (firstMove === -1 || firstArrival === -1 || firstMove > firstArrival) return 0;
  return firstArrival - firstMove + 1;
}
