import { useState, useMemo } from 'react';
import { ResponsiveContainer, ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip } from 'recharts';
import { useForecast, usePrediction } from '../../hooks/monitor/useForecast';
import { validateForecast } from '../../utils/dataValidator';
import { DataState } from '../shared/DataState';
import { ErrorBoundary } from '../shared/ErrorBoundary';
import { fmtCurrency, fmtNum, fmtPercent } from '../../utils/formatters';

const tick = { fill: 'var(--color-text-secondary)', fontSize: 12 };
const tip = { background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 8, color: 'var(--color-text-primary)' };

export function Forecaster() {
  const { data: raw, loading, error } = useForecast();
  const { valid, data, error: ve } = validateForecast(raw);
  const monthly = data ? data.monthly : [];
  const meta = data ? data.meta : {};
  const [months, setMonths] = useState(3);
  const { loading: pl, error: pe, result, predict } = usePrediction(monthly);
  const rows = useMemo(() => monthly.map((m) => ({
    month: m.month, base: m.mrr_base, band: [Math.min(m.mrr_worst, m.mrr_base), Math.max(m.mrr_best, m.mrr_base)]
  })), [monthly]);
  const lo = monthly.length ? Math.min(...monthly.map((m) => Math.min(m.mrr_worst, m.mrr_base))) : 0;
  const hi = monthly.length ? Math.max(...monthly.map((m) => Math.max(m.mrr_best, m.mrr_base))) : 1;
  const last = monthly[monthly.length - 1];
  const bt = meta && meta.backtest;
  return (
    <DataState loading={loading} error={error} valid={valid} detail={ve} message="No forecast available yet." height={350}>
      <div className="stack">
        <div className="grid-kpi">
          <div className="card kpi-card"><div className="kpi-label">MRR now</div><div className="kpi-value">{fmtCurrency(monthly[0] && monthly[0].mrr_base)}</div></div>
          <div className="card kpi-card"><div className="kpi-label">Expected MRR in {last && last.month_index} months</div><div className="kpi-value">{fmtCurrency(last && last.mrr_base)}</div></div>
          <div className="card kpi-card"><div className="kpi-label">Change if nothing is done</div><div className="kpi-value">{fmtPercent(last && last.pct_vs_now)}</div></div>
          <div className="card kpi-card"><div className="kpi-label">Forecast reliability</div><div className="kpi-value">{String(meta.label || 'indicative')}</div></div>
        </div>
        <div className="card">
          <div className="card-title">Recurring revenue run-off of today's active base</div>
          <ErrorBoundary>
            <ResponsiveContainer width="100%" height={350}>
              <ComposedChart data={rows} margin={{ top: 10, right: 20, bottom: 20, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                <XAxis dataKey="month" tick={tick} />
                <YAxis tick={tick} domain={[Math.floor(lo * 0.97), Math.ceil(hi * 1.02)]} tickFormatter={(v) => fmtCurrency(v, true)} />
                <Tooltip contentStyle={tip} formatter={(v) => (Array.isArray(v) ? fmtCurrency(v[0]) + ' to ' + fmtCurrency(v[1]) : fmtCurrency(v))} />
                <Area type="monotone" dataKey="band" name="Likely range" stroke="none" fill="var(--color-accent)" fillOpacity={0.18} />
                <Line type="monotone" dataKey="base" name="Expected" stroke="var(--color-accent)" strokeWidth={2} dot />
              </ComposedChart>
            </ResponsiveContainer>
          </ErrorBoundary>
        </div>
        <div className="card">
          <div className="card-title">Ask the forecast</div>
          <div className="row">
            <label className="field">Months ahead<input type="number" min={0} max={24} value={months} onChange={(e) => setMonths(e.target.value)} /></label>
            <button className="btn" disabled={pl} onClick={() => predict(months)}>{pl ? 'Working...' : 'Get forecast'}</button>
          </div>
          {pe && <p style={{ color: 'var(--color-danger)' }}>{pe}</p>}
          {result && (
            <p>Expected MRR around month {result.nearest_key}: <b>{fmtCurrency(result.prediction)}</b>
              {result.range_low != null && result.range_high != null ? <> (likely {fmtCurrency(result.range_low)} to {fmtCurrency(result.range_high)})</> : null}
              <span className="muted"> {'\u00B7'} source: {result.source}</span></p>
          )}
        </div>
        <div className="card">
          <div className="card-title">How reliable is this?</div>
          {bt && bt.available ? (
            <p>When we held out the last {bt.months_held_out} months and predicted them, the retained-revenue estimate was off by {fmtNum(bt.mape_pct, 1)}%. Label: <b>{bt.label}</b>.</p>
          ) : (
            <p>There was not enough history to back-test, so treat this forecast as <b>indicative</b>.</p>
          )}
          {meta.method && <p className="muted footnote">{meta.method}</p>}
        </div>
      </div>
    </DataState>
  );
}
