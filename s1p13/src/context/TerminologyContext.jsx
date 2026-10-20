import { createContext, useContext, useMemo } from 'react';
import { useData } from '../hooks/useData';
import { PATHS, CONTRACT } from '../utils/contract';

const Ctx = createContext(null);

export function TerminologyProvider({ children }) {
  const { data } = useData(PATHS.terminology);
  const terms = useMemo(() => ({
    ...(CONTRACT.terminology || {}),
    ...(data && typeof data === 'object' && !Array.isArray(data) ? data : {})
  }), [data]);
  const term = useMemo(() => (key, opts = {}) => {
    const v = terms[key] ?? key;
    return opts.plural ? v + 's' : v;
  }, [terms]);
  return <Ctx.Provider value={{ terms, term }}>{children}</Ctx.Provider>;
}

export function useTerm() {
  const c = useContext(Ctx);
  return c ? c.term : (k) => k;
}
export function useTerms() {
  const c = useContext(Ctx);
  return c ? c.terms : {};
}
