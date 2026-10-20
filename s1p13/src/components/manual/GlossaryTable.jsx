import { highlight } from './ManualSection';

export function GlossaryTable({ rows, q }) {
  return (
    <div className="card table-wrap">
      <table className="data">
        <thead><tr><th>Term</th><th>What it means</th></tr></thead>
        <tbody>
          {rows.map(([t, d]) => <tr key={t}><td><b>{highlight(t, q)}</b></td><td>{highlight(d, q)}</td></tr>)}
        </tbody>
      </table>
      {rows.length === 0 && <p className="muted">No matching terms.</p>}
    </div>
  );
}
