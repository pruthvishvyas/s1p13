// Each validator returns { valid, data, error } and normalises the pipeline's JSON shapes.
import { titleCase } from './formatters';
import { KPI_ORDER } from './terminology';

const isObj = (x) => x && typeof x === 'object' && !Array.isArray(x);

export function validateKPIs(raw, meta = {}) {
  let items = [];
  if (Array.isArray(raw)) {
    items = raw.filter((k) => k && typeof k.label === 'string' && k.value !== undefined)
      .map((k) => ({ key: k.key ?? k.label, label: k.label, value: k.value, format: k.format, tone: k.tone }));
  } else if (isObj(raw)) {
    items = Object.entries(raw)
      .filter(([k, v]) => k !== 'snapshot_note' && v !== null && v !== undefined && typeof v !== 'object')
      .map(([k, v]) => ({
        key: k,
        label: meta[k]?.label ?? titleCase(k),
        value: v,
        format: meta[k]?.format ?? (typeof v === 'number' ? 'decimal' : 'text'),
        tone: meta[k]?.tone
      }));
    items.sort((a, b) => {
      const ia = KPI_ORDER.indexOf(a.key); const ib = KPI_ORDER.indexOf(b.key);
      return (ia < 0 ? 999 : ia) - (ib < 0 ? 999 : ib);
    });
  } else {
    return { valid: false, data: [], error: 'KPIs must be an object or array' };
  }
  return { valid: items.length > 0, data: items, error: items.length === 0 ? 'No valid KPI entries' : null };
}

export function normalizeChart(raw) {
  if (!isObj(raw)) return null;
  let x; let y;
  if (Array.isArray(raw.x) && Array.isArray(raw.y)) { x = raw.x; y = raw.y; }
  else if (Array.isArray(raw.data)) { x = raw.data.map((d) => d.label); y = raw.data.map((d) => d.value); }
  else return null;
  return { type: raw.type || 'bar', title: raw.title || '', x, y, horizontal: raw.horizontal };
}

export function validateChartData(raw) {
  const c = normalizeChart(raw);
  if (!c) return { valid: false, data: null, error: 'Invalid chart data' };
  if (c.x.length === 0 || c.y.length === 0) return { valid: false, data: null, error: 'Chart has no data points' };
  if (c.x.length !== c.y.length) return { valid: false, data: null, error: 'Chart x/y length mismatch' };
  return { valid: true, data: c, error: null };
}

export function validateInsights(raw) {
  if (!Array.isArray(raw)) return { valid: false, data: [], error: 'Insights must be an array' };
  const cleaned = raw.filter((i) => i && i.finding && i.severity);
  return { valid: cleaned.length > 0, data: cleaned, error: cleaned.length === 0 ? 'No valid insights' : null };
}

export function validateRecommendations(raw) {
  const rows = Array.isArray(raw) ? raw : (isObj(raw) && Array.isArray(raw.accounts) ? raw.accounts : null);
  if (!rows) return { valid: false, data: [], error: 'Recommendations must contain an accounts array' };
  return { valid: rows.length > 0, data: rows, error: rows.length === 0 ? 'No recommendations' : null };
}

export function validateSegments(raw) {
  const rows = isObj(raw) && Array.isArray(raw.segments) ? raw.segments : (Array.isArray(raw) ? raw : null);
  if (!rows) return { valid: false, data: [], meta: {}, error: 'Segments missing' };
  return { valid: rows.length > 0, data: rows, meta: isObj(raw) ? raw : {}, error: rows.length === 0 ? 'No segments' : null };
}

export function validateAnomalies(raw) {
  const rows = Array.isArray(raw) ? raw : (isObj(raw) && Array.isArray(raw.items) ? raw.items : null);
  if (!rows) return { valid: false, data: [], error: 'Anomalies must be an array' };
  return { valid: true, data: rows, error: null };
}

export function validateForecast(raw) {
  if (!isObj(raw) || !Array.isArray(raw.monthly)) return { valid: false, data: null, error: 'Forecast has no monthly data' };
  const monthly = raw.monthly.filter((m) => m && Number.isFinite(Number(m.mrr_base)));
  return { valid: monthly.length > 0, data: { monthly, meta: raw.meta || {} }, error: monthly.length ? null : 'Forecast is empty' };
}

export function validateAlerts(raw) {
  if (!Array.isArray(raw)) return { valid: false, data: [], error: 'Alerts must be an array' };
  return { valid: true, data: raw, error: null };
}

export function validateSimulation(raw) {
  if (!isObj(raw) || !Array.isArray(raw.results) || raw.results.length === 0) {
    return { valid: false, data: null, error: 'Simulation has no results' };
  }
  const rs = raw.results.filter((r) => isObj(r.input) && isObj(r.outputs));
  return { valid: rs.length > 0, data: { ...raw, results: rs }, error: rs.length ? null : 'Simulation results malformed' };
}

export function validateGoalProgress(raw) {
  if (!isObj(raw)) return { valid: false, data: null, error: 'Goal progress missing' };
  return { valid: true, data: raw, error: null };
}
