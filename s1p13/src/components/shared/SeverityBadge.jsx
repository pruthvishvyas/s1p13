import { severityClass } from '../../utils/colors';

export function SeverityBadge({ severity }) {
  return <span className={`badge ${severityClass(severity)}`}>{String(severity || '').toUpperCase()}</span>;
}
