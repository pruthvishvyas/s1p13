import { useCallback, useState } from 'react';
import { useData } from '../useData';
import { PATHS } from '../../utils/contract';

const KEY = 'goal-overrides';
function readOverrides() {
  try { return JSON.parse(localStorage.getItem(KEY) || '{}') || {}; } catch { return {}; }
}

export function useGoals() {
  const { data, loading, error } = useData(PATHS.goals);
  const [overrides, setOverrides] = useState(readOverrides);
  const setOverride = useCallback((key, value) => {
    setOverrides((prev) => {
      const next = { ...prev };
      if (value === '' || value === null || Number.isNaN(Number(value))) delete next[key]; else next[key] = Number(value);
      try { localStorage.setItem(KEY, JSON.stringify(next)); } catch { /* storage unavailable */ }
      return next;
    });
  }, []);
  const target = (key) => (overrides[key] !== undefined ? overrides[key] : data?.[key]?.value ?? null);
  return { goals: data, loading, error, overrides, setOverride, target };
}
