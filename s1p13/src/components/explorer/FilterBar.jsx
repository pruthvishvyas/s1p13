import { useContext } from 'react';
import { ExplorerContext } from '../../context/ExplorerContext';
import { titleCase } from '../../utils/formatters';

export function FilterBar({ date, setDate, hasDate, onExport, copied }) {
  const { filters, setFilter, clearFilters, activeFilters } = useContext(ExplorerContext);
  return (
    <div className="filterbar no-print">
      <div className="row">
        {hasDate && (
          <>
            <label className="field">From<input type="date" value={date.from} onChange={(e) => setDate({ ...date, from: e.target.value })} /></label>
            <label className="field">To<input type="date" value={date.to} onChange={(e) => setDate({ ...date, to: e.target.value })} /></label>
          </>
        )}
        {Object.entries(filters).map(([d, v]) => (
          <button key={d} className="chip active" onClick={() => setFilter(d, null)}>{titleCase(d)}: {v} {'\u00D7'}</button>
        ))}
        {activeFilters === 0 && <span className="muted">No filters. Click any bar to filter.</span>}
        <button className="btn ghost" disabled={activeFilters === 0} onClick={clearFilters}>Clear filters{activeFilters ? ` (${activeFilters})` : ''}</button>
        <button className="btn ghost" onClick={onExport}>{copied ? 'Copied' : 'Copy summary'}</button>
      </div>
    </div>
  );
}
