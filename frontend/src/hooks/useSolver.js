import { useState, useEffect, useRef } from 'react';
import {
  DEFAULT_N, DEFAULT_M, DEFAULT_D, DEFAULT_U,
  DEFAULT_ADJ, DEFAULT_START, DEFAULT_END, DEFAULT_ZONES,
  DEFAULT_DB_PER_CRAFT, STORAGE_KEY,
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
  const [protectedStn, setProtectedStn] = useState(saved.protectedStn ?? []);
  const [weightUtil,   setWeightUtil]   = useState(saved.weightUtil   ?? 1.0);
  const [weightPrior,  setWeightPrior]  = useState(saved.weightPrior  ?? 1.0);

  const [status,            setStatus]            = useState("idle");
  const [solvedT,           setSolvedT]           = useState(null);
  const [paths,             setPaths]             = useState(null);
  const [noiseMatrix,       setNoiseMatrix]       = useState(null);
  const [unstatDetail,      setUnstatDetail]      = useState(null);
  const [protectedNoiseVal, setProtectedNoiseVal] = useState(null);
  const [optimizeUtil,      setOptimizeUtil]      = useState(false);
  const [optimizePrior,     setOptimizePrior]     = useState(false);
  const [activeTab,         setActiveTab]         = useState("solver");
  const fileInputRef = useRef(null);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      N, M, D, U, adjacency, startPos, endPos,
      stationZones, dbPerCraft, protectedStn, weightUtil, weightPrior,
    }));
  }, [N, M, D, U, adjacency, startPos, endPos, stationZones, dbPerCraft, protectedStn, weightUtil, weightPrior]);

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
    const blob = new Blob([JSON.stringify({ N, M, D, U, adjacency, startPos, endPos, stationZones, dbPerCraft }, null, 2)], { type: "application/json" });
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
        if (c.adjacency    !== undefined) setAdjacency(c.adjacency);
        if (c.startPos     !== undefined) setStartPos(c.startPos);
        if (c.endPos       !== undefined) setEndPos(c.endPos);
        if (c.stationZones !== undefined) setStationZones(c.stationZones);
        if (c.dbPerCraft   !== undefined) setDbPerCraft(c.dbPerCraft);
      } catch { alert("Invalid config file."); }
    };
    reader.readAsText(file);
    e.target.value = "";
  }

  async function handleSolve() {
    setStatus("solving");
    setPaths(null); setNoiseMatrix(null); setSolvedT(null); setProtectedNoiseVal(null);
    try {
      const res = await fetch("http://localhost:5050/solve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          N, M, D, U, adjacency,
          startPositions:       startPos,
          endPositions:         endPos,
          optimizeUtilitarian:  optimizeUtil,
          optimizePrioritarian: optimizePrior,
          protectedStations:    protectedStn,
          weightUtilitarian:    weightUtil,
          weightPrioritarian:   weightPrior,
        }),
      });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      if (data.status === "sat") {
        setStatus("sat"); setSolvedT(data.T); setPaths(data.paths);
        setNoiseMatrix(data.noiseMatrix); setUnstatDetail(null);
        setProtectedNoiseVal(data.protectedNoise ?? null);
      } else {
        setStatus("unsat"); setUnstatDetail(data.detail || null);
      }
    } catch { setStatus("error"); }
  }

  return {
    N, M, D, U, adjacency, startPos, endPos, stationZones, dbPerCraft,
    protectedStn, weightUtil, weightPrior,
    status, solvedT, paths, noiseMatrix, unstatDetail, protectedNoiseVal,
    optimizeUtil, optimizePrior, activeTab, fileInputRef,
    setD, setU, setStationZones, setDbPerCraft,
    setWeightUtil, setWeightPrior, setOptimizeUtil, setOptimizePrior,
    setProtectedStn, setActiveTab,
    handleN, handleM, toggleAdj, updateStartPos, updateEndPos,
    handleExport, handleImport, handleSolve,
  };
}
