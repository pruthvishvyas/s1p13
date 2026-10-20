import { useData } from '../useData';
import { PATHS } from '../../utils/contract';

export function useKPIs() {
  return useData(PATHS.kpis);
}
