import { useMemo, useState } from 'react';
import {
  ResponsiveContainer, BarChart, Bar, LineChart, Line, ScatterChart, Scatter, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip
} from 'recharts';
import { useChartIndex, useChart } from '../../hooks/understand/useCharts';
import { validateChartData } from '../../utils/dataValidator';
import { DataState } from '../shared/DataState';
import { EmptyState } from '../shared/EmptyState';
import { SkeletonCard } from '../shared/SkeletonCard';
import { ErrorBoundary } from '../shared/ErrorBoundary';
import { fmtNum, titleCase } from '../../utils/formatters';

const tick = { fill: 'var(--color-text-secondary)', fontSize: 12 };
const tip = { background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 8, color: 'var(--color-text-primary)' };
export const PIE_COLORS = ['var(--chart-1)', 'var(--chart-2)', 'var(--chart-3)', 'var(--chart-4)', 'var(--chart-5)', 'var(--chart-6)'];

export function chartGroup(name) {
  if (/^(mrr_waterfall|cohort_)/.test(name)) return 'Revenue';
  if (/^churn_/.test(name)) return 'Churn';
  if (/^channel_/.test(name)) return 'Channels';
  if (/^discount_/.test(name)) return 'Pricing';
  if (/^survival_/.test(name)) return 'Retention';
  if (/^(pr_curve|calibration_curve|permutation_importance)/.test(name)) return 'Model';
  if (/^correlation/.test(name)) return 'Signals';
  return 'Other';
}

function heatColor(v) {
  const n = Number(v);
  if (!Number.isFinite(n)) return 'var(--color-surface-2)';
  const p = Math.round(Math.min(Math.abs(n), 1) * 80);
  return `color-mix(in srgb, ${n >= 0 ? 'var(--color-danger)' : 'var(--color-accent)'} ${p}%, var(--color-surface))`;
}

function Heatmap({ rows }) {
  const pairs = rows.map((r) => ({ parts: String(r.x).split(' | '), v: r.y }));
  const names = Array.from(new Set(pairs.map((p) => p.parts[0])));
  const lookup = {};
  pairs.forEach((p) => { lookup[p.parts[0] + '||' + p.parts[1]] = p.v; });
  return (
    <div className="table-wrap">
      <div className="heat" style={{ gridTemplateColumns: `140px repeat(${names.length}, minmax(44px, 1fr))` }}>
        <div />
        {names.map((n) => <div key={n} className="heat-label" title={n}>{n}</div>)}
        {names.map((r) => (
          <div key={r} style={{ display: 'contents' }}>
            <div className="heat-label" title={r}>{r}</div>
            {names.map((c) => {
              const v = lookup[r + '||' + c];
              return <div key={r + c} className="heat-cell" style={{ background: heatColor(v) }} title={`${r} / ${c}: ${fmtNum(v)}`}>{fmtNum(v, 1)}</div>;
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

export function ChartRenderer({ chart, onSelect, selected, accent = 'var(--color-accent)' }) {
  const { valid, data: c, error } = validateChartData(chart);
  if (!valid) return <EmptyState message={error} />;
  const rows = c.x.map((x, i) => ({ x: String(x), y: c.y[i] === undefined ? null : c.y[i] }));
  const fmt = (v) => fmtNum(v);

  if (c.type === 'heatmap') return <Heatmap rows={rows} />;

  if (c.type === 'line') {
    return (
      <ResponsiveContainer width="100%" height={350}>
        <LineChart data={rows} margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis dataKey="x" tick={tick} />
          <YAxis tick={tick} />
          <Tooltip contentStyle={tip} formatter={fmt} />
          <Line type="monotone" dataKey="y" stroke={accent} strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    );
  }

  if (c.type === 'scatter') {
    const pts = rows.map((r, i) => ({ x: Number.isFinite(Number(r.x)) ? Number(r.x) : i, y: r.y }));
    return (
      <ResponsiveContainer width="100%" height={350}>
        <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis type="number" dataKey="x" tick={tick} />
          <YAxis type="number" dataKey="y" tick={tick} />
          <Tooltip contentStyle={tip} formatter={fmt} />
          <Scatter data={pts} fill={accent} />
        </ScatterChart>
      </ResponsiveContainer>
    );
  }

  if (c.type === 'pie' || c.type === 'doughnut') {
    return (
      <ResponsiveContainer width="100%" height={350}>
        <PieChart>
          <Pie data={rows} dataKey="y" nameKey="x" cx="50%" cy="50%" innerRadius={c.type === 'doughnut' ? '50%' : 0} outerRadius="70%"
            label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`} labelLine>
            {rows.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
          </Pie>
          <Tooltip contentStyle={tip} />
        </PieChart>
      </ResponsiveContainer>
    );
  }

  // bar / histogram (default)
  const horizontal = c.horizontal ?? (rows.length > 6 || rows.some((r) => r.x.length > 14));
  const height = horizontal ? Math.max(350, rows.length * 28 + 60) : 350;
  const pick = (d) => { if (onSelect) onSelect(d && d.payload ? d.payload.x : d && d.x); };
  const bar = (
    <Bar dataKey="y" fill={accent} radius={horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0]} onClick={pick} cursor={onSelect ? 'pointer' : 'default'}>
      {rows.map((r, i) => <Cell key={i} fill={accent} fillOpacity={selected && selected !== r.x ? 0.3 : 1} />)}
    </Bar>
  );
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={rows} layout={horizontal ? 'vertical' : 'horizontal'} margin={{ top: 10, right: 20, bottom: horizontal ? 10 : 40, left: 10 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
        {horizontal ? (
          <>
            <YAxis type="category" dataKey="x" tick={{ ...tick, fontSize: 11 }} width={130} />
            <XAxis type="number" tick={tick} />
          </>
        ) : (
          <>
            <XAxis dataKey="x" tick={tick} interval={0} angle={rows.length > 4 ? -25 : 0} textAnchor={rows.length > 4 ? 'end' : 'middle'} />
            <YAxis tick={tick} />
          </>
        )}
        <Tooltip contentStyle={tip} formatter={fmt} />
        {bar}
      </BarChart>
    </ResponsiveContainer>
  );
}

function ChartCard({ name }) {
  const { data, loading, error } = useChart(name);
  return (
    <div className={'card' + (name === 'correlation_heatmap' ? ' wide' : '')}>
      <div className="card-title">{(data && data.title) || titleCase(name)}</div>
      {loading ? <SkeletonCard height={350} />
        : error ? <EmptyState message="This chart could not be loaded." detail={error} />
          : <ErrorBoundary><ChartRenderer chart={data} /></ErrorBoundary>}
    </div>
  );
}

export function ChartPanel() {
  const { data: idx, loading, error } = useChartIndex();
  const [group, setGroup] = useState('All');
  const names = useMemo(() => (Array.isArray(idx && idx.charts) ? idx.charts.filter((n) => !n.startsWith('forecast_')) : []), [idx]);
  const groups = useMemo(() => ['All', ...Array.from(new Set(names.map(chartGroup)))], [names]);
  const shown = names.filter((n) => group === 'All' || chartGroup(n) === group);
  return (
    <DataState loading={loading} error={error} valid={names.length > 0} message="No charts available yet." height={350} count={2}>
      <div className="chips">
        {groups.map((g) => (
          <button key={g} className={'chip' + (g === group ? ' active' : '')} onClick={() => setGroup(g)}>{g}</button>
        ))}
      </div>
      <div className="grid-2">
        {shown.map((n) => <ChartCard key={n} name={n} />)}
      </div>
    </DataState>
  );
}
