import { useState } from 'react';
import { useInsights } from '../../hooks/decide/useInsights';
import { validateInsights } from '../../utils/dataValidator';
import { DataState } from '../shared/DataState';
import { SeverityBadge } from '../shared/SeverityBadge';

const ORDER = { HIGH: 0, MEDIUM: 1, LOW: 2 };

export function InsightCards() {
  const { data: raw, loading, error } = useInsights();
  const { valid, data, error: ve } = validateInsights(raw);
  const [sev, setSev] = useState('ALL');
  const rows = [...data].sort((a, b) => (ORDER[String(a.severity).toUpperCase()] ?? 9) - (ORDER[String(b.severity).toUpperCase()] ?? 9))
    .filter((i) => sev === 'ALL' || String(i.severity).toUpperCase() === sev);
  return (
    <DataState loading={loading} error={error} valid={valid} detail={ve} message="No insights available yet." height={140} count={3}>
      <div className="chips">
        {['ALL', 'HIGH', 'MEDIUM', 'LOW'].map((s) => (
          <button key={s} className={'chip' + (sev === s ? ' active' : '')} onClick={() => setSev(s)}>{s}</button>
        ))}
      </div>
      <div className="stack">
        {rows.map((i, k) => (
          <div key={k} className={`card hoverable insight ${String(i.severity).toLowerCase()}`}>
            <div className="row"><SeverityBadge severity={i.severity} /><span className="muted">{i.category}</span></div>
            <h3 style={{ marginTop: 8 }}>{i.finding}</h3>
            {i.evidence && <p><b>Evidence:</b> {i.evidence}</p>}
            {i.action && <p><b>What to do:</b> {i.action}</p>}
          </div>
        ))}
      </div>
    </DataState>
  );
}
