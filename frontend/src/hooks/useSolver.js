import { useState, useEffect, useRef } from 'react';
import {
  DEFAULT_N, DEFAULT_M, DEFAULT_D, DEFAULT_U,
  DEFAULT_ADJ, DEFAULT_START, DEFAULT_END, DEFAULT_ZONES,
  DEFAULT_DB_PER_CRAFT, STORAGE_KEY, BENEFIT_ZONE_IDS, PROTECTED_ZONE_IDS, ZONES,
} from '../constants';
import { resizeAdj, resizePos } from '../utils';

function loadSaved() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {}; }
  catch { return {}; }
}

export function useSolver() {
  const saved = loadSaved();

  const [N,            setN]            = useState(saved.N            ?? DEFAULT_N);
  const [M,            setM]            = useState(saved.M            ?? DEFAULT_M);
  const [D,            setD]            = useState(saved.D            ?? DEFAULT_D);
  const [U,            setU]            = useState(saved.U            ?? DEFAULT_U);
  const [adjacency,    setAdjacency]    = useState(saved.adjacency    ?? DEFAULT_ADJ);
  const [startPos,     setStartPos]     = useState(saved.startPos     ?? DEFAULT_START);
  const [endPos,       setEndPos]       = useState(saved.endPos       ?? DEFAULT_END);
  const [stationZones, setStationZones] = useState(
    (saved.stationZones ?? DEFAULT_ZONES).map(z => (z >= 1 && z <= ZONES.length) ? z : 1)
  );
  const [dbPerCraft,   setDbPerCraft]   = useState(saved.dbPerCraft   ?? DEFAULT_DB_PER_CRAFT);
  const [protectedStn,     setProtectedStn]     = useState(saved.protectedStn     ?? []);
  const [proportionalStn,  setProportionalStn]  = useState(saved.proportionalStn  ?? []);
  const [weightUtil,       setWeightUtil]       = useState(saved.weightUtil       ?? 1.0);
  const [weightPrior,      setWeightPrior]      = useState(saved.weightPrior      ?? 1.0);
  const [weightProp,       setWeightProp]       = useState(saved.weightProp       ?? 1.0);
  const [hardT,            setHardT]            = useState(saved.hardT            ?? true);
  const [tMax,             setTMax]             = useState(saved.tMax             ?? null);
  const [weightTime,       setWeightTime]       = useState(saved.weightTime       ?? 1.0);

  const [status,            setStatus]            = useState("idle");
  const [solvedT,           setSolvedT]           = useState(null);
  const [paths,             setPaths]             = useState(null);
  const [noiseMatrix,       setNoiseMatrix]       = useState(null);
  const [countMatrix,       setCountMatrix]       = useState(null);
  const [unstatDetail,      setUnstatDetail]      = useState(null);
  const [solvedStationZones,   setSolvedStationZones]   = useState(null);
  const [solvedDbPerCraft,     setSolvedDbPerCraft]     = useState(null);
  const [solvedM,              setSolvedM]              = useState(null);
  const [solvedUseDbSolver,    setSolvedUseDbSolver]    = useState(null);
  const [protectedNoiseVal,    setProtectedNoiseVal]    = useState(null);
  const [solvedProtectedStn,   setSolvedProtectedStn]   = useState(null);
  const [proportionalNoiseVal, setProportionalNoiseVal] = useState(null);
  const [solvedProportionalStn,setSolvedProportionalStn]= useState(null);
  const [warningMsg,           setWarningMsg]           = useState(null);
  const [errorDetail,          setErrorDetail]          = useState(null);
  const [solvedTMin,           setSolvedTMin]           = useState(null);
  const [solvedTUsed,          setSolvedTUsed]          = useState(null);
  const [solvedOptimizeUtil,   setSolvedOptimizeUtil]   = useState(null);
  const [solvedOptimizePrior,  setSolvedOptimizePrior]  = useState(null);
  const [solvedOptimizeProp,   setSolvedOptimizeProp]   = useState(null);
  const [stationCategories,    setStationCategories]    = useState(null);
  const [totalUtilNoise,       setTotalUtilNoise]       = useState(null);
  const [solvedEndPos,         setSolvedEndPos]         = useState(null);
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
  const fileInputRef = useRef(null);
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
    setProtectedStn(ps => ps.filter(s => s <= newM));
    setProportionalStn(ps => ps.filter(s => s <= newM));
    setRouteVertiports(vs => vs.filter(s => s <= newM));
    setStationTransitWeights(w => newM <= w.length ? w.slice(0, newM) : [...w, ...Array(newM - w.length).fill(1.0)]);
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
    setSolvedStationZones(null); setSolvedDbPerCraft(null);
    setSolvedM(null); setSolvedUseDbSolver(null);
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
            baseline: stationZones.map(z => ZONES[(z || 1) - 1].dba),
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
        setStatus("sat"); setSolvedT(data.T); setPaths(data.paths);
        setCountMatrix(data.countMatrix);
        setNoiseMatrix(useDbSolver ? data.noiseMatrix : data.countMatrix);
        setUnstatDetail(null);
        setSolvedStationZones(stationZones); setSolvedDbPerCraft(dbPerCraft);
        setSolvedM(M); setSolvedUseDbSolver(useDbSolver);
        setProtectedNoiseVal(data.protectedNoise ?? null);
        setSolvedProtectedStn(data.protectedStations ?? null);
        setProportionalNoiseVal(data.proportionalNoise ?? null);
        setSolvedProportionalStn(data.proportionalStations ?? null);
        setWarningMsg(data.warning ?? null);
        setSolvedTMin(data.T_min ?? null);
        setSolvedTUsed(data.T_used ?? null);
        setSolvedOptimizeUtil(optimizeUtil);
        setSolvedOptimizePrior(optimizePrior);
        setSolvedOptimizeProp(optimizeProp);
        setStationCategories(data.stationCategories ?? null);
        setTotalUtilNoise(data.totalUtilNoise ?? null);
        setSolvedEndPos(effectiveEndPos);
      } else {
        setStatus("unsat"); setUnstatDetail(data.detail || null);
      }
    } catch (err) {
      if (err.name === "AbortError") { setStatus("idle"); return; }
      console.error("Solve error:", err);
      setErrorDetail(err.message || "Cannot reach server — is it running?");
      setStatus("error");
    }
  }

  return {
    N, M, D, U, adjacency, startPos, endPos, stationZones, dbPerCraft,
    protectedStn, proportionalStn, weightUtil, weightPrior, weightProp,
    status, solvedT, paths, noiseMatrix, countMatrix, unstatDetail,
    solvedStationZones, solvedDbPerCraft, solvedM, solvedUseDbSolver,
    protectedNoiseVal, solvedProtectedStn, proportionalNoiseVal, solvedProportionalStn, warningMsg, errorDetail, totalUtilNoise, solvedEndPos,
    optimizeUtil, optimizePrior, optimizeProp, autoProportional, autoProtected, proportionalAlloc,
    stationWeightedTransit, stationTransitWeights, aircraftMultipliers, utilNoiseMode,
    useRouteMode, routeVertiports, routeN, effectiveN,
    useDbSolver, activeTab, fileInputRef,
    stationCategories,
    hardT, tMax, weightTime, solvedTMin, solvedTUsed,
    solvedOptimizeUtil, solvedOptimizePrior, solvedOptimizeProp,
    setAutoProportional, setAutoProtected, setProportionalAlloc,
    setStationWeightedTransit, setStationTransitWeights, setAircraftMultipliers, setUtilNoiseMode,
    setUseRouteMode, setRouteVertiports, setRouteN,
    setUseDbSolver,
    setD, setU, setStationZones, setDbPerCraft,
    setHardT, setTMax, setWeightTime,
    setWeightUtil, setWeightPrior, setWeightProp,
    setOptimizeUtil, setOptimizePrior, setOptimizeProp,
    setProtectedStn, setProportionalStn, setActiveTab,
    handleN, handleM, toggleAdj, updateStartPos, updateEndPos, removeAircraft,
    handleExport, handleImport, handleSolve, handleCancel,
  };
}
