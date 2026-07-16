import { ZONES, CUSTOM_ZONE_ID } from '../../constants';

export default function ZonesTab({ stationZones, stationBaselines, updateStationZone, updateStationBaseline }) {
  return (
    <div>
      <section>
        <h2>Station Zones</h2>
        <p className="noise-model-desc" style={{ marginBottom: "8px" }}>
          Zone sets the default ambient level; the number field overrides it per station.
        </p>
        {stationZones.map((zoneId, m) => (
          <div className="zone-row" key={m}>
            <label>S{m + 1}</label>
            <select value={zoneId}
              onChange={e => updateStationZone(m, Number(e.target.value))}>
              <option value={CUSTOM_ZONE_ID}>Custom</option>
              {ZONES.map(z => (
                <option key={z.id} value={z.id}>{z.id}. {z.name} ({z.dba} dBA)</option>
              ))}
            </select>
            <input type="number" step={0.1} value={stationBaselines[m]}
              onChange={e => updateStationBaseline(m, e.target.value)}
              className="field-input" style={{ width: "60px" }}
              title="Ambient noise level (dBA) — overrides the zone default" />
          </div>
        ))}
      </section>
    </div>
  );
}
