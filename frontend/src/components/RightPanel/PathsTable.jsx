export default function PathsTable({ paths, solvedT }) {
  return (
    <section>
      <h2>Aircraft Paths</h2>
      <div className="table-wrap">
        <table className="paths-table">
          <thead>
            <tr>
              <th>Aircraft</th>
              {Array.from({ length: solvedT }, (_, t) => <th key={t}>t={t}</th>)}
            </tr>
          </thead>
          <tbody>
            {paths.map((row, i) => (
              <tr key={i}>
                <td className="row-label">A{i}</td>
                {row.map((stn, t) => <td key={t}>{stn}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
