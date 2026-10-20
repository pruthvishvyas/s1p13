import React from 'react';
import { EmptyState } from './EmptyState';

export class ErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = { failed: false, msg: '' }; }
  static getDerivedStateFromError(err) { return { failed: true, msg: String(err && err.message ? err.message : err) }; }
  componentDidCatch(err) { console.error('Render error:', err); }
  render() {
    if (this.state.failed) return <EmptyState message="This panel could not be drawn." detail={this.state.msg} />;
    return this.props.children;
  }
}
