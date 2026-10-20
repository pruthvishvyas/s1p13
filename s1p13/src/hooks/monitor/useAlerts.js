import { useData } from '../useData';
import { PATHS } from '../../utils/contract';

export function useAlerts() {
  return useData(PATHS.alerts);
}
