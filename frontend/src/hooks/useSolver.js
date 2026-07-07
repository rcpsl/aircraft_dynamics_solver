import { useState, useEffect, useRef } from 'react';
import {
  DEFAULT_N, DEFAULT_M, DEFAULT_D, DEFAULT_U,
  DEFAULT_ADJ, DEFAULT_START, DEFAULT_END, DEFAULT_ZONES,
  DEFAULT_DB_PER_CRAFT, STORAGE_KEY, BENEFIT_ZONE_IDS, PROTECTED_ZONE_IDS,
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
  const [stationZones, setStationZones] = useState(saved.stationZones ?? DEFAULT_ZONES);
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
  const [unstatDetail,      setUnstatDetail]      = useState(null);
  const [solvedStationZones,   setSolvedStationZones]   = useState(null);
  const [solvedDbPerCraft,     setSolvedDbPerCraft]     = useState(null);
  const [protectedNoiseVal,    setProtectedNoiseVal]    = useState(null);
  const [solvedProtectedStn,   setSolvedProtectedStn]   = useState(null);
  const [proportionalNoiseVal, setProportionalNoiseVal] = useState(null);
  const [solvedProportionalStn,setSolvedProportionalStn]= useState(null);
  const [warningMsg,           setWarningMsg]           = useState(null);
  const [solvedTMin,           setSolvedTMin]           = useState(null);
  const [solvedTUsed,          setSolvedTUsed]          = useState(null);
  const [solvedOptimizeUtil,   setSolvedOptimizeUtil]   = useState(null);
  const [solvedOptimizePrior,  setSolvedOptimizePrior]  = useState(null);
  const [solvedOptimizeProp,   setSolvedOptimizeProp]   = useState(null);
  const [optimizeUtil,         setOptimizeUtil]         = useState(saved.optimizeUtil      ?? false);
  const [optimizePrior,        setOptimizePrior]        = useState(saved.optimizePrior     ?? false);
  const [optimizeProp,         setOptimizeProp]         = useState(saved.optimizeProp      ?? false);
  const [autoProportional,     setAutoProportional]     = useState(saved.autoProportional  ?? false);
  const [autoProtected,        setAutoProtected]        = useState(saved.autoProtected     ?? false);
  const [activeTab,         setActiveTab]         = useState("solver");
  const fileInputRef = useRef(null);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      N, M, D, U, adjacency, startPos, endPos,
      stationZones, dbPerCraft, protectedStn, proportionalStn, weightUtil, weightPrior, weightProp,
      hardT, tMax, weightTime,
      optimizeUtil, optimizePrior, optimizeProp, autoProportional, autoProtected,
    }));
  }, [N, M, D, U, adjacency, startPos, endPos, stationZones, dbPerCraft, protectedStn, proportionalStn, weightUtil, weightPrior, weightProp, hardT, tMax, weightTime, optimizeUtil, optimizePrior, optimizeProp, autoProportional, autoProtected]);

  function handleN(newN) {
    setN(newN);
    setStartPos(p => resizePos(p, newN));
    setEndPos(p   => resizePos(p, newN));
  }

  function handleM(newM) {
    setM(newM);
    setAdjacency(a => resizeAdj(a, newM));
    setStartPos(p => p.map(v => Math.min(v, newM)));
    setEndPos(p   => p.map(v => Math.min(v, newM)));
    setStationZones(z => newM <= z.length ? z.slice(0, newM) : z.concat(Array.from({ length: newM - z.length }, () => 1)));
    setProtectedStn(ps => ps.filter(s => s <= newM));
    setProportionalStn(ps => ps.filter(s => s <= newM));
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

  function handleExport() {
    const blob = new Blob([JSON.stringify({
      N, M, D, U, adjacency, startPos, endPos, stationZones, dbPerCraft,
      protectedStn, proportionalStn, weightUtil, weightPrior, weightProp,
      optimizeUtil, optimizePrior, optimizeProp, autoProportional, autoProtected,
      hardT, tMax, weightTime,
    }, null, 2)], { type: "application/json" });
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
        if (c.D !== undefined) setD(c.D);
        if (c.U !== undefined) setU(c.U);
        if (c.adjacency         !== undefined) setAdjacency(c.adjacency);
        if (c.startPos          !== undefined) setStartPos(c.startPos);
        if (c.endPos            !== undefined) setEndPos(c.endPos);
        if (c.stationZones      !== undefined) setStationZones(c.stationZones);
        if (c.dbPerCraft        !== undefined) setDbPerCraft(c.dbPerCraft);
        if (c.protectedStn      !== undefined) setProtectedStn(c.protectedStn);
        if (c.proportionalStn   !== undefined) setProportionalStn(c.proportionalStn);
        if (c.weightUtil        !== undefined) setWeightUtil(c.weightUtil);
        if (c.weightPrior       !== undefined) setWeightPrior(c.weightPrior);
        if (c.weightProp        !== undefined) setWeightProp(c.weightProp);
        if (c.optimizeUtil      !== undefined) setOptimizeUtil(c.optimizeUtil);
        if (c.optimizePrior     !== undefined) setOptimizePrior(c.optimizePrior);
        if (c.optimizeProp      !== undefined) setOptimizeProp(c.optimizeProp);
        if (c.autoProportional  !== undefined) setAutoProportional(c.autoProportional);
        if (c.autoProtected     !== undefined) setAutoProtected(c.autoProtected);
        if (c.hardT             !== undefined) setHardT(c.hardT);
        if (c.tMax              !== undefined) setTMax(c.tMax);
        if (c.weightTime        !== undefined) setWeightTime(c.weightTime);
      } catch { alert("Invalid config file."); }
    };
    reader.readAsText(file);
    e.target.value = "";
  }

  async function handleSolve() {
    setStatus("solving");
    setPaths(null); setNoiseMatrix(null); setSolvedT(null);
    setSolvedStationZones(null); setSolvedDbPerCraft(null);
    setProtectedNoiseVal(null); setSolvedProtectedStn(null);
    setProportionalNoiseVal(null); setSolvedProportionalStn(null);
    setWarningMsg(null); setSolvedTMin(null); setSolvedTUsed(null);
    setSolvedOptimizeUtil(null); setSolvedOptimizePrior(null); setSolvedOptimizeProp(null);
    try {
      const res = await fetch("http://localhost:5050/solve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          N, M, D, U, adjacency,
          startPositions:        startPos,
          endPositions:          endPos,
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
        }),
      });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      if (data.status === "sat") {
        setStatus("sat"); setSolvedT(data.T); setPaths(data.paths);
        setNoiseMatrix(data.noiseMatrix); setUnstatDetail(null);
        setSolvedStationZones(stationZones); setSolvedDbPerCraft(dbPerCraft);
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
      } else {
        setStatus("unsat"); setUnstatDetail(data.detail || null);
      }
    } catch { setStatus("error"); }
  }

  return {
    N, M, D, U, adjacency, startPos, endPos, stationZones, dbPerCraft,
    protectedStn, proportionalStn, weightUtil, weightPrior, weightProp,
    status, solvedT, paths, noiseMatrix, unstatDetail,
    solvedStationZones, solvedDbPerCraft,
    protectedNoiseVal, solvedProtectedStn, proportionalNoiseVal, solvedProportionalStn, warningMsg,
    optimizeUtil, optimizePrior, optimizeProp, autoProportional, autoProtected, activeTab, fileInputRef,
    hardT, tMax, weightTime, solvedTMin, solvedTUsed,
    solvedOptimizeUtil, solvedOptimizePrior, solvedOptimizeProp,
    setAutoProportional, setAutoProtected,
    setD, setU, setStationZones, setDbPerCraft,
    setHardT, setTMax, setWeightTime,
    setWeightUtil, setWeightPrior, setWeightProp,
    setOptimizeUtil, setOptimizePrior, setOptimizeProp,
    setProtectedStn, setProportionalStn, setActiveTab,
    handleN, handleM, toggleAdj, updateStartPos, updateEndPos,
    handleExport, handleImport, handleSolve,
  };
}
