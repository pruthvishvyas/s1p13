import { useData } from '../useData';
import { PATHS } from '../../utils/contract';

export function useSegments() {
  return useData(PATHS.segments);
}
