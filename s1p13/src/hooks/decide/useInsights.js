import { useData } from '../useData';
import { PATHS } from '../../utils/contract';

export function useInsights() {
  return useData(PATHS.insights);
}
