import { SkeletonCard } from './SkeletonCard';
import { EmptyState } from './EmptyState';

export const DEFAULT_ACTION = 'Run main.py, then python export_for_frontend.py, then regenerate or redeploy this site.';

export function DataState({ loading, error, valid = true, message, action, detail, height = 120, count = 1, children }) {
  if (loading) {
    return <div className="skeleton-grid"><SkeletonCard height={height} count={count} /></div>;
  }
  if (error || !valid) {
    return <EmptyState message={message || 'No data available yet.'} action={action || DEFAULT_ACTION} detail={detail || error} />;
  }
  return children;
}
