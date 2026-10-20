import { useEffect, useState } from 'react';
import { useParams, Navigate } from 'react-router-dom';
import { Sidebar } from '../components/shared/Sidebar';
import { Header } from '../components/shared/Header';
import { ErrorBoundary } from '../components/shared/ErrorBoundary';
import { useTerm } from '../components/shared/TerminologyProvider';
import { useOutcome } from '../context/OutcomeContext';
import { VIEW_INDEX } from '../utils/navigation';
import { KPICards } from '../components/understand/KPICards';
import { ChartPanel } from '../components/understand/ChartPanel';
import { SegmentExplorer } from '../components/understand/SegmentExplorer';
import { AnomalyTable } from '../components/understand/AnomalyTable';
import { InsightCards } from '../components/decide/InsightCards';
import { RecommendationEngine } from '../components/decide/RecommendationEngine';
import { WhatIfSimulator } from '../components/decide/WhatIfSimulator';
import { GoalTracker } from '../components/decide/GoalTracker';
import { Forecaster } from '../components/monitor/Forecaster';
import { GoalProgress } from '../components/monitor/GoalProgress';
import { AlertCenter } from '../components/monitor/AlertCenter';
import { InteractiveExplorer } from '../components/explorer/InteractiveExplorer';
import { UserManual } from '../components/manual/UserManual';

const VIEWS = {
  overview: KPICards, charts: ChartPanel, segments: SegmentExplorer, anomalies: AnomalyTable,
  insights: InsightCards, recommendations: RecommendationEngine, simulator: WhatIfSimulator, goals: GoalTracker,
  forecast: Forecaster, progress: GoalProgress, alerts: AlertCenter, explorer: InteractiveExplorer, manual: UserManual
};

export default function Dashboard() {
  const { view } = useParams();
  const term = useTerm();
  const { setOutcome } = useOutcome();
  const [menu, setMenu] = useState(false);
  const meta = VIEW_INDEX[view];
  useEffect(() => { if (meta) { setOutcome(meta.section); window.scrollTo(0, 0); } }, [view]);
  if (!meta || !VIEWS[view]) return <Navigate to="/overview" replace />;
  const View = VIEWS[view];
  return (
    <div className="app">
      <Sidebar open={menu} onClose={() => setMenu(false)} />
      <div className="main">
        <Header title={meta.title(term)} onMenu={() => setMenu(!menu)} />
        <div className="content">
          <p className="page-desc">{meta.desc(term)}</p>
          <ErrorBoundary key={view}><View /></ErrorBoundary>
        </div>
      </div>
    </div>
  );
}
