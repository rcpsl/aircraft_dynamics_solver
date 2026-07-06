import { computeTransitTime } from '../../utils';

export default function TransitTable({ paths, endPos }) {
  const tt    = paths.map((path, i) => computeTransitTime(path, endPos[i]));
  const total = tt.reduce((a, b) => a + b, 0);
  return (
    <section>
      <h2>Transit Times</h2>
      <div className="noise-legend">
        Steps in motion per aircraft (first move → first arrival, inclusive)&nbsp;·&nbsp;Total: {total}
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th></th>
              {tt.map((_, i) => <th key={i}>A{i}</th>)}
              <th>Total</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="row-label">Transit</td>
              {tt.map((v, i) => <td key={i}>{v}</td>)}
              <td className="row-label">{total}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  );
}
