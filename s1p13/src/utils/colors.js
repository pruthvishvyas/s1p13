export function severityClass(sev) {
  const s = String(sev || '').toLowerCase();
  if (s === 'critical' || s === 'high') return 'danger';
  if (s === 'medium') return 'warning';
  if (s === 'low') return 'success';
  return '';
}
export function priorityClass(p) {
  return { P1: 'danger', P2: 'warning', P3: 'info', P4: '' }[p] ?? '';
}
export const SEVERITY_RANK = { critical: 0, high: 1, medium: 2, low: 3 };
