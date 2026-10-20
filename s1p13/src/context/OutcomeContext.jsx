import { createContext, useContext, useState } from 'react';

const Ctx = createContext({ outcome: 'UNDERSTAND', setOutcome: () => {} });

export function OutcomeProvider({ children }) {
  const [outcome, setOutcome] = useState('UNDERSTAND');
  return <Ctx.Provider value={{ outcome, setOutcome }}>{children}</Ctx.Provider>;
}
export function useOutcome() {
  return useContext(Ctx);
}
