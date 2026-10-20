import { useData } from '../useData';
import { PATHS } from '../../utils/contract';

export function useSimulationIndex() {
  return useData(PATHS.simulations ? PATHS.simulations + 'index.json' : null);
}
export function useSimulations(name) {
  return useData(name && PATHS.simulations ? PATHS.simulations + name + '.json' : null, { deps: [name] });
}
