import { useData } from '../useData';
import { PATHS } from '../../utils/contract';

export function useChartIndex() {
  return useData(PATHS.charts ? PATHS.charts + 'index.json' : null);
}
export function useChart(name) {
  return useData(name && PATHS.charts ? PATHS.charts + name + '.json' : null, { deps: [name] });
}
