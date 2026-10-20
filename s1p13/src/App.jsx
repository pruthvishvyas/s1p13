import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { TerminologyProvider } from './context/TerminologyContext';
import { OutcomeProvider } from './context/OutcomeContext';
import { ExplorerProvider } from './context/ExplorerContext';
import Dashboard from './pages/Dashboard';

export default function App() {
  return (
    <TerminologyProvider>
      <OutcomeProvider>
        <ExplorerProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<Navigate to="/overview" replace />} />
              <Route path="/:view" element={<Dashboard />} />
              <Route path="*" element={<Navigate to="/overview" replace />} />
            </Routes>
          </BrowserRouter>
        </ExplorerProvider>
      </OutcomeProvider>
    </TerminologyProvider>
  );
}
