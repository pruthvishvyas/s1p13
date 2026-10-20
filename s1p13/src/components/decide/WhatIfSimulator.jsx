import { useMemo, useState } from 'react';
import { useSimulationIndex, useSimulations } from '../../hooks/decide/useSimulations';
import { validateSimulation } from '../../utils/dataValidator';
import { DataState } from '../shared/DataState';
import { ChartRenderer } from '../understand/ChartPanel';
import { fmtOutput, titleCase } from '../../utils/formatters';

const NICE = {
  price_change_impact: 'Price change', retention_campaign_roi: 'Retention campaign', discount_policy_impact: 'Discount cap', channel_budget_shift: 'Acquisition budget shift'
};

function SimPanel({ sim }) {
  const results = sim.results;
  const keys = Object.keys(results[0].input);
  const values = useMemo(() => Object.fromEntries(keys.map((k) => [k, Array.from(new Set(results.map((r) => r.input[k])))])), [results]);
  const [sel, setSel] = useState(() => ({ ...results[0].input }));
  const outKeys = Object.keys(results[0].outputs);
  const [metric, setMetric] = useState(outKeys[0]);
  const match = results.find((r) => keys.every((k) => String(r.input[k]) === String(sel[k])));
  const series = results.filter((r) => keys.slice(1).every((k) => String(r.input[k]) === String(sel[k])));
  const chart = { type: 'bar', x: series.map((r) => String(r.input[keys[0]])), y: series.map((r) => r.outputs[metric]) };
  return (
    <div className="stack">
      <div className="card">
        <div className="card-title">Choose your scenario</div>
        <div className="grid-3">
          {keys.map((k) => {
            const vs = values[k];
            const numeric = vs.every((v) => typeof v === 'number');
            const idx = Math.max(0, vs.findIndex((v) => String(v) === String(sel[k])));
            return (
              <label className="field" key={k}>{titleCase(k)}: <b>{String(sel[k])}</b>
                {numeric && vs.length > 1 ? (
                  <input type="range" min={0} max={vs.length - 1} step={1} value={idx} onChange={(e) => setSel({ ...sel, [k]: vs[Number(e.target.value)] })} />
                ) : (
                  <select value={String(sel[k])} onChange={(e) => setSel({ ...sel, [k]: vs.find((v) => String(v) === e.target.value) })}>
                    {vs.map((v) => <option key={String(v)} value={String(v)}>{String(v)}</option>)}
                  </select>
                )}
              </label>
            );
          })}
        </div>
      </div>
      {match && (
        <div className="grid-kpi">
          {Object.entries(match.outputs).map(([k, v]) => (
            <div key={k} className="card hoverable kpi-card"><div className="kpi-label">{titleCase(k)}</div><div className="kpi-value">{fmtOutput(k, v)}</div></div>
          ))}
        </div>
      )}
      <div className="card">
        <div className="row"><div className="card-title" style={{ margin: 0 }}>Effect across {titleCase(keys[0])}</div>
          <select value={metric} onChange={(e) => setMetric(e.target.value)}>{outKeys.map((k) => <option key={k} value={k}>{titleCase(k)}</option>)}</select></div>
        <ChartRenderer chart={chart} />
      </div>
      <div className="card">
        <div className="card-title">Assumptions behind these numbers</div>
        <ul>{(sim.assumptions || []).map((a, i) => <li key={i}>{a}</li>)}</ul>
      </div>
    </div>
  );
}

export function WhatIfSimulator() {
  const { data: idx, loading, error } = useSimulationIndex();
  const names = Array.isArray(idx && idx.simulations) ? idx.simulations : [];
  const [name, setName] = useState(null);
  const active = name || names[0];
  const { data: raw, loading: l2, error: e2 } = useSimulations(active);
  const { valid, data, error: ve } = validateSimulation(raw);
  return (
    <DataState loading={loading} error={error} valid={names.length > 0} message="No simulations available yet." height={200}>
      <div className="chips">
        {names.map((n) => <button key={n} className={'chip' + (n === active ? ' active' : '')} onClick={() => setName(n)}>{NICE[n] || titleCase(n)}</button>)}
      </div>
      <DataState loading={l2} error={e2} valid={valid} detail={ve} message="This simulation has no usable results." height={200}>
        {data && <SimPanel key={active} sim={data} />}
      </DataState>
    </DataState>
  );
}
