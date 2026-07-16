import { aircraftColor, noiseColor, combinedDb } from '../../utils';

function levelRows(noiseMatrix, stationBaselines, dbPerCraft, isDbMode) {
  return noiseMatrix.map((row, m) => {
    const baseline = stationBaselines[m];
    const levels = row.map(count => isDbMode ? baseline + count : combinedDb(baseline, count, dbPerCraft));
    const avg = levels.reduce((a, b) => a + b, 0) / levels.length;
    return { baseline, counts: row, levels, avg };
  });
}

function LevelTable({ title, legend, rows, solvedT, format, tooltip }) {
  return (
    <section>
      <h2>{title}</h2>
      <div className="noise-legend">{legend}</div>
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
            {rows.map((row, m) => (
              <tr key={m}>
                <td className="row-label">{m + 1}</td>
                {row.levels.map((level, t) => (
                  <td key={t} className="noise-cell"
                    style={{ background: noiseColor(level - row.baseline) }}
                    title={tooltip(row, m, t, level)}>
                    {format(row, level)}
                  </td>
                ))}
                <td className="row-label noise-cell"
                  style={{ background: noiseColor(row.avg - row.baseline) }}
                  title={tooltip(row, m, null, row.avg)}>
                  {format(row, row.avg)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function NoiseMatrix({ noiseMatrix, countMatrix, solvedT, M, stationBaselines, dbPerCraft, isDbMode }) {
  const counts = countMatrix ?? noiseMatrix;
  const maxVal = Math.max(1, ...counts.map(r => Math.max(...r)));
  const rows = levelRows(noiseMatrix, stationBaselines, dbPerCraft, isDbMode);

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
              {counts.map((row, m) => (
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

      <LevelTable
        title="Noise Matrix"
        legend={<>Rows = stations 1…{M}&nbsp;·&nbsp;Columns = timesteps 0…{solvedT - 1}&nbsp;·&nbsp;dB increase above zone baseline&nbsp;·&nbsp;scale 0–15 dB</>}
        rows={rows}
        solvedT={solvedT}
        format={(row, level) => `+${(level - row.baseline).toFixed(1)}`}
        tooltip={(row, m, t, level) => t == null
          ? `stn ${m+1} avg: +${(level - row.baseline).toFixed(1)} dB above ${row.baseline} dBA baseline`
          : isDbMode
            ? `stn ${m+1}, t=${t}: +${(level - row.baseline).toFixed(1)} dB`
            : `stn ${m+1}, t=${t}: ${row.counts[t]} aircraft, +${(level - row.baseline).toFixed(1)} dB above ${row.baseline} dBA baseline`}
      />

      <LevelTable
        title="Total Noise Matrix"
        legend={<>Rows = stations 1…{M}&nbsp;·&nbsp;Columns = timesteps 0…{solvedT - 1}&nbsp;·&nbsp;absolute dB level at station (baseline + aircraft contribution)</>}
        rows={rows}
        solvedT={solvedT}
        format={(row, level) => level.toFixed(1)}
        tooltip={(row, m, t, level) => t == null
          ? `stn ${m+1} avg: ${level.toFixed(1)} dB`
          : `stn ${m+1}, t=${t}: ${level.toFixed(1)} dB (baseline ${row.baseline} dB)`}
      />
    </>
  );
}
