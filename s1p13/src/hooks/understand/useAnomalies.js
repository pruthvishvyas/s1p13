import { useData } from '../useData';
import { PATHS } from '../../utils/contract';

export function useAnomalies() {
  return useData(PATHS.anomalies);
}
