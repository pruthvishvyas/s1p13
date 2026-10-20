import { F } from '../../utils/fields';
import { fmtCurrency, fmtInt, fmtProb, titleCase } from '../../utils/formatters';

export function DrillDownPanel({ drill, rows, onClose }) {
  if (!drill) return null;
  const subset = rows.filter((r) => String(r[drill.dim]) === drill.value);
  const arr = subset.reduce((s, r) => s + F.arr(r), 0);
  const risk = subset.reduce((s, r) => s + F.risk(r), 0);
  const prob = subset.length ? subset.reduce((s, r) => s + F.prob(r), 0) / subset.length : 0;
  const top = [...subset].sort((a, b) => F.risk(b) - F.risk(a)).slice(0, 5);
  return (
    <div className="drawer">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h3>{titleCase(drill.dim)}: {drill.value}</h3>
        <button className="btn ghost" onClick={onClose}>Close {'\u00D7'}</button>
      </div>
      <div className="stack" style={{ marginTop: 16 }}>
        <div className="card"><div className="kpi-label">Accounts</div><div className="kpi-value">{fmtInt(subset.length)}</div></div>
        <div className="card"><div className="kpi-label">ARR</div><div className="kpi-value">{fmtCurrency(arr)}</div></div>
        <div className="card"><div className="kpi-label">ARR at risk</div><div className="kpi-value">{fmtCurrency(risk)}</div></div>
        <div className="card"><div className="kpi-label">Average churn risk</div><div className="kpi-value">{fmtProb(prob)}</div></div>
        <div className="card">
          <div className="card-title">Top accounts by ARR at risk</div>
          {top.length === 0 ? <p className="muted">No accounts.</p> : top.map((r, i) => (
            <div key={F.id(r) + i} style={{ marginBottom: 8 }}><b>{F.company(r) || F.id(r)}</b> <span className="muted">{fmtCurrency(F.risk(r))}</span><div className="muted">{r.recommendation}</div></div>
          ))}
        </div>
      </div>
    </div>
  );
}
