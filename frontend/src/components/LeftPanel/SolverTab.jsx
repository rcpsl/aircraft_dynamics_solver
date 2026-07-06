import Slider from '../Slider';
import { BENEFIT_ZONE_IDS, PROTECTED_ZONE_IDS } from '../../constants';

export default function SolverTab({
  N, M, D, U, adjacency, startPos, endPos,
  optimizeUtil, optimizePrior, optimizeProp, autoProportional, autoProtected,
  protectedStn, proportionalStn, stationZones, weightUtil, weightPrior, weightProp,
  handleN, handleM, setD, setU, toggleAdj, updateStartPos, updateEndPos,
  setOptimizeUtil, setOptimizePrior, setOptimizeProp, setAutoProportional, setAutoProtected,
  setProtectedStn, setProportionalStn, setWeightUtil, setWeightPrior, setWeightProp,
}) {
  return (
    <div>
      <section>
        <h2>Parameters</h2>
        <Slider label="N  aircraft"  value={N} min={1} max={10} onChange={handleN} />
        <Slider label="M  stations"  value={M} min={2} max={10} onChange={handleM} />
        <Slider label="D  noise cap" value={D} min={0} max={10} onChange={setD} />
        <Slider label="U  adj. diff" value={U} min={0} max={10} onChange={setU} />
      </section>

      <section>
        <h2>Start Positions</h2>
        <div className="pos-grid">
          {startPos.map((p, i) => (
            <div className="pos-cell" key={i}>
              <span>A{i}</span>
              <input type="number" min={1} max={M} value={p}
                onChange={e => updateStartPos(i, e.target.value)} />
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2>End Positions</h2>
        <div className="pos-grid">
          {endPos.map((p, i) => (
            <div className="pos-cell" key={i}>
              <span>A{i}</span>
              <input type="number" min={1} max={M} value={p}
                onChange={e => updateEndPos(i, e.target.value)} />
            </div>
          ))}
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
      </section>
    </div>
  );
}
