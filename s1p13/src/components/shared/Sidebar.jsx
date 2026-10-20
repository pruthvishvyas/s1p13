import { NavLink } from 'react-router-dom';
import { NAV } from '../../utils/navigation';
import { PROJECT } from '../../utils/contract';
import { useTerm } from './TerminologyProvider';

export function Sidebar({ open, onClose }) {
  const term = useTerm();
  return (
    <aside className={`sidebar ${open ? 'open' : ''}`}>
      <div className="sidebar-brand">{PROJECT.name}</div>
      <nav>
        {NAV.map((sec) => (
          <div key={sec.id} className="nav-section">
            <div className="nav-title">{sec.title}</div>
            <div className="nav-blurb">{sec.blurb}</div>
            {sec.items.map((it) => (
              <NavLink key={it.id} to={'/' + it.id} onClick={onClose}
                className={({ isActive }) => 'nav-item' + (isActive ? ' active' : '')}>
                {it.label(term)}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>
    </aside>
  );
}
