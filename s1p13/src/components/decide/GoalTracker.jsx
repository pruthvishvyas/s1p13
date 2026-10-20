import { useGoals } from '../../hooks/decide/useGoals';
import { useData } from '../../hooks/useData';
import { PATHS } from '../../utils/contract';
import { DataState } from '../shared/DataState';
import { titleCase, fmtNum } from '../../utils/formatters';

export function GoalTracker() {
  const { goals, loading, error, overrides, setOverride } = useGoals();
  const { data: prog } = useData(PATHS.goalProgress);
  const entries = goals && typeof goals === 'object' ? Object.entries(goals) : [];
  const actual = (k) => {
    if (!prog) return null;
    if (k === 'grr_target') return prog.grr && prog.grr.actual_pct;
    if (k === 'nrr_target') return prog.nrr && prog.nrr.actual_pct;
    if (k === 'mrr_target') return prog.mrr && prog.mrr.actual;
    if (k === 'at_risk_arr_share') return prog.high_risk_arr_share_pct && prog.high_risk_arr_share_pct.actual;
    return null;
  };
  return (
    <DataState loading={loading} error={error} valid={entries.length > 0} message="No goals configured yet." height={160}>
      <div className="card table-wrap">
        <table className="data">
          <thead><tr><th>Goal</th><th>Unit</th><th className="num">Pipeline value</th><th>Your target</th><th className="num">Today</th></tr></thead>
          <tbody>
            {entries.map(([k, g]) => (
              <tr key={k}>
                <td>{titleCase(k)}<div className="muted">{g.description || ''}</div></td><td>{g.unit}</td>
                <td className="num">{g.value === null || g.value === undefined ? '\u2014' : fmtNum(g.value)}</td>
                <td><input type="number" style={{ width: 110 }} value={overrides[k] !== undefined ? overrides[k] : ''} placeholder={g.value === null ? 'set target' : String(g.value)} onChange={(e) => setOverride(k, e.target.value)} /></td>
                <td className="num">{actual(k) === null || actual(k) === undefined ? '\u2014' : fmtNum(actual(k), 1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted footnote">Targets you type are saved in this browser only. To make a target permanent for the pipeline, edit config/goals.json and rerun it.</p>
    </DataState>
  );
}
