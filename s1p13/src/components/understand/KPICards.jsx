import { useKPIs } from '../../hooks/understand/useKPIs';
import { validateKPIs } from '../../utils/dataValidator';
import { DataState } from '../shared/DataState';
import { useTerm } from '../shared/TerminologyProvider';
import { kpiMeta } from '../../utils/terminology';
import { formatKPI } from '../../utils/formatters';

export function KPICards() {
  const term = useTerm();
  const { data: raw, loading, error } = useKPIs();
  const { valid, data, error: valError } = validateKPIs(raw, kpiMeta(term));
  const note = raw && !Array.isArray(raw) ? raw.snapshot_note : null;
  return (
    <DataState loading={loading} error={error} valid={valid} detail={valError}
      message={`No ${term('revenue')} data available yet.`} height={120} count={4}>
      <div className="grid-kpi">
        {data.map((k) => (
          <div key={k.key} className={`card hoverable kpi-card ${k.tone || ''}`}>
            <div className="kpi-label">{k.label}</div>
            <div className="kpi-value">{formatKPI(k)}</div>
          </div>
        ))}
      </div>
      {note && <p className="muted footnote">{note}</p>}
    </DataState>
  );
}
