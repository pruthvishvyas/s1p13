import { useData } from '../useData';
import { PATHS } from '../../utils/contract';

export function useRecommendations() {
  return useData(PATHS.recommendations);
}
