import { useCallback, useState } from 'react';
import { useData } from '../useData';
import { PATHS } from '../../utils/contract';

export function useForecast() {
  return useData(PATHS.forecast);
}

function localLookup(monthly, input) {
  if (!Array.isArray(monthly) || monthly.length === 0) return null;
  const nearest = monthly.reduce((a, b) => (Math.abs(b.month_index - input) < Math.abs(a.month_index - input) ? b : a));
  return {
    prediction: nearest.mrr_base, range_low: nearest.mrr_worst, range_high: nearest.mrr_best,
    confidence: null, input_received: input, nearest_key: nearest.month_index, source: 'local data file'
  };
}

// Calls the Worker's POST /api; falls back to the data file when the Worker is not reachable (local dev).
export function usePrediction(monthly) {
  const [state, setState] = useState({ loading: false, error: null, result: null });
  const predict = useCallback(async (value) => {
    const input = Number(value);
    if (!Number.isFinite(input)) { setState({ loading: false, error: 'Enter a number of months.', result: null }); return; }
    setState({ loading: true, error: null, result: null });
    try {
      const res = await fetch('/api', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ input: Number(input) }) });
      const text = await res.text();
      let body = null;
      try { body = JSON.parse(text); } catch { body = null; }
      if (!res.ok) {
        if (body && body.error) throw new Error(body.error);
        throw new Error(`Forecast service returned HTTP ${res.status}`);
      }
      if (!body || body.prediction === undefined || body.prediction === null) throw new Error('Forecast response had no prediction.');
      setState({ loading: false, error: null, result: { ...body, source: 'forecast service' } });
    } catch (e) {
      const local = localLookup(monthly, input);
      if (local && /HTTP 404|Unexpected|Failed to fetch|NetworkError|Forecast service returned HTTP 404/i.test(String(e.message))) {
        setState({ loading: false, error: null, result: local });
      } else {
        setState({ loading: false, error: e.message, result: null });
      }
    }
  }, [monthly]);
  return { ...state, predict };
}
