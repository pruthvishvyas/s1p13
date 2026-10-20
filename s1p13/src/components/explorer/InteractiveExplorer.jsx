import { useContext, useMemo, useState } from 'react';
import { ExplorerContext } from '../../context/ExplorerContext';
import { useRecommendations } from '../../hooks/decide/useRecommendations';
import { validateRecommendations } from '../../utils/dataValidator';
import { DataState } from '../shared/DataState';
import { EmptyState } from '../shared/EmptyState';
import { ErrorBoundary } from '../shared/ErrorBoundary';
import { ChartRenderer } from '../understand/ChartPanel';
import { FilterBar } from './FilterBar';
import { DrillDownPanel } from './DrillDownPanel';
import { F } from '../../utils/fields';
import { fmtCurrency, fmtInt, fmtProb, fmtNum, titleCase } from '../../utils/formatters';

const EXCLUDE = /(^id$|_id$|^customer|company|name|recommend|driver|alert|reason|trait)/i;

function detectDims(rows) {
  const keys = Array.from(new Set(rows.slice(0, 50).flatMap((r) => Object.keys(r))));
  return keys.filter((k) => {
    if (EXCLUDE.test(k)) return false;
    const vals = rows.map((r) => r[k]).filter((v) => v !== null && v !== undefined && v !== '');
    if (vals.length === 0 || !vals.every((v) => typeof v === 'string')) return false;
    const n = new Set(vals).size;
    return n >= 2 && n <= 30;
  });
}
function detectMetrics(rows) {
  const keys = Array.from(new Set(rows.slice(0, 50).flatMap((r) => Object.keys(r))));
  const nums = keys.filter((k) => rows.some((r) => typeof r[k] === 'number'));
  return [{ key: '__count', label: 'Accounts', agg: 'count' }, ...nums.map((k) => ({ key: k, label: titleCase(k), agg: /prob|pct|rate|score/i.test(k) ? 'avg' : 'sum' }))];
}
function detectDate(rows) {
  const keys = Array.from(new Set(rows.slice(0, 50).flatMap((r) => Object.keys(r))));
  return keys.find((k) => /date|month/i.test(k) && rows.some((r) => typeof r[k] === 'string' && !Number.isNaN(Date.parse(r[k])))) || null;
}
function aggregate(rows, dim, metric) {
  const map = new Map();
  rows.forEach((r) => {
    const g = String(r[dim] ?? 'Unknown');
    const cur = map.get(g) || { sum: 0, n: 0 };
    cur.n += 1; cur.sum += metric.agg === 'count' ? 1 : Number(r[metric.key]) || 0;
    map.set(g, cur);
  });
  return Array.from(map, ([x, v]) => ({ x, y: metric.agg === 'avg' ? v.sum / v.n : v.sum })).sort((a, b) => b.y - a.y);
}

