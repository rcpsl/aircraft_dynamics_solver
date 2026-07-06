import { ZONE_COLORS } from './constants';
import { useSolver } from './hooks/useSolver';
import GraphPanel from './components/GraphPanel';
import SolverTab from './components/LeftPanel/SolverTab';
import ZonesTab from './components/LeftPanel/ZonesTab';
import NoiseModelTab from './components/LeftPanel/NoiseModelTab';
import PathsTable from './components/RightPanel/PathsTable';
import TransitTable from './components/RightPanel/TransitTable';
import NoiseMatrix from './components/RightPanel/NoiseMatrix';

export default function App() {
  const s = useSolver();

  const optLabel = [
    s.optimizeUtil  ? "transit"       : null,
    s.optimizePrior ? "prioritarian"  : null,
    s.optimizeProp  ? "proportional"  : null,
  ].filter(Boolean).join(" + ");

  return (
    <div className="app">

      {/* ── Left panel ── */}
      <div className="left-panel">
        <h1>UAM Noise<br />Solver</h1>

        <div className="tab-bar">
          {[["solver","Solver"],["zones","Zones"],["noise","Noise Model"]].map(([id, label]) => (
            <button key={id} className={`tab-btn${s.activeTab === id ? " active" : ""}`}
              onClick={() => s.setActiveTab(id)}>{label}</button>
          ))}
        </div>

        {s.activeTab === "solver" && (
          <SolverTab
            N={s.N} M={s.M} D={s.D} U={s.U} adjacency={s.adjacency}
            startPos={s.startPos} endPos={s.endPos}
            optimizeUtil={s.optimizeUtil} optimizePrior={s.optimizePrior} optimizeProp={s.optimizeProp}
            autoProportional={s.autoProportional} autoProtected={s.autoProtected}
            protectedStn={s.protectedStn} proportionalStn={s.proportionalStn}
            stationZones={s.stationZones}
            weightUtil={s.weightUtil} weightPrior={s.weightPrior} weightProp={s.weightProp}
            handleN={s.handleN} handleM={s.handleM} setD={s.setD} setU={s.setU}
            toggleAdj={s.toggleAdj} updateStartPos={s.updateStartPos} updateEndPos={s.updateEndPos}
            setOptimizeUtil={s.setOptimizeUtil} setOptimizePrior={s.setOptimizePrior} setOptimizeProp={s.setOptimizeProp}
            setAutoProportional={s.setAutoProportional} setAutoProtected={s.setAutoProtected}
            setProtectedStn={s.setProtectedStn} setProportionalStn={s.setProportionalStn}
            setWeightUtil={s.setWeightUtil} setWeightPrior={s.setWeightPrior} setWeightProp={s.setWeightProp}
          />
        )}
        {s.activeTab === "zones" && (
          <ZonesTab stationZones={s.stationZones} setStationZones={s.setStationZones} />
        )}
        {s.activeTab === "noise" && (
          <NoiseModelTab dbPerCraft={s.dbPerCraft} setDbPerCraft={s.setDbPerCraft} />
        )}

        <button className="solve-btn" onClick={s.handleSolve} disabled={s.status === "solving"}>
          {s.status === "solving" ? "Solving…" : "Run Solver"}
        </button>

        <div className="config-btns">
          <button className="config-btn" onClick={s.handleExport}>Save Config</button>
          <button className="config-btn" onClick={() => s.fileInputRef.current.click()}>Load Config</button>
          <input ref={s.fileInputRef} type="file" accept=".json"
            style={{ display: "none" }} onChange={s.handleImport} />
        </div>
      </div>

      {/* ── Right panel ── */}
      <div className="right-panel">
        {s.status === "idle" && (
          <p className="idle-message">Configure parameters on the left and click <strong>Run Solver</strong>.</p>
        )}

        {s.status !== "idle" && (
          <div>
            {s.status === "solving" && <span className="status solving">Solving…</span>}
            {s.status === "sat" && (
              <div>
                <span className="status sat">
                  ✓ sat — minimum T = {s.solvedT}
                  {optLabel ? `  ·  ${optLabel} optimized` : ""}
                </span>
                {s.protectedNoiseVal != null && (
                  <div style={{ fontSize: "13px", color: "#44403c", marginTop: "6px" }}>
                    Total aircraft visits to protected stations: <strong>{s.protectedNoiseVal}</strong>
                    {s.solvedProtectedStn?.length > 0 ? ` (stations ${s.solvedProtectedStn.join(", ")})` : ""}
                  </div>
                )}
                {s.proportionalNoiseVal != null && (
                  <div style={{ fontSize: "13px", color: "#44403c", marginTop: "6px" }}>
                    Total aircraft visits to burden stations: <strong>{s.proportionalNoiseVal}</strong>
                    {s.solvedProportionalStn?.length > 0 ? ` (stations ${s.solvedProportionalStn.join(", ")})` : ""}
                  </div>
                )}
                {s.warningMsg && (
                  <div style={{ fontSize: "12px", color: "#92400e", background: "#fef3c7", borderRadius: "5px", padding: "6px 10px", marginTop: "6px" }}>
                    ⚠ {s.warningMsg}
                  </div>
                )}
              </div>
            )}
            {s.status === "unsat" && (
              <span className="status unsat">✗ unsat — {s.unstatDetail || "try relaxing D or U"}</span>
            )}
            {s.status === "error" && (
              <span className="status error">Connection error — is the server running on port 5050?</span>
            )}
          </div>
        )}

        {s.paths && <PathsTable paths={s.paths} solvedT={s.solvedT} />}
        {s.paths && <TransitTable paths={s.paths} endPos={s.endPos} />}
        {s.noiseMatrix && (
          <NoiseMatrix noiseMatrix={s.noiseMatrix} solvedT={s.solvedT} M={s.M}
            stationZones={s.solvedStationZones} dbPerCraft={s.solvedDbPerCraft} />
        )}
      </div>

      {/* ── Graph panel ── */}
      <div className="graph-panel">
        <div>
          <h2>Station Graph</h2>
          <p className="graph-hint">→ one-way &nbsp;·&nbsp; ↔ two-way &nbsp;·&nbsp; self-loops omitted</p>
        </div>
        <GraphPanel key={s.M} M={s.M} adjacency={s.adjacency} stationZones={s.stationZones} />
        <div className="zone-legend">
          {Object.entries(ZONE_COLORS).map(([cat, color]) => (
            <div key={cat} className="zone-legend-item">
              <span className="zone-dot" style={{ background: color }} />
              <span>{cat}</span>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
}
