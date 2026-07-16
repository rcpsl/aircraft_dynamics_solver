import { ZONE_COLORS } from './constants';
import { useSolver } from './hooks/useSolver';
import GraphPanel from './components/GraphPanel';
import SolverTab from './components/LeftPanel/SolverTab';
import ZonesTab from './components/LeftPanel/ZonesTab';
import NoiseModelTab from './components/LeftPanel/NoiseModelTab';
import PathsTable from './components/RightPanel/PathsTable';
import TransitTable from './components/RightPanel/TransitTable';
import NoiseMatrix from './components/RightPanel/NoiseMatrix';
import ResultsImportPreview from './components/RightPanel/ResultsImportPreview';

export default function App() {
  const s = useSolver();

  const effectiveT = s.paths
    ? Math.max(1, ...s.paths.map(path => {
        for (let t = path.length - 1; t > 0; t--) {
          if (path[t] !== path[t - 1]) return t + 1;
        }
        return 1;
      }))
    : s.solvedT;

  const optLabel = [
    s.solvedOptimizeUtil  ? "utilitarian" : null,
    s.solvedOptimizePrior ? "prioritarian"  : null,
    s.solvedOptimizeProp  ? "proportional"  : null,
  ].filter(Boolean).join(" + ");

  // isSoftT: phase-2 ran with a window larger than T_min (soft-T mode)
  const isSoftT = s.solvedTMin != null && s.solvedTUsed != null && s.solvedTUsed > s.solvedTMin;

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

        {s.activeTab === "solver" && <SolverTab {...s} />}
        {s.activeTab === "zones" && (
          <ZonesTab stationZones={s.stationZones} stationBaselines={s.stationBaselines}
            updateStationZone={s.updateStationZone} updateStationBaseline={s.updateStationBaseline} />
        )}
        {s.activeTab === "noise" && (
          <NoiseModelTab dbPerCraft={s.dbPerCraft} setDbPerCraft={s.setDbPerCraft} />
        )}

        <button className="solve-btn" onClick={s.handleSolve} disabled={s.status === "solving"}>
          {s.status === "solving" ? "Solving…" : "Run Solver"}
        </button>
        {s.status === "solving" && (
          <button className="solve-btn" onClick={s.handleCancel}
            style={{ background: "#b91c1c", marginTop: "6px" }}>
            Stop
          </button>
        )}

        <div className="config-btns">
          <button className="config-btn" onClick={s.handleExport}>Save Config</button>
          <button className="config-btn" onClick={() => s.fileInputRef.current.click()}>Load Config</button>
          <input ref={s.fileInputRef} type="file" accept=".json"
            style={{ display: "none" }} onChange={s.handleImport} />
        </div>
      </div>

      {/* ── Right panel ── */}
      <div className="right-panel">
        <div style={{ marginBottom: "12px" }}>
          <input type="text" className="field-input" placeholder={s.defaultResultName}
            value={s.resultName} onChange={e => s.setResultName(e.target.value)}
            title="Optional name for Save Results — leave blank to auto-name from N, M, and active fairness principles"
            style={{ width: "100%", marginBottom: "6px", boxSizing: "border-box" }} />
          <div className="config-btns" style={{ marginBottom: "6px" }}>
            <button className="config-btn" onClick={s.handleExportResults}
              disabled={s.status !== "sat" && s.status !== "unsat"}>
              Save Results
            </button>
            <button className="config-btn" onClick={() => s.resultsFileInputRef.current.click()}
              title="Load only the saved results — leaves your current config untouched">
              Load Results
            </button>
            <input ref={s.resultsFileInputRef} type="file" accept=".json"
              style={{ display: "none" }} onChange={s.handleImportResults} />
          </div>
          <div className="config-btns">
            <button className="config-btn" onClick={() => s.resultsWithConfigFileInputRef.current.click()}
              title="Load results and replace your current config — asks for confirmation first">
              Load Results + Config
            </button>
            <input ref={s.resultsWithConfigFileInputRef} type="file" accept=".json"
              style={{ display: "none" }} onChange={s.handleImportResultsWithConfig} />
          </div>
        </div>

        {s.status === "idle" && (
          <p className="idle-message">Configure parameters on the left and click <strong>Run Solver</strong>.</p>
        )}

        {s.status !== "idle" && (
          <div>
            {s.status === "solving" && <span className="status solving">Solving…</span>}
            {s.status === "sat" && (
              <div>
                <span className="status sat">
                  {isSoftT
                    ? `✓ sat — T_min = ${s.solvedTMin}  ·  T_used = ${effectiveT}  ·  T_max = ${s.solvedTUsed}`
                    : `✓ sat — T = ${s.solvedTMin ?? s.solvedT}`}
                  {optLabel ? `  ·  ${optLabel} optimized` : ""}
                </span>
                {s.protectedNoiseVal != null && (
                  <div style={{ fontSize: "13px", color: "#44403c", marginTop: "6px" }}>
                    {s.solvedUseDbSolver ? "Total dB-weighted exposure at protected stations" : "Total aircraft visits to protected stations"}:{" "}
                    <strong>{s.protectedNoiseVal}{s.solvedUseDbSolver ? " dB·t" : ""}</strong>
                    {s.solvedProtectedStn?.length > 0 ? ` (stations ${s.solvedProtectedStn.join(", ")})` : ""}
                  </div>
                )}
                {s.proportionalNoiseVal != null && (
                  <div style={{ fontSize: "13px", color: "#44403c", marginTop: "6px" }}>
                    {s.solvedUseDbSolver ? "Total dB-weighted exposure at burden stations" : "Total aircraft visits to burden stations"}:{" "}
                    <strong>{s.proportionalNoiseVal}{s.solvedUseDbSolver ? " dB·t" : ""}</strong>
                    {s.solvedProportionalStn?.length > 0 ? ` (stations ${s.solvedProportionalStn.join(", ")})` : ""}
                  </div>
                )}
                {s.totalUtilNoise != null && (
                  <div style={{ fontSize: "13px", color: "#44403c", marginTop: "6px" }}>
                    Total noise sum (utilitarian): <strong>{s.totalUtilNoise.toFixed(2)} dB·t</strong>
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
              <span className="status error">{s.errorDetail ?? `Connection error — is the server running on port ${s.useDbSolver ? 5051 : 5050}?`}</span>
            )}
          </div>
        )}

        {s.paths && <PathsTable paths={s.paths.map(p => p.slice(0, effectiveT))} solvedT={effectiveT} />}
        {s.paths && <TransitTable paths={s.paths.map(p => p.slice(0, effectiveT))} endPos={s.solvedEndPos ?? s.endPos} />}
        {s.noiseMatrix && (
          <NoiseMatrix
            noiseMatrix={s.noiseMatrix.map(r => r.slice(0, effectiveT))}
            countMatrix={s.countMatrix ? s.countMatrix.map(r => r.slice(0, effectiveT)) : null}
            solvedT={effectiveT} M={s.solvedM}
            stationBaselines={s.solvedStationBaselines} dbPerCraft={s.solvedDbPerCraft} isDbMode={s.solvedUseDbSolver} />
        )}
      </div>

      {s.pendingResultsImport && (
        <ResultsImportPreview
          envelope={s.pendingResultsImport}
          onConfirm={s.confirmImportResults}
          onCancel={s.cancelImportResults}
        />
      )}

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
