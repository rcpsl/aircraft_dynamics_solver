import Slider from '../Slider';
import { BENEFIT_ZONE_IDS, PROTECTED_ZONE_IDS } from '../../constants';

export default function SolverTab({
  N, M, D, U, adjacency, startPos, endPos,
  optimizeUtil, optimizePrior, optimizeProp, autoProportional, autoProtected,
  protectedStn, proportionalStn, stationZones, weightUtil, weightPrior, weightProp,
  handleN, handleM, setD, setU, toggleAdj, updateStartPos, updateEndPos, removeAircraft,
  hardT, tMax, weightTime, setHardT, setTMax, setWeightTime,
  setOptimizeUtil, setOptimizePrior, setOptimizeProp, setAutoProportional, setAutoProtected,
  setProtectedStn, setProportionalStn, setWeightUtil, setWeightPrior, setWeightProp,
  proportionalAlloc, setProportionalAlloc,
  stationWeightedTransit, setStationWeightedTransit, stationTransitWeights, setStationTransitWeights,
  aircraftMultipliers, setAircraftMultipliers,
  utilNoiseMode, setUtilNoiseMode,
  useRouteMode, setUseRouteMode, routeVertiports, setRouteVertiports, routeN, setRouteN, effectiveN,
  useDbSolver, setUseDbSolver,
}) {
  return (
    <div>
      <section>
        <h2>Solver Mode</h2>
        <label className="check-row">
          <input type="checkbox" checked={useDbSolver}
            onChange={e => { setUseDbSolver(e.target.checked); if (e.target.checked) setD(70); }} />
          Use dB-based solver (port 5051)
        </label>
        {useDbSolver && (
          <div className="adj-hint" style={{ marginTop: "4px" }}>
            D = max absolute dB level at any station · U = max dB disparity between stations · baseline from zone assignments
          </div>
        )}
      </section>

      <section>
        <h2>Parameters</h2>

        <label className="check-row" style={{ marginBottom: "10px" }}>
          <input type="checkbox" checked={useRouteMode}
            onChange={e => setUseRouteMode(e.target.checked)} />
          Route mode
        </label>
        {useRouteMode && (
          <div className="opt-indent" style={{ marginBottom: "10px" }}>
            <div className="adj-hint" style={{ marginBottom: "5px" }}>Vertiports</div>
            <div className="station-chips">
              {Array.from({ length: M }, (_, idx) => {
                const s = idx + 1;
                const on = routeVertiports.includes(s);
                return (
                  <div key={s} className={`station-chip${on ? " on" : ""}`}
                    onClick={() => on
                      ? setRouteVertiports(vs => vs.filter(x => x !== s))
                      : setRouteVertiports(vs => [...vs, s].sort((a, b) => a - b))}>
                    {s}
                  </div>
                );
              })}
            </div>
            <div className="weight-row" style={{ marginTop: "6px" }}>
              <span className="wlabel">N / dir</span>
              <input type="number" min={1} max={10} value={routeN}
                onChange={e => setRouteN(Math.max(1, parseInt(e.target.value) || 1))}
                className="field-input" style={{ width: "52px" }} />
            </div>
            {routeVertiports.length >= 2 ? (
              <div className="adj-hint" style={{ marginTop: "5px" }}>
                {effectiveN} aircraft total &nbsp;·&nbsp; {routeVertiports.length} vertiports × {routeN} per direction
              </div>
            ) : (
              <div className="adj-hint" style={{ marginTop: "5px", color: "#b91c1c" }}>
                Select at least 2 vertiports
              </div>
            )}
          </div>
        )}

        <div style={useRouteMode ? { opacity: 0.35, pointerEvents: "none" } : {}}>
          <Slider label="N  aircraft" value={useRouteMode ? effectiveN : N} min={1} max={20} onChange={handleN} />
        </div>
        <Slider label="M  stations"  value={M} min={2} max={16} onChange={handleM} />
        <Slider label={useDbSolver ? "D  abs. dB limit" : "D  noise cap"}
          value={D} min={useDbSolver ? 40 : 0} max={useDbSolver ? 90 : 10}
          step={useDbSolver ? 1 : 1} onChange={setD} />
        <Slider label="U  global diff" value={U} min={0} max={useDbSolver ? 50 : 10} step={useDbSolver ? 0.5 : 1} onChange={setU} />
      </section>

      <section style={useRouteMode ? { opacity: 0.35, pointerEvents: "none" } : {}}>
        <h2>Aircraft</h2>
        <div style={{
          display: "grid",
          gridTemplateColumns: useDbSolver ? "28px 1fr 1fr 1fr 24px" : "28px 1fr 1fr 24px",
          gap: "4px 6px",
          alignItems: "center",
        }}>
          <div />
          <div className="adj-hint" style={{ textAlign: "center" }}>Start</div>
          <div className="adj-hint" style={{ textAlign: "center" }}>End</div>
          {useDbSolver && <div className="adj-hint" style={{ textAlign: "center" }}>Mult</div>}
          <div />
          {startPos.flatMap((p, i) => [
            <span key={`lbl-${i}`} style={{ fontSize: "12px", color: "#78716c" }}>A{i}</span>,
            <input key={`s-${i}`} type="number" min={1} max={M} value={p}
              onChange={e => updateStartPos(i, e.target.value)}
              className="field-input" style={{ width: "100%" }} />,
            <input key={`e-${i}`} type="number" min={1} max={M} value={endPos[i]}
              onChange={e => updateEndPos(i, e.target.value)}
              className="field-input" style={{ width: "100%" }} />,
            ...(useDbSolver ? [
              <input key={`m-${i}`} type="number" min={1} step={1} value={aircraftMultipliers[i]}
                onChange={e => {
                  const nv = Math.max(1, parseInt(e.target.value, 10) || 1);
                  setAircraftMultipliers(ms => ms.map((x, j) => j === i ? nv : x));
                }}
                className="field-input" style={{ width: "100%" }} />,
            ] : []),
            <button key={`del-${i}`} type="button" onClick={() => removeAircraft(i)}
              disabled={N <= 1} title="Remove aircraft"
              style={{
                width: "22px", height: "22px", padding: 0, lineHeight: 1,
                border: "1px solid #d4cfc8", borderRadius: "4px",
                background: N <= 1 ? "#f0efec" : "#faf9f7",
                color: N <= 1 ? "#c7c2ba" : "#b91c1c",
                cursor: N <= 1 ? "not-allowed" : "pointer",
                fontSize: "14px",
              }}>
              ×
            </button>,
          ])}
        </div>
      </section>

      <section>
        <h2>Adjacency Matrix</h2>
        <div className="adj-hint">Row = from station, Col = to station</div>
        <div className="adj-grid" style={{ gridTemplateColumns: `22px repeat(${M}, 22px)` }}>
          <div />
          {Array.from({ length: M }, (_, j) => <div key={j} className="adj-header">{j + 1}</div>)}
          {adjacency.map((row, i) => [
            <div key={`h${i}`} className="adj-header">{i + 1}</div>,
            ...row.map((val, j) => (
              <div key={`${i}-${j}`} className={`adj-cell ${val ? "adj-on" : "adj-off"}`}
                onClick={() => toggleAdj(i, j)} title={`${i+1} → ${j+1}`} />
            )),
          ])}
        </div>
      </section>

      <section>
        <h2>Optimization</h2>
        <label className="check-row">
          <input type="checkbox" checked={optimizeUtil} onChange={e => setOptimizeUtil(e.target.checked)} />
          Minimize transit time
        </label>
        <div className="opt-indent">
          <div className="weight-row">
            <span className="wlabel">Weight</span>
            <input type="range" min={0} max={2} step={0.1} value={weightUtil}
              onChange={e => setWeightUtil(Number(e.target.value))} />
            <span className="wval">{weightUtil.toFixed(1)}</span>
          </div>
          {useDbSolver && optimizeUtil && (
            <>
              <label className="check-row" style={{ marginTop: "8px" }}>
                <input type="checkbox" checked={utilNoiseMode}
                  onChange={e => setUtilNoiseMode(e.target.checked)} />
                Use actual noise sum instead of transit time
              </label>
              <label className="check-row" style={{ marginTop: "6px" }}>
                <input type="checkbox" checked={stationWeightedTransit}
                  onChange={e => setStationWeightedTransit(e.target.checked)} />
                Station-weighted transit cost
              </label>
              {stationWeightedTransit && (
                <div style={{ marginTop: "4px" }}>
                  {stationTransitWeights.map((w, m) => (
                    <div key={m} className="weight-row" style={{ marginTop: "3px" }}>
                      <span className="wlabel">Stn {m + 1}</span>
                      <input
                        type="number" min={0} step={0.1} value={w}
                        onChange={e => {
                          const v = Math.max(0, parseFloat(e.target.value) || 0);
                          setStationTransitWeights(ws => ws.map((x, i) => i === m ? v : x));
                        }}
                        className="field-input" style={{ width: "60px" }} />
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>

        <label className="check-row" style={{ marginTop: "10px" }}>
          <input type="checkbox" checked={optimizePrior} onChange={e => setOptimizePrior(e.target.checked)} />
          Reduce noise at protected stations
        </label>
        <div className="opt-indent">
          <label className="check-row" style={{ marginBottom: "8px" }}>
            <input type="checkbox" checked={autoProtected}
              onChange={e => setAutoProtected(e.target.checked)} />
            Auto-select high-burden zone stations
          </label>
          <div className="adj-hint" style={{ marginBottom: "5px" }}>Target stations</div>
          <div className="station-chips"
            style={autoProtected ? { opacity: 0.4, pointerEvents: 'none' } : {}}>
            {Array.from({ length: M }, (_, idx) => {
              const s = idx + 1;
              const on = autoProtected
                ? PROTECTED_ZONE_IDS.includes(stationZones[idx])
                : protectedStn.includes(s);
              return (
                <div key={s} className={`station-chip${on ? " on" : ""}`}
                  onClick={() => on
                    ? setProtectedStn(ps => ps.filter(x => x !== s))
                    : setProtectedStn(ps => [...ps, s].sort((a, b) => a - b))}>
                  {s}
                </div>
              );
            })}
          </div>
          <div className="weight-row">
            <span className="wlabel">Weight</span>
            <input type="range" min={0} max={2} step={0.1} value={weightPrior}
              onChange={e => setWeightPrior(Number(e.target.value))} />
            <span className="wval">{weightPrior.toFixed(1)}</span>
          </div>
        </div>

        <label className="check-row" style={{ marginTop: "10px" }}>
          <input type="checkbox" checked={optimizeProp} onChange={e => setOptimizeProp(e.target.checked)} />
          Maximize burden on specific stations
        </label>
        <div className="opt-indent">
          <label className="check-row" style={{ marginBottom: "8px" }}>
            <input type="checkbox" checked={autoProportional}
              onChange={e => setAutoProportional(e.target.checked)} />
            Auto-select high-benefit zone stations
          </label>
          <div className="adj-hint" style={{ marginBottom: "5px" }}>Benefit stations</div>
          <div className="station-chips"
            style={autoProportional ? { opacity: 0.4, pointerEvents: 'none' } : {}}>
            {Array.from({ length: M }, (_, idx) => {
              const s = idx + 1;
              const on = autoProportional
                ? BENEFIT_ZONE_IDS.includes(stationZones[idx])
                : proportionalStn.includes(s);
              return (
                <div key={s} className={`station-chip${on ? " prop-on" : ""}`}
                  onClick={() => on
                    ? setProportionalStn(ps => ps.filter(x => x !== s))
                    : setProportionalStn(ps => [...ps, s].sort((a, b) => a - b))}>
                  {s}
                </div>
              );
            })}
          </div>
          <div className="weight-row">
            <span className="wlabel">Weight</span>
            <input type="range" min={0} max={2} step={0.1} value={weightProp}
              onChange={e => setWeightProp(Number(e.target.value))} />
            <span className="wval">{weightProp.toFixed(1)}</span>
          </div>
        </div>
        <label className="check-row" style={{ marginTop: "10px" }}>
          <input type="checkbox" checked={!hardT} onChange={e => setHardT(!e.target.checked)} />
          Soft T mode (allow extra timesteps)
        </label>
        {!hardT && (
          <div className="opt-indent">
            <div className="weight-row">
              <span className="wlabel">T max</span>
              <input type="number" min={2} step={1}
                value={tMax ?? ""}
                placeholder="auto"
                className="field-input" style={{ width: "60px" }}
                onChange={e => setTMax(e.target.value === "" ? null : Math.max(2, parseInt(e.target.value) || 2))}
              />
            </div>
            <div className="weight-row" style={{ marginTop: "6px" }}>
              <span className="wlabel">Weight</span>
              <input type="range" min={0} max={2} step={0.1} value={weightTime}
                onChange={e => setWeightTime(Number(e.target.value))} />
              <span className="wval">{weightTime.toFixed(1)}</span>
            </div>
          </div>
        )}
        {useDbSolver && (
          <label className="check-row" style={{ marginTop: "10px" }}>
            <input type="checkbox" checked={proportionalAlloc}
              onChange={e => setProportionalAlloc(e.target.checked)} />
            Proportional allocation (active stations bear more noise than adjacent, then others)
          </label>
        )}
      </section>
    </div>
  );
}
