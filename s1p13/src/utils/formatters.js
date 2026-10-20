export const CURRENCY = '$';

const toNum = (v) => (v === null || v === undefined || v === '' ? NaN : Number(v));

export function fmtInt(v) {
  const n = toNum(v);
  return Number.isFinite(n) ? Math.round(n).toLocaleString('en-US') : '\u2014';
}
export function fmtNum(v, d = 2) {
  const n = toNum(v);
  return Number.isFinite(n) ? n.toLocaleString('en-US', { maximumFractionDigits: d }) : '\u2014';
}
export function fmtCurrency(v, compact = false) {
  const n = toNum(v);
  if (!Number.isFinite(n)) return '\u2014';
  if (compact && Math.abs(n) >= 1000) {
    const units = [['B', 1e9], ['M', 1e6], ['K', 1e3]];
    for (const [s, div] of units) {
      if (Math.abs(n) >= div) return CURRENCY + (n / div).toFixed(1) + s;
    }
  }
  return CURRENCY + Math.round(n).toLocaleString('en-US');
}
export function fmtPercent(v, d = 1) {
  const n = toNum(v);
  return Number.isFinite(n) ? n.toFixed(d) + '%' : '\u2014';
}
export function fmtProb(v) {
  const n = toNum(v);
  return Number.isFinite(n) ? (n * 100).toFixed(0) + '%' : '\u2014';
}
export function titleCase(s) {
  return String(s ?? '').replace(/[_-]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}
export function fmtDateTime(iso) {
  if (!iso) return '\u2014';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? String(iso) : d.toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' });
}
export function formatKPI(k) {
  const v = k.value;
  switch (k.format) {
    case 'currency': return fmtCurrency(v, Math.abs(Number(v)) >= 1e6);
    case 'percent': return fmtPercent(v);
    case 'integer': return fmtInt(v);
    case 'months': return fmtNum(v, 1) + ' mo';
    case 'ratio': return fmtNum(v, 2) + 'x';
    case 'decimal': return fmtNum(v, 3);
    case 'text': return titleCase(v);
    default: return typeof v === 'number' ? fmtNum(v, 2) : String(v ?? '\u2014');
  }
}
export function fmtOutput(key, v) {
  const k = String(key).toLowerCase();
  if (/roi/.test(k)) return fmtNum(v, 2) + 'x';
  if (/months/.test(k)) return fmtNum(v, 1) + ' mo';
  if (/arr|mrr|margin|cost|saved/.test(k) && !/accounts/.test(k)) return fmtCurrency(v);
  return fmtNum(v, 1);
}
