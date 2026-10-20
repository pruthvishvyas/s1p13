import { ThemeToggle } from './ThemeToggle';
import { useRunLog } from '../../hooks/shared/useRunLog';
import { fmtDateTime } from '../../utils/formatters';

export function Header({ title, onMenu }) {
  const { data } = useRunLog();
  return (
    <header className="header">
      <button className="menu-btn" onClick={onMenu} aria-label="Open menu">{'\u2630'}</button>
      <div className="header-title">{title}</div>
      <div className="header-meta">
        <div>Last updated: {fmtDateTime(data && data.timestamp)}</div>
        {data && data.scoring_source && <div>Risk scoring: {data.scoring_source}</div>}
      </div>
      <ThemeToggle />
    </header>
  );
}
