import { useData } from '../useData';
import { PATHS } from '../../utils/contract';
export function useRunLog() {
  return useData(PATHS.runLog);
}
