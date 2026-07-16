const FIELD_LABELS = {
  N: "Aircraft (N)", M: "Stations (M)", D: "D (max visits)", U: "U (max per-station noise)",
  adjacency: "Adjacency matrix", startPos: "Start positions", endPos: "End positions",
  stationZones: "Station zones", stationBaselines: "Station ambient baselines (dBA)",
  dbPerCraft: "dB per aircraft", protectedStn: "Protected stations", proportionalStn: "Proportional/burden stations",
  weightUtil: "Utilitarian weight", weightPrior: "Prioritarian weight", weightProp: "Proportional weight",
  hardT: "Hard T (fixed horizon)", tMax: "T max (soft T)", weightTime: "Time weight",
  optimizeUtil: "Optimize utilitarian", optimizePrior: "Optimize prioritarian", optimizeProp: "Optimize proportional",
  autoProportional: "Auto proportional stations", autoProtected: "Auto protected stations",
  proportionalAlloc: "Proportional allocation", stationWeightedTransit: "Station-weighted transit cost",
  stationTransitWeights: "Station transit weights", aircraftMultipliers: "Per-aircraft multipliers",
  utilNoiseMode: "Utilitarian noise-sum mode", useRouteMode: "Route mode",
  routeVertiports: "Route vertiports", routeN: "Flights per route pair", useDbSolver: "Solver",
};

function formatValue(key, value) {
  if (key === "useDbSolver") return value ? "dB-based" : "Count-based";
  if (Array.isArray(value)) return value.length ? JSON.stringify(value) : "(none)";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
}

export default function ResultsImportPreview({ envelope, onConfirm, onCancel }) {
  const config = envelope.config || {};
  const keys = Object.keys(FIELD_LABELS).filter(k => config[k] !== undefined);

  return (
    <div className="modal-overlay">
      <div className="modal-box">
        <h2>Load Results — Review Input Parameters</h2>
        <p className="noise-model-desc" style={{ marginBottom: "12px" }}>
          <strong>{envelope.name || "(unnamed)"}</strong>
          {envelope.savedAt ? ` — saved ${new Date(envelope.savedAt).toLocaleString()}` : ""}
          <br />
          These are the input parameters that produced this result (read-only). Confirming
          will replace your current left-panel configuration and results panel with these values.
        </p>
        <div className="table-wrap" style={{ maxHeight: "45vh", overflowY: "auto" }}>
          <table>
            <tbody>
              {keys.map(k => (
                <tr key={k}>
                  <td className="row-label" style={{ textAlign: "left", whiteSpace: "normal" }}>{FIELD_LABELS[k]}</td>
                  <td style={{ textAlign: "left", whiteSpace: "normal", wordBreak: "break-word" }}>
                    {formatValue(k, config[k])}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="config-btns" style={{ marginTop: "16px" }}>
          <button className="config-btn" onClick={onCancel}>Cancel</button>
          <button className="config-btn config-btn-primary" onClick={onConfirm}>
            Replace Config &amp; Results
          </button>
        </div>
      </div>
    </div>
  );
}
