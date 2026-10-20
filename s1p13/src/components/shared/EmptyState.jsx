export function EmptyState({ message, action, detail }) {
  return (
    <div className="empty-state">
      <span className="empty-icon">{'\uD83D\uDCCA'}</span>
      <p className="empty-message">{message}</p>
      {action && <p className="empty-action">{action}</p>}
      {detail && <p className="empty-detail">{detail}</p>}
    </div>
  );
}
