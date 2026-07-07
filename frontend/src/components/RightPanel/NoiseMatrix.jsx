import { ZONES } from '../../constants';
import { aircraftColor, noiseColor, combinedDb } from '../../utils';

export default function NoiseMatrix({ noiseMatrix, solvedT, M, stationZones, dbPerCraft }) {
  const maxVal = Math.max(1, ...noiseMatrix.map(r => Math.max(...r)));

  return (
    <>
      <section>
        <h2>Aircraft Matrix</h2>
        <div className="noise-legend">
          Rows = stations 1…{M}&nbsp;·&nbsp;Columns = timesteps 0…{solvedT - 1}&nbsp;·&nbsp;Darker = more aircraft present
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Stn</th>
                {Array.from({ length: solvedT }, (_, t) => <th key={t}>t={t}</th>)}
              </tr>
            </thead>
            <tbody>
              {noiseMatrix.map((row, m) => (
                <tr key={m}>
                  <td className="row-label">{m + 1}</td>
                  {row.map((count, t) => (
                    <td key={t} className="noise-cell"
                      style={{ background: aircraftColor(count, maxVal) }}
                      title={`stn ${m+1}, t=${t}: ${count} aircraft`}>
                      {count}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2>Noise Matrix</h2>
        <div className="noise-legend">
          Rows = stations 1…{M}&nbsp;·&nbsp;Columns = timesteps 0…{solvedT - 1}&nbsp;·&nbsp;dB increase above zone baseline&nbsp;·&nbsp;scale 0–15 dB
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Stn</th>
                {Array.from({ length: solvedT }, (_, t) => <th key={t}>t={t}</th>)}
                <th>Avg</th>
              </tr>
            </thead>
            <tbody>
              {noiseMatrix.map((row, m) => {
                const baseline = ZONES[(stationZones[m] || 1) - 1].dba;
                const deltas = row.map(count => combinedDb(baseline, count, dbPerCraft) - baseline);
                const avg = deltas.reduce((a, b) => a + b, 0) / deltas.length;
                return (
                  <tr key={m}>
                    <td className="row-label">{m + 1}</td>
                    {deltas.map((delta, t) => (
                      <td key={t} className="noise-cell"
                        style={{ background: noiseColor(delta) }}
                        title={`stn ${m+1}, t=${t}: ${row[t]} aircraft, +${delta.toFixed(1)} dB above ${baseline} dBA baseline`}>
                        +{delta.toFixed(1)}
                      </td>
                    ))}
                    <td className="row-label noise-cell" style={{ background: noiseColor(avg) }}
                      title={`stn ${m+1} avg: +${avg.toFixed(1)} dB above ${baseline} dBA baseline`}>
                      +{avg.toFixed(1)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
      <section>
        <h2>Total Noise Matrix</h2>
        <div className="noise-legend">
          Rows = stations 1…{M}&nbsp;·&nbsp;Columns = timesteps 0…{solvedT - 1}&nbsp;·&nbsp;absolute dB level at station (baseline + aircraft contribution)
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Stn</th>
                {Array.from({ length: solvedT }, (_, t) => <th key={t}>t={t}</th>)}
                <th>Peak</th>
              </tr>
            </thead>
            <tbody>
              {noiseMatrix.map((row, m) => {
                const baseline = ZONES[(stationZones[m] || 1) - 1].dba;
                const absLevels = row.map(count => combinedDb(baseline, count, dbPerCraft));
                const peak = Math.max(...absLevels);
                return (
                  <tr key={m}>
                    <td className="row-label">{m + 1}</td>
                    {absLevels.map((db, t) => (
                      <td key={t} className="noise-cell"
                        style={{ background: noiseColor(db - baseline) }}
                        title={`stn ${m+1}, t=${t}: ${db.toFixed(1)} dB (baseline ${baseline} dB)`}>
                        {db.toFixed(1)}
                      </td>
                    ))}
                    <td className="row-label noise-cell" style={{ background: noiseColor(peak - baseline) }}
                      title={`stn ${m+1} peak: ${peak.toFixed(1)} dB`}>
                      {peak.toFixed(1)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
