import { useData } from '../useData';
import { PATHS } from '../../utils/contract';

export function useGoalProgress() {
  return useData(PATHS.goalProgress);
}
