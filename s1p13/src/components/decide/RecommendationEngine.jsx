import { useMemo, useState, Fragment } from 'react';
import { useRecommendations } from '../../hooks/decide/useRecommendations';
import { useData } from '../../hooks/useData';
import { PATHS } from '../../utils/contract';
import { validateRecommendations } from '../../utils/dataValidator';
import { DataState } from '../shared/DataState';
import { useTerm } from '../shared/TerminologyProvider';
import { priorityClass } from '../../utils/colors';
import { F } from '../../utils/fields';
import { fmtCurrency, fmtProb } from '../../utils/formatters';

export function RecommendationEngine() {
  const term = useTerm();
  const { data: raw, loading, error } = useRecommendations();
  const { data: summary } = useData(PATHS.summary);
  const { valid, data, error: ve } = validateRecommendations(raw);
  const [prio, setPrio] = useState('ALL');
  const [q, setQ] = useState('');
  const [open, setOpen] = useState(null);
  const [copied, setCopied] = useState(false);
  const rows = useMemo(() => data
    .filter((r) => (prio === 'ALL' || r.priority === prio) && (!q || (F.company(r) + F.id(r)).toLowerCase().includes(q.toLowerCase())))
    .sort((a, b) => F.risk(b) - F.risk(a)), [data, prio, q]);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(rows.map((r) => [F.id(r), F.company(r), r.priority, Math.round(F.risk(r)), r.recommendation].join('\t')).join('\n'));
      setCopied(true); setTimeout(() => setCopied(false), 1500);
    } catch { setCopied(false); }
  };
  return (
    <DataState loading={loading} error={error} valid={valid} detail={ve} message="No recommendations available yet." height={200} count={2}>
      <div className="stack">
        {summary && summary.P1_P2_arr_at_risk !== undefined && (
          <div className="card kpi-card danger"><div className="kpi-label">ARR at risk in urgent (P1 + P2) {term('customer', { plural: true }).toLowerCase()}</div><div className="kpi-value">{fmtCurrency(summary.P1_P2_arr_at_risk)}</div></div>
        )}
        <div className="row">
          {['ALL', 'P1', 'P2', 'P3', 'P4'].map((p) => <button key={p} className={'chip' + (prio === p ? ' active' : '')} onClick={() => setPrio(p)}>{p}</button>)}
          <input placeholder="Search company or ID" value={q} onChange={(e) => setQ(e.target.value)} />
          <button className="btn ghost" onClick={copy}>{copied ? 'Copied' : 'Copy list'}</button>
        </div>
        <div className="card table-wrap">
          <table className="data">
            <thead><tr><th>Priority</th><th>{term('customer')}</th><th>{term('product')}</th><th className="num">Churn risk</th><th className="num">ARR</th><th className="num">ARR at risk</th><th>What to do</th></tr></thead>
            <tbody>
              {rows.map((r, i) => (
                <Fragment key={F.id(r) + i}>
                  <tr className="clickable" onClick={() => setOpen(open === i ? null : i)}>
                    <td><span className={`badge ${priorityClass(r.priority)}`}>{r.priority}</span></td>
                    <td>{F.company(r)}<div className="muted">{F.id(r)}</div></td><td>{F.plan(r)}</td>
                    <td className="num">{fmtProb(F.prob(r))}</td><td className="num">{fmtCurrency(F.arr(r))}</td><td className="num">{fmtCurrency(F.risk(r))}</td>
                    <td>{r.recommendation}</td>
                  </tr>
                  {open === i && (
                    <tr><td colSpan={7}><b>Why:</b> {r.drivers || 'No single dominant driver.'}{r.alerts ? <div className="muted">Alerts: {r.alerts}</div> : null}{r.segment ? <div className="muted">Segment: {r.segment}</div> : null}</td></tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
          {rows.length === 0 && <p className="muted">No accounts match the current filter.</p>}
        </div>
        <p className="muted footnote">The list shows the top accounts exported by the pipeline (up to 200), ordered by ARR at risk. Click a row to see why.</p>
      </div>
    </DataState>
  );
}
