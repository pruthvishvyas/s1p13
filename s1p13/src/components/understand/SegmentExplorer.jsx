import { useState } from 'react';
import { useSegments } from '../../hooks/understand/useSegments';
import { useRecommendations } from '../../hooks/decide/useRecommendations';
import { validateSegments, validateRecommendations } from '../../utils/dataValidator';
import { DataState } from '../shared/DataState';
import { ChartRenderer } from './ChartPanel';
import { useTerm } from '../shared/TerminologyProvider';
import { F } from '../../utils/fields';
import { fmtCurrency, fmtInt, fmtProb, fmtPercent } from '../../utils/formatters';

export function SegmentExplorer() {
  const term = useTerm();
  const { data: raw, loading, error } = useSegments();
  const { data: recRaw } = useRecommendations();
  const { valid, data, meta, error: ve } = validateSegments(raw);
  const recs = validateRecommendations(recRaw).data;
  const [sel, setSel] = useState(null);
  const members = sel ? recs.filter((r) => r.segment === sel).sort((a, b) => F.risk(b) - F.risk(a)).slice(0, 10) : [];
  return (
    <DataState loading={loading} error={error} valid={valid} detail={ve} message={`No ${term('customer').toLowerCase()} segments available yet.`} height={160} count={3}>
      <div className="stack">
        <div className="grid-3">
          {data.map((s) => (
            <div key={s.segment} className={'card hoverable' + (sel === s.segment ? ' selected' : '')} style={{ cursor: 'pointer', outline: sel === s.segment ? '2px solid var(--color-accent)' : 'none' }} onClick={() => setSel(sel === s.segment ? null : s.segment)}>
              <div className="card-title">{s.segment}</div>
              <div className="muted">{fmtInt(s.n)} {term('customer', { plural: true }).toLowerCase()}{s.arr_share_pct !== undefined ? ` \u00B7 ${fmtPercent(s.arr_share_pct, 0)} of ARR` : ''}</div>
              {s.avg_churn_prob !== undefined && <div>Average churn risk: <b>{fmtProb(s.avg_churn_prob)}</b></div>}
              {s.arr !== undefined && <div>ARR: <b>{fmtCurrency(s.arr)}</b></div>}
              {s.traits && <p className="muted" style={{ fontSize: 'var(--fs-sm)' }}>{String(s.traits).split(' | ').map((t, i) => <span key={i}>{'\u2022'} {t}<br /></span>)}</p>}
            </div>
          ))}
        </div>
        <div className="card">
          <div className="card-title">ARR by segment</div>
          <ChartRenderer chart={{ type: 'bar', x: data.map((s) => s.segment), y: data.map((s) => s.arr ?? s.n) }} />
          {meta && meta.silhouette !== undefined && <p className="muted footnote">Grouping quality (silhouette): {Number(meta.silhouette).toFixed(2)}{meta.fallback_k3 ? ' - simple 3-group fallback used' : ''}</p>}
        </div>
        {sel && (
          <div className="card table-wrap">
            <div className="card-title">Highest-risk accounts in {sel}</div>
            {members.length === 0 ? <p className="muted">None of the top accounts in the save list belong to this segment.</p> : (
              <table className="data"><thead><tr><th>Account</th><th>Company</th><th className="num">ARR at risk</th><th>Action</th></tr></thead>
                <tbody>{members.map((r, i) => <tr key={F.id(r) + i}><td>{F.id(r)}</td><td>{F.company(r)}</td><td className="num">{fmtCurrency(F.risk(r))}</td><td>{r.recommendation}</td></tr>)}</tbody></table>
            )}
          </div>
        )}
      </div>
    </DataState>
  );
}
