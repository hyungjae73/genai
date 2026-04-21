import { useQuery } from '@tanstack/react-query';
import { getStatistics } from '../../services/api';

export const statisticsKeys = {
  all: ['statistics'] as const,
};

export function useStatistics() {
  return useQuery({
    queryKey: statisticsKeys.all,
    queryFn: getStatistics,
    refetchInterval: 30_000,
  });
}
