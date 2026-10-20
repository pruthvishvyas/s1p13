import { useMemo, useState } from 'react';
import { useAnomalies } from '../../hooks/understand/useAnomalies';
import { validateAnomalies } from '../../utils/dataValidator';
import { DataState } from '../shared/DataState';
import { F } from '../../utils/fields';
import { fmtCurrency } from '../../utils/formatters';

export function AnomalyTable() {
  const { data: raw, loading, error } = useAnomalies();
  const { valid, data } = validateAnomalies(raw);
  const [dir, setDir] = useState('desc');
  const rows = useMemo(() => [...data].sort((a, b) => (dir === 'desc' ? F.arr(b) - F.arr(a) : F.arr(a) - F.arr(b))), [data, dir]);
  return (
    <DataState loading={loading} error={error} valid={valid} message="No anomaly data available yet." height={200}>
      {rows.length === 0 ? (
        <div className="card">No unusual accounts were detected in the latest run.</div>
      ) : (
        <div className="card table-wrap">
          <table className="data">
            <thead>
              <tr><th>Account</th><th>Company</th><th className="num" onClick={() => setDir(dir === 'desc' ? 'asc' : 'desc')}>ARR {dir === 'desc' ? '\u25BC' : '\u25B2'}</th><th>Why it stands out</th></tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={F.id(r) + i}>
                  <td>{F.id(r)}</td><td>{F.company(r)}</td><td className="num">{fmtCurrency(F.arr(r))}</td><td>{r.anomaly_reason || r.reason || '\u2014'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </DataState>
  );
}