function ExplorerBody({ rows }) {
  const { filters, setFilter } = useContext(ExplorerContext);
  const dims = useMemo(() => detectDims(rows), [rows]);
  const metrics = useMemo(() => detectMetrics(rows), [rows]);
  const dateKey = useMemo(() => detectDate(rows), [rows]);
  const [dim, setDim] = useState(dims[0]);
  const [metricKey, setMetricKey] = useState(metrics.find((m) => m.key === 'arr_at_risk') ? 'arr_at_risk' : '__count');
  const [drill, setDrill] = useState(null);
  const [date, setDate] = useState({ from: '', to: '' });
  const [sort, setSort] = useState({ key: 'arr_at_risk', dir: 'desc' });
  const [copied, setCopied] = useState(false);
  const metric = metrics.find((m) => m.key === metricKey) || metrics[0];
  const active = dims.includes(dim) ? dim : dims[0];

  const inDate = (r) => !dateKey || ((!date.from || String(r[dateKey]) >= date.from) && (!date.to || String(r[dateKey]) <= date.to));
  const filteredFor = (exclude) => rows.filter((r) => inDate(r) && Object.entries(filters).every(([d, v]) => d === exclude || String(r[d]) === v));
  const all = filteredFor(null);

  const toggle = (d, v) => {
    if (v === undefined || v === null) return;
    if (filters[d] === v) { setFilter(d, null); setDrill(null); } else { setFilter(d, v); setDrill({ dim: d, value: v }); }
  };
  const chartFor = (d) => { const a = aggregate(filteredFor(d), d, metric); return { type: 'bar', x: a.map((i) => i.x), y: a.map((i) => i.y), horizontal: a.length > 6 }; };
  const others = dims.filter((d) => d !== active).slice(0, 2);

  const sorted = [...all].sort((a, b) => {
    const va = a[sort.key]; const vb = b[sort.key];
    const cmp = typeof va === 'number' && typeof vb === 'number' ? va - vb : String(va ?? '').localeCompare(String(vb ?? ''));
    return sort.dir === 'desc' ? -cmp : cmp;
  }).slice(0, 25);
  const cols = ['priority', 'churn_band', 'segment'].filter((k) => rows.some((r) => r[k] !== undefined));

  const exportSummary = async () => {
    const txt = [
      `Accounts: ${all.length}`, `ARR: ${Math.round(all.reduce((s, r) => s + F.arr(r), 0))}`, `ARR at risk: ${Math.round(all.reduce((s, r) => s + F.risk(r), 0))}`,
      `Filters: ${Object.entries(filters).map(([d, v]) => d + '=' + v).join(', ') || 'none'}`
    ].join('\n');
    try { await navigator.clipboard.writeText(txt); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch { setCopied(false); }
  };

  if (dims.length === 0) return <EmptyState message="No categories found to explore in the exported accounts." />;
  const sortBy = (k) => setSort((s) => ({ key: k, dir: s.key === k && s.dir === 'desc' ? 'asc' : 'desc' }));
  return (
    <div className="stack">
      <FilterBar date={date} setDate={setDate} hasDate={Boolean(dateKey)} onExport={exportSummary} copied={copied} />
      <div className="grid-kpi">
        <div className="card kpi-card"><div className="kpi-label">Accounts in view</div><div className="kpi-value">{fmtInt(all.length)}</div></div>
        <div className="card kpi-card"><div className="kpi-label">ARR</div><div className="kpi-value">{fmtCurrency(all.reduce((s, r) => s + F.arr(r), 0), true)}</div></div>
        <div className="card kpi-card danger"><div className="kpi-label">ARR at risk</div><div className="kpi-value">{fmtCurrency(all.reduce((s, r) => s + F.risk(r), 0), true)}</div></div>
        <div className="card kpi-card"><div className="kpi-label">Average churn risk</div><div className="kpi-value">{fmtProb(all.length ? all.reduce((s, r) => s + F.prob(r), 0) / all.length : 0)}</div></div>
      </div>
      <div className="card">
        <div className="row">
          <label className="field">Group by<select value={active} onChange={(e) => setDim(e.target.value)}>{dims.map((d) => <option key={d} value={d}>{titleCase(d)}</option>)}</select></label>
          <label className="field">Measure<select value={metric.key} onChange={(e) => setMetricKey(e.target.value)}>{metrics.map((m) => <option key={m.key} value={m.key}>{m.label}</option>)}</select></label>
        </div>
        <div className="card-title" style={{ marginTop: 16 }}>{metric.label} by {titleCase(active)} {metric.agg === 'avg' ? '(average)' : ''}</div>
        <ErrorBoundary><ChartRenderer chart={chartFor(active)} onSelect={(v) => toggle(active, v)} selected={filters[active]} /></ErrorBoundary>
      </div>
      <div className="grid-2">
        {others.map((d) => (
          <div className="card" key={d}>
            <div className="card-title">{metric.label} by {titleCase(d)}</div>
            <ErrorBoundary><ChartRenderer chart={chartFor(d)} onSelect={(v) => toggle(d, v)} selected={filters[d]} accent="var(--chart-2)" /></ErrorBoundary>
          </div>
        ))}
      </div>
      <div className="card table-wrap">
        <div className="card-title">Accounts in view (top 25)</div>
        <table className="data">
          <thead><tr>
            <th onClick={() => sortBy('Company')}>Company</th>
            {cols.map((k) => <th key={k} onClick={() => sortBy(k)}>{titleCase(k)}</th>)}
            <th className="num" onClick={() => sortBy('churn_prob')}>Churn risk</th>
            <th className="num" onClick={() => sortBy('ARR_Current')}>ARR</th>
            <th className="num" onClick={() => sortBy('arr_at_risk')}>ARR at risk</th>
          </tr></thead>
          <tbody>
            {sorted.map((r, i) => (
              <tr key={F.id(r) + i}>
                <td>{F.company(r) || F.id(r)}</td>
                {cols.map((k) => <td key={k}>{String(r[k] ?? '')}</td>)}
                <td className="num">{fmtProb(F.prob(r))}</td><td className="num">{fmtCurrency(F.arr(r))}</td><td className="num">{fmtCurrency(F.risk(r))}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {all.length === 0 && <p className="muted">No accounts match the current filters.</p>}
        <p className="muted footnote">Explores the accounts exported in the save list ({fmtNum(rows.length, 0)} accounts).</p>
      </div>
      <DrillDownPanel drill={drill} rows={filteredFor(drill && drill.dim)} onClose={() => setDrill(null)} />
    </div>
  );
}

export function InteractiveExplorer() {
  const { data: raw, loading, error } = useRecommendations();
  const { valid, data, error: ve } = validateRecommendations(raw);
  return (
    <DataState loading={loading} error={error} valid={valid} detail={ve} message="No account data available to explore yet." height={200} count={2}>
      <ExplorerBody rows={data} />
    </DataState>
  );
}
