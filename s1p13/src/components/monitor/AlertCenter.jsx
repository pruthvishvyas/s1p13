import { useAlerts } from '../../hooks/monitor/useAlerts';
import { validateAlerts } from '../../utils/dataValidator';
import { DataState } from '../shared/DataState';
import { SeverityBadge } from '../shared/SeverityBadge';
import { SEVERITY_RANK } from '../../utils/colors';

export function AlertCenter() {
  const { data: raw, loading, error } = useAlerts();
  const { valid, data, error: ve } = validateAlerts(raw);
  const rows = [...data].sort((a, b) => (SEVERITY_RANK[String(a.severity).toLowerCase()] ?? 9) - (SEVERITY_RANK[String(b.severity).toLowerCase()] ?? 9));
  return (
    <DataState loading={loading} error={error} valid={valid} detail={ve} message="No alert data available yet." height={100} count={3}>
      {rows.length === 0 ? <div className="card">All clear: no alerts were raised in the latest run.</div> : (
        <div className="stack">
          {rows.map((a, i) => (
            <div key={i} className={`card hoverable insight ${String(a.severity).toLowerCase() === 'critical' ? 'high' : String(a.severity).toLowerCase()}`}>
              <div className="row"><SeverityBadge severity={a.severity} /><span className="muted">{String(a.type || '').replace(/_/g, ' ')}</span></div>
              <h3 style={{ marginTop: 8 }}>{a.message}</h3>
              {Array.isArray(a.accounts) && a.accounts.length > 0 && <p className="muted">Accounts: {a.accounts.join(', ')}</p>}
            </div>
          ))}
        </div>
      )}
    </DataState>
  );
}
