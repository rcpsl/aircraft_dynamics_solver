import { ZONES } from '../../constants';

export default function ZonesTab({ stationZones, setStationZones }) {
  return (
    <div>
      <section>
        <h2>Station Zones</h2>
        {stationZones.map((zoneId, m) => (
          <div className="zone-row" key={m}>
            <label>S{m + 1}</label>
            <select value={zoneId}
              onChange={e => setStationZones(z => z.map((v, i) => i === m ? Number(e.target.value) : v))}>
              {ZONES.map(z => (
                <option key={z.id} value={z.id}>{z.id}. {z.name} ({z.dba} dBA)</option>
              ))}
            </select>
          </div>
        ))}
      </section>
    </div>
  );
}
