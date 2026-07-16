import { useState, useEffect, useRef } from 'react';
import {
  DEFAULT_N, DEFAULT_M, DEFAULT_D, DEFAULT_U,
  DEFAULT_ADJ, DEFAULT_START, DEFAULT_END, DEFAULT_ZONES,
  DEFAULT_DB_PER_CRAFT, STORAGE_KEY, RESULTS_STORAGE_KEY, BENEFIT_ZONE_IDS, PROTECTED_ZONE_IDS, ZONES, CUSTOM_ZONE_ID,
} from '../constants';
import { resizeAdj, resizePos, buildResultLabel, sanitizeFilename } from '../utils';

function loadSaved() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {}; }
  catch { return {}; }
}

function loadSavedResults() {
  try { return JSON.parse(localStorage.getItem(RESULTS_STORAGE_KEY)) || {}; }
  catch { return {}; }
}

export function useSolver() {
  const saved = loadSaved();
  const savedResults = loadSavedResults();

  const [N,            setN]            = useState(saved.N            ?? DEFAULT_N);
  const [M,            setM]            = useState(saved.M            ?? DEFAULT_M);
  const [D,            setD]            = useState(saved.D            ?? DEFAULT_D);
  const [U,            setU]            = useState(saved.U            ?? DEFAULT_U);
  const [adjacency,    setAdjacency]    = useState(saved.adjacency    ?? DEFAULT_ADJ);
  const [startPos,     setStartPos]     = useState(saved.startPos     ?? DEFAULT_START);
  const [endPos,       setEndPos]       = useState(saved.endPos       ?? DEFAULT_END);
  const [stationZones, setStationZones] = useState(
    (saved.stationZones ?? DEFAULT_ZONES).map(z => (z === CUSTOM_ZONE_ID || (z >= 1 && z <= ZONES.length)) ? z : 1)
  );
  const [stationBaselines, setStationBaselines] = useState(() => {
    const zones = (saved.stationZones ?? DEFAULT_ZONES).map(z => (z === CUSTOM_ZONE_ID || (z >= 1 && z <= ZONES.length)) ? z : 1);
    return Array.isArray(saved.stationBaselines) && saved.stationBaselines.length === zones.length
      ? saved.stationBaselines
      : zones.map(z => z === CUSTOM_ZONE_ID ? ZONES[0].dba : ZONES[z - 1].dba);
  });
  const [dbPerCraft,   setDbPerCraft]   = useState(saved.dbPerCraft   ?? DEFAULT_DB_PER_CRAFT);
  const [protectedStn,     setProtectedStn]     = useState(saved.protectedStn     ?? []);
  const [proportionalStn,  setProportionalStn]  = useState(saved.proportionalStn  ?? []);
  const [weightUtil,       setWeightUtil]       = useState(saved.weightUtil       ?? 1.0);
  const [weightPrior,      setWeightPrior]      = useState(saved.weightPrior      ?? 1.0);
  const [weightProp,       setWeightProp]       = useState(saved.weightProp       ?? 1.0);
  const [hardT,            setHardT]            = useState(saved.hardT            ?? true);
  const [tMax,             setTMax]             = useState(saved.tMax             ?? null);
  const [weightTime,       setWeightTime]       = useState(saved.weightTime       ?? 1.0);

  // Restoring a stale "solving" status on reload would show a spinner for a
  // request that no longer exists, so only sat/unsat carry over.
  const [status,            setStatus]            = useState(
    (savedResults.status === "sat" || savedResults.status === "unsat") ? savedResults.status : "idle"
  );
  const [solvedT,           setSolvedT]           = useState(savedResults.solvedT           ?? null);
  const [paths,             setPaths]             = useState(savedResults.paths             ?? null);
  const [noiseMatrix,       setNoiseMatrix]       = useState(savedResults.noiseMatrix       ?? null);
  const [countMatrix,       setCountMatrix]       = useState(savedResults.countMatrix       ?? null);
  const [unstatDetail,      setUnstatDetail]      = useState(savedResults.unstatDetail      ?? null);
  const [solvedStationZones,   setSolvedStationZones]   = useState(savedResults.solvedStationZones   ?? null);
  const [solvedStationBaselines, setSolvedStationBaselines] = useState(savedResults.solvedStationBaselines ?? null);
  const [solvedDbPerCraft,     setSolvedDbPerCraft]     = useState(savedResults.solvedDbPerCraft     ?? null);
  const [solvedM,              setSolvedM]              = useState(savedResults.solvedM              ?? null);
  const [solvedUseDbSolver,    setSolvedUseDbSolver]    = useState(savedResults.solvedUseDbSolver    ?? null);
  const [solvedD,              setSolvedD]              = useState(savedResults.solvedD              ?? null);
  const [solvedU,              setSolvedU]              = useState(savedResults.solvedU              ?? null);
  const [solvedProportionalAlloc, setSolvedProportionalAlloc] = useState(savedResults.solvedProportionalAlloc ?? null);
  const [protectedNoiseVal,    setProtectedNoiseVal]    = useState(savedResults.protectedNoiseVal    ?? null);
  const [solvedProtectedStn,   setSolvedProtectedStn]   = useState(savedResults.solvedProtectedStn   ?? null);
  const [proportionalNoiseVal, setProportionalNoiseVal] = useState(savedResults.proportionalNoiseVal ?? null);
  const [solvedProportionalStn,setSolvedProportionalStn]= useState(savedResults.solvedProportionalStn ?? null);
  const [warningMsg,           setWarningMsg]           = useState(savedResults.warningMsg           ?? null);
  const [errorDetail,          setErrorDetail]          = useState(null);
  const [solvedTMin,           setSolvedTMin]           = useState(savedResults.solvedTMin           ?? null);
  const [solvedTUsed,          setSolvedTUsed]          = useState(savedResults.solvedTUsed          ?? null);
  const [solvedOptimizeUtil,   setSolvedOptimizeUtil]   = useState(savedResults.solvedOptimizeUtil   ?? null);
  const [solvedOptimizePrior,  setSolvedOptimizePrior]  = useState(savedResults.solvedOptimizePrior  ?? null);
  const [solvedOptimizeProp,   setSolvedOptimizeProp]   = useState(savedResults.solvedOptimizeProp   ?? null);
  const [stationCategories,    setStationCategories]    = useState(savedResults.stationCategories    ?? null);
  const [totalUtilNoise,       setTotalUtilNoise]       = useState(savedResults.totalUtilNoise       ?? null);
  const [solvedEndPos,         setSolvedEndPos]         = useState(savedResults.solvedEndPos         ?? null);
  const [optimizeUtil,         setOptimizeUtil]         = useState(saved.optimizeUtil      ?? false);
  const [optimizePrior,        setOptimizePrior]        = useState(saved.optimizePrior     ?? false);
  const [optimizeProp,         setOptimizeProp]         = useState(saved.optimizeProp      ?? false);
  const [autoProportional,     setAutoProportional]     = useState(saved.autoProportional  ?? false);
  const [autoProtected,        setAutoProtected]        = useState(saved.autoProtected     ?? false);
  const [proportionalAlloc,    setProportionalAlloc]    = useState(saved.proportionalAlloc    ?? false);
  const [stationWeightedTransit, setStationWeightedTransit] = useState(saved.stationWeightedTransit ?? false);
  const [stationTransitWeights,  setStationTransitWeights]  = useState(() => {
    const initM = saved.M ?? DEFAULT_M;
    return Array.isArray(saved.stationTransitWeights) && saved.stationTransitWeights.length === initM
      ? saved.stationTransitWeights
      : Array(initM).fill(1.0);
  });
  const [aircraftMultipliers,    setAircraftMultipliers]    = useState(() => {
    const initN = saved.N ?? DEFAULT_N;
    return Array.isArray(saved.aircraftMultipliers) && saved.aircraftMultipliers.length === initN
      ? saved.aircraftMultipliers
      : Array(initN).fill(1.0);
  });
  const [utilNoiseMode,          setUtilNoiseMode]          = useState(saved.utilNoiseMode          ?? false);
  const [useRouteMode,           setUseRouteMode]           = useState(saved.useRouteMode            ?? false);
  const [routeVertiports,      setRouteVertiports]      = useState(saved.routeVertiports   ?? []);
  const [routeN,               setRouteN]               = useState(saved.routeN            ?? 1);
  const [useDbSolver,          setUseDbSolver]          = useState(saved.useDbSolver       ?? false);
  const [activeTab,         setActiveTab]         = useState("solver");
  const [resultName,        setResultName]        = useState("");
  const [pendingResultsImport, setPendingResultsImport] = useState(null);
  const fileInputRef = useRef(null);
  const resultsFileInputRef = useRef(null);
  const resultsWithConfigFileInputRef = useRef(null);
  const abortRef     = useRef(null);

  // Single source of truth for config save/load: [key, currentValue, setter] triples.
  // Both the save side (configValues, used by localStorage persistence and Save
  // Config) and the load side (handleImport) are derived from this one array, so a
  // field can never exist on one side and not the other. N and M are excluded here —
  // they cascade-resize other fields via handleN/handleM, so handleImport applies
  // them first and separately.
  const configFields = [
    ['D', D, setD], ['U', U, setU],
    ['adjacency', adjacency, setAdjacency],
    ['startPos', startPos, setStartPos],
    ['endPos', endPos, setEndPos],
    ['stationZones', stationZones, setStationZones],
    ['stationBaselines', stationBaselines, setStationBaselines],
    ['dbPerCraft', dbPerCraft, setDbPerCraft],
    ['protectedStn', protectedStn, setProtectedStn],
    ['proportionalStn', proportionalStn, setProportionalStn],
    ['weightUtil', weightUtil, setWeightUtil],
    ['weightPrior', weightPrior, setWeightPrior],
    ['weightProp', weightProp, setWeightProp],
    ['hardT', hardT, setHardT],
    ['tMax', tMax, setTMax],
    ['weightTime', weightTime, setWeightTime],
    ['optimizeUtil', optimizeUtil, setOptimizeUtil],
    ['optimizePrior', optimizePrior, setOptimizePrior],
    ['optimizeProp', optimizeProp, setOptimizeProp],
    ['autoProportional', autoProportional, setAutoProportional],
    ['autoProtected', autoProtected, setAutoProtected],
    ['proportionalAlloc', proportionalAlloc, setProportionalAlloc],
    ['stationWeightedTransit', stationWeightedTransit, setStationWeightedTransit],
    ['stationTransitWeights', stationTransitWeights, setStationTransitWeights],
    ['aircraftMultipliers', aircraftMultipliers, setAircraftMultipliers],
    ['utilNoiseMode', utilNoiseMode, setUtilNoiseMode],
    ['useRouteMode', useRouteMode, setUseRouteMode],
    ['routeVertiports', routeVertiports, setRouteVertiports],
    ['routeN', routeN, setRouteN],
    ['useDbSolver', useDbSolver, setUseDbSolver],
  ];

  const configValues = {
    N, M,
    ...Object.fromEntries(configFields.map(([key, value]) => [key, value])),
  };

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(configValues));
  });

  // Same [key, currentValue, setter] pattern as configFields, but for the solved
  // state the middle/right panel renders. Drives Save/Load Results (handleExportResults/
  // handleImportResults below) and is also the field list handleSolve's sat branch
  // uses to apply a fresh solve's snapshot to state in one loop.
  const resultFields = [
    ['status', status, setStatus],
    ['solvedT', solvedT, setSolvedT],
    ['paths', paths, setPaths],
    ['noiseMatrix', noiseMatrix, setNoiseMatrix],
    ['countMatrix', countMatrix, setCountMatrix],
    ['unstatDetail', unstatDetail, setUnstatDetail],
    ['solvedStationZones', solvedStationZones, setSolvedStationZones],
    ['solvedStationBaselines', solvedStationBaselines, setSolvedStationBaselines],
    ['solvedDbPerCraft', solvedDbPerCraft, setSolvedDbPerCraft],
    ['solvedM', solvedM, setSolvedM],
    ['solvedUseDbSolver', solvedUseDbSolver, setSolvedUseDbSolver],
    ['solvedD', solvedD, setSolvedD],
    ['solvedU', solvedU, setSolvedU],
    ['solvedProportionalAlloc', solvedProportionalAlloc, setSolvedProportionalAlloc],
    ['protectedNoiseVal', protectedNoiseVal, setProtectedNoiseVal],
    ['solvedProtectedStn', solvedProtectedStn, setSolvedProtectedStn],
    ['proportionalNoiseVal', proportionalNoiseVal, setProportionalNoiseVal],
    ['solvedProportionalStn', solvedProportionalStn, setSolvedProportionalStn],
    ['warningMsg', warningMsg, setWarningMsg],
    ['solvedTMin', solvedTMin, setSolvedTMin],
    ['solvedTUsed', solvedTUsed, setSolvedTUsed],
    ['solvedOptimizeUtil', solvedOptimizeUtil, setSolvedOptimizeUtil],
    ['solvedOptimizePrior', solvedOptimizePrior, setSolvedOptimizePrior],
    ['solvedOptimizeProp', solvedOptimizeProp, setSolvedOptimizeProp],
    ['stationCategories', stationCategories, setStationCategories],
    ['totalUtilNoise', totalUtilNoise, setTotalUtilNoise],
    ['solvedEndPos', solvedEndPos, setSolvedEndPos],
  ];

  const resultValues = Object.fromEntries(resultFields.map(([key, value]) => [key, value]));

  // Live preview only (shown as the name input's placeholder before a solve exists
  // to freeze values from) — handleExportResults recomputes this from the frozen
  // solved* fields so the saved name always matches what was actually solved.
  const defaultResultName = buildResultLabel({ N, M, D, U, optimizeUtil, optimizePrior, proportionalAlloc, useDbSolver });

  function handleN(newN) {
    setN(newN);
    setStartPos(p => resizePos(p, newN));
    setEndPos(p   => resizePos(p, newN));
    setAircraftMultipliers(m => newN <= m.length ? m.slice(0, newN) : [...m, ...Array(newN - m.length).fill(1.0)]);
  }

  function handleM(newM) {
    setM(newM);
    setAdjacency(a => resizeAdj(a, newM));
    setStartPos(p => p.map(v => Math.min(v, newM)));
    setEndPos(p   => p.map(v => Math.min(v, newM)));
    setStationZones(z => newM <= z.length ? z.slice(0, newM) : z.concat(Array.from({ length: newM - z.length }, () => 1)));
    setStationBaselines(b => newM <= b.length ? b.slice(0, newM) : b.concat(Array.from({ length: newM - b.length }, () => ZONES[0].dba)));
    setProtectedStn(ps => ps.filter(s => s <= newM));
    setProportionalStn(ps => ps.filter(s => s <= newM));
    setRouteVertiports(vs => vs.filter(s => s <= newM));
    setStationTransitWeights(w => newM <= w.length ? w.slice(0, newM) : [...w, ...Array(newM - w.length).fill(1.0)]);
  }

  // Changing a station's zone resets its baseline to that zone's default dBA
  // (picking "Custom" leaves the baseline as-is, since it has no preset default).
  // Editing the baseline number directly flips the zone to "Custom" — the value
  // no longer matches any preset, so the dropdown shouldn't claim it does.
  function updateStationZone(idx, zoneId) {
    setStationZones(z => z.map((v, i) => i === idx ? zoneId : v));
    if (zoneId !== CUSTOM_ZONE_ID) {
      setStationBaselines(b => b.map((v, i) => i === idx ? ZONES[zoneId - 1].dba : v));
    }
  }

  function updateStationBaseline(idx, raw) {
    const v = Number(raw);
    if (Number.isNaN(v)) return;
    setStationBaselines(b => b.map((x, i) => i === idx ? v : x));
    setStationZones(z => z.map((x, i) => i === idx ? CUSTOM_ZONE_ID : x));
  }

  function toggleAdj(i, j) {
    setAdjacency(prev => prev.map((row, ri) =>
      ri === i ? row.map((v, ci) => ci === j ? (v ? 0 : 1) : v) : row
    ));
  }

  function updateStartPos(idx, raw) {
    const v = Math.max(1, Math.min(M, Number(raw) || 1));
    setStartPos(prev => prev.map((x, i) => i === idx ? v : x));
  }

  function updateEndPos(idx, raw) {
    const v = Math.max(1, Math.min(M, Number(raw) || 1));
    setEndPos(prev => prev.map((x, i) => i === idx ? v : x));
  }

  function removeAircraft(idx) {
    if (N <= 1) return;
    setN(n => n - 1);
    setStartPos(p => p.filter((_, i) => i !== idx));
    setEndPos(p => p.filter((_, i) => i !== idx));
    setAircraftMultipliers(m => m.filter((_, i) => i !== idx));
  }

  function handleExport() {
    const blob = new Blob([JSON.stringify(configValues, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "uam-config.json"; a.click();
    URL.revokeObjectURL(url);
  }

  function handleImport(e) {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = ev => {
      try {
        const c = JSON.parse(ev.target.result);
        if (c.N !== undefined) handleN(c.N);
        if (c.M !== undefined) handleM(c.M);
        for (const [key, , setter] of configFields) {
          if (c[key] !== undefined) setter(c[key]);
        }
      } catch { alert("Invalid config file."); }
    };
    reader.readAsText(file);
    e.target.value = "";
  }

  // Results are wrapped in an envelope (distinct from the bare config JSON) so
  // Load Results can tell a config file was dropped in by mistake, and so the
  // config that produced a result travels with it for reference without being
  // silently applied to the live left-panel state.
  function handleExportResults() {
    // Named from the frozen solved* fields (not live config) so the name always
    // matches what was actually solved, even if the left panel has since changed.
    const name = resultName.trim() || buildResultLabel({
      N: paths ? paths.length : N,
      M: solvedM, D: solvedD, U: solvedU,
      optimizeUtil: solvedOptimizeUtil, optimizePrior: solvedOptimizePrior,
      proportionalAlloc: solvedProportionalAlloc, useDbSolver: solvedUseDbSolver,
    });
    const envelope = {
      kind: "uam-results", version: 1,
      name,
      savedAt: new Date().toISOString(),
      config: configValues,
      results: resultValues,
    };
    const blob = new Blob([JSON.stringify(envelope, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `${sanitizeFilename(name)}.json`; a.click();
    URL.revokeObjectURL(url);
  }

  function parseResultsEnvelope(ev) {
    const envelope = JSON.parse(ev.target.result);
    if (envelope.kind !== "uam-results" || !envelope.results) {
      alert("This doesn't look like a results file — try Load Config instead?");
      return null;
    }
    return envelope;
  }

  function applyResultsOnly(envelope) {
    for (const [key, , setter] of resultFields) {
      if (envelope.results[key] !== undefined) setter(envelope.results[key]);
    }
    if (envelope.name) setResultName(envelope.name);
    localStorage.setItem(RESULTS_STORAGE_KEY, JSON.stringify(envelope.results));
  }

  // Results-only load: doesn't touch the live left-panel config, so it's safe
  // to apply immediately without a confirmation step.
  function handleImportResults(e) {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = ev => {
      try {
        const envelope = parseResultsEnvelope(ev);
        if (envelope) applyResultsOnly(envelope);
      } catch { alert("Invalid results file."); }
    };
    reader.readAsText(file);
    e.target.value = "";
  }

  // Results + config load overwrites the live left-panel config, so it stages
  // the parsed envelope for read-only review — only confirmImportResults
  // actually writes it to state.
  function handleImportResultsWithConfig(e) {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = ev => {
      try {
        const envelope = parseResultsEnvelope(ev);
        if (envelope) setPendingResultsImport(envelope);
      } catch { alert("Invalid results file."); }
    };
    reader.readAsText(file);
    e.target.value = "";
  }

  function confirmImportResults() {
    if (!pendingResultsImport) return;
    const envelope = pendingResultsImport;
    const c = envelope.config || {};
    if (c.N !== undefined) handleN(c.N);
    if (c.M !== undefined) handleM(c.M);
    for (const [key, , setter] of configFields) {
      if (c[key] !== undefined) setter(c[key]);
    }
    applyResultsOnly(envelope);
    setPendingResultsImport(null);
  }

  function cancelImportResults() {
    setPendingResultsImport(null);
  }

  function handleCancel() {
    abortRef.current?.abort();
  }

  // Route-mode derived values — recomputed every render so handleSolve captures fresh values
  let effectiveN = N, effectiveStartPos = startPos, effectiveEndPos = endPos;
  if (useRouteMode && routeVertiports.length >= 2) {
    const starts = [], ends = [];
    for (const v1 of routeVertiports) {
      for (const v2 of routeVertiports) {
        if (v1 !== v2) {
          for (let k = 0; k < routeN; k++) { starts.push(v1); ends.push(v2); }
        }
      }
    }
    effectiveN = starts.length;
    effectiveStartPos = starts;
    effectiveEndPos = ends;
  }

  async function handleSolve() {
    abortRef.current = new AbortController();
    setStatus("solving");
    setPaths(null); setNoiseMatrix(null); setCountMatrix(null); setSolvedT(null);
    setSolvedStationZones(null); setSolvedStationBaselines(null); setSolvedDbPerCraft(null);
    setSolvedM(null); setSolvedUseDbSolver(null);
    setSolvedD(null); setSolvedU(null); setSolvedProportionalAlloc(null);
    setProtectedNoiseVal(null); setSolvedProtectedStn(null);
    setProportionalNoiseVal(null); setSolvedProportionalStn(null);
    setWarningMsg(null); setSolvedTMin(null); setSolvedTUsed(null); setErrorDetail(null);
    setSolvedOptimizeUtil(null); setSolvedOptimizePrior(null); setSolvedOptimizeProp(null);
    setStationCategories(null); setTotalUtilNoise(null); setSolvedEndPos(null);
    try {
      const res = await fetch(useDbSolver ? '/api/db/solve' : '/api/count/solve', {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: abortRef.current.signal,
        body: JSON.stringify({
          N: effectiveN, M, D, U, adjacency,
          startPositions:        effectiveStartPos,
          endPositions:          effectiveEndPos,
          optimizeUtilitarian:   optimizeUtil,
          optimizePrioritarian:  optimizePrior,
          optimizeProportional:  optimizeProp,
          protectedStations:     autoProtected
            ? stationZones.map((z, i) => PROTECTED_ZONE_IDS.includes(z) ? i + 1 : null).filter(Boolean)
            : protectedStn,
          proportionalStations:  autoProportional
            ? stationZones.map((z, i) => BENEFIT_ZONE_IDS.includes(z) ? i + 1 : null).filter(Boolean)
            : proportionalStn,
          weightUtilitarian:     weightUtil,
          weightPrioritarian:    weightPrior,
          weightProportional:    weightProp,
          hardT,
          ...(!hardT && tMax != null ? { T_max: tMax } : {}),
          ...(!hardT ? { weightTime } : {}),
          ...(useDbSolver ? {
            aircraftDB: dbPerCraft,
            baseline: stationBaselines,
            proportionalAllocation: proportionalAlloc,
            ...(!useRouteMode ? { aircraftMultipliers } : {}),
            ...(stationWeightedTransit && optimizeUtil ? { stationTransitWeights } : {}),
            ...(utilNoiseMode && optimizeUtil ? { utilNoiseMode: true } : {}),
          } : {}),
        }),
      });
      if (!res.ok) {
        let msg = null;
        try { const e = await res.json(); if (e.error) msg = e.error; } catch {}
        if (!msg) msg = res.status === 500
          ? `Cannot reach server — is port ${useDbSolver ? 5051 : 5050} running?`
          : `Server error (HTTP ${res.status})`;
        setErrorDetail(msg);
        setStatus("error");
        return;
      }
      const data = await res.json();
      if (data.status === "sat") {
        // Built once, then applied to state and persisted from the same object —
        // see resultFields above for why this stays in sync with Save/Load Results.
        const snapshot = {
          status: "sat", solvedT: data.T, paths: data.paths,
          noiseMatrix: useDbSolver ? data.noiseMatrix : data.countMatrix,
          countMatrix: data.countMatrix,
          unstatDetail: null,
          solvedStationZones: stationZones, solvedStationBaselines: stationBaselines, solvedDbPerCraft: dbPerCraft,
          solvedM: M, solvedUseDbSolver: useDbSolver,
          solvedD: D, solvedU: U, solvedProportionalAlloc: proportionalAlloc,
          protectedNoiseVal: data.protectedNoise ?? null,
          solvedProtectedStn: data.protectedStations ?? null,
          proportionalNoiseVal: data.proportionalNoise ?? null,
          solvedProportionalStn: data.proportionalStations ?? null,
          warningMsg: data.warning ?? null,
          solvedTMin: data.T_min ?? null,
          solvedTUsed: data.T_used ?? null,
          solvedOptimizeUtil: optimizeUtil,
          solvedOptimizePrior: optimizePrior,
          solvedOptimizeProp: optimizeProp,
          stationCategories: data.stationCategories ?? null,
          totalUtilNoise: data.totalUtilNoise ?? null,
          solvedEndPos: effectiveEndPos,
        };
        for (const [key, , setter] of resultFields) setter(snapshot[key]);
        localStorage.setItem(RESULTS_STORAGE_KEY, JSON.stringify(snapshot));
      } else {
        setStatus("unsat"); setUnstatDetail(data.detail || null);
        localStorage.setItem(RESULTS_STORAGE_KEY, JSON.stringify({ status: "unsat", unstatDetail: data.detail || null }));
      }
    } catch (err) {
      if (err.name === "AbortError") { setStatus("idle"); return; }
      console.error("Solve error:", err);
      setErrorDetail(err.message || "Cannot reach server — is it running?");
      setStatus("error");
    }
  }

  return {
    N, M, D, U, adjacency, startPos, endPos, stationZones, stationBaselines, dbPerCraft,
    protectedStn, proportionalStn, weightUtil, weightPrior, weightProp,
    status, solvedT, paths, noiseMatrix, countMatrix, unstatDetail,
    solvedStationZones, solvedStationBaselines, solvedDbPerCraft, solvedM, solvedUseDbSolver, solvedD, solvedU, solvedProportionalAlloc,
    resultName, setResultName, defaultResultName,
    pendingResultsImport, confirmImportResults, cancelImportResults,
    protectedNoiseVal, solvedProtectedStn, proportionalNoiseVal, solvedProportionalStn, warningMsg, errorDetail, totalUtilNoise, solvedEndPos,
    optimizeUtil, optimizePrior, optimizeProp, autoProportional, autoProtected, proportionalAlloc,
    stationWeightedTransit, stationTransitWeights, aircraftMultipliers, utilNoiseMode,
    useRouteMode, routeVertiports, routeN, effectiveN,
    useDbSolver, activeTab, fileInputRef, resultsFileInputRef, resultsWithConfigFileInputRef,
    stationCategories,
    hardT, tMax, weightTime, solvedTMin, solvedTUsed,
    solvedOptimizeUtil, solvedOptimizePrior, solvedOptimizeProp,
    setAutoProportional, setAutoProtected, setProportionalAlloc,
    setStationWeightedTransit, setStationTransitWeights, setAircraftMultipliers, setUtilNoiseMode,
    setUseRouteMode, setRouteVertiports, setRouteN,
    setUseDbSolver,
    setD, setU, setStationZones, setStationBaselines, setDbPerCraft,
    setHardT, setTMax, setWeightTime,
    setWeightUtil, setWeightPrior, setWeightProp,
    setOptimizeUtil, setOptimizePrior, setOptimizeProp,
    setProtectedStn, setProportionalStn, setActiveTab,
    handleN, handleM, toggleAdj, updateStartPos, updateEndPos, removeAircraft,
    updateStationZone, updateStationBaseline,
    handleExport, handleImport, handleSolve, handleCancel,
    handleExportResults, handleImportResults, handleImportResultsWithConfig,
  };
}
