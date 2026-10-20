import { useData } from '../../hooks/useData';
import { useGoals } from '../../hooks/decide/useGoals';
import { PATHS } from '../../utils/contract';
import { validateGoalProgress } from '../../utils/dataValidator';
import { DataState } from '../shared/DataState';
import { fmtCurrency, fmtPercent } from '../../utils/formatters';

function Bar({ label, actual, target, text, higherIsBetter = true }) {
  const have = actual !== null && actual !== undefined && target !== null && target !== undefined && Number(target) > 0;
  const pct = have ? Math.max(0, Math.min(100, (Number(actual) / Number(target)) * 100)) : 0;
  const ok = have ? (higherIsBetter ? Number(actual) >= Number(target) : Number(actual) <= Number(target)) : null;
  return (
    <div className="card">
      <div className="row" style={{ justifyContent: 'space-between' }}><b>{label}</b><span className="muted">{text}</span></div>
      <div className="progress" style={{ marginTop: 8 }}><span className={ok === null ? '' : ok ? 'good' : 'bad'} style={{ width: pct + '%' }} /></div>
      <p className="muted footnote">{ok === null ? 'No target set yet - add one in Goals & targets.' : ok ? 'On target' : 'Off target'}</p>
    </div>
  );
}

export function GoalProgress() {
  const { data: raw, loading, error } = useData(PATHS.goalProgress);
  const { target } = useGoals();
  const { valid, data: p, error: ve } = validateGoalProgress(raw);
  return (
    <DataState loading={loading} error={error} valid={valid} detail={ve} message="No goal progress available yet." height={120} count={3}>
      {p && (
        <div className="stack">
          <Bar label="Gross revenue retention" actual={p.grr && p.grr.actual_pct} target={target('grr_target')} text={`${fmtPercent(p.grr && p.grr.actual_pct)} vs target ${fmtPercent(target('grr_target'), 0)}`} />
          <Bar label="Net revenue retention" actual={p.nrr && p.nrr.actual_pct} target={target('nrr_target')} text={`${fmtPercent(p.nrr && p.nrr.actual_pct)} vs target ${fmtPercent(target('nrr_target'), 0)}`} />
          <Bar label="Share of ARR in high-risk accounts (lower is better)" higherIsBetter={false} actual={p.high_risk_arr_share_pct && p.high_risk_arr_share_pct.actual} target={target('at_risk_arr_share')} text={`${fmtPercent(p.high_risk_arr_share_pct && p.high_risk_arr_share_pct.actual)} vs limit ${fmtPercent(target('at_risk_arr_share'), 0)}`} />
          <Bar label="Monthly recurring revenue" actual={p.mrr && p.mrr.actual} target={target('mrr_target')} text={`${fmtCurrency(p.mrr && p.mrr.actual)} vs target ${target('mrr_target') ? fmtCurrency(target('mrr_target')) : 'not set'}`} />
          {p.basis && <p className="muted footnote">Basis: {p.basis}</p>}
        </div>
      )}
    </DataState>
  );
}
