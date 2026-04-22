import { useQuery } from '@tanstack/react-query';
import { getMonitoringHistory } from '../../services/api';

export const monitoringHistoryKeys = {
  all: ['monitoring-history'] as const,
};

export function useMonitoringHistory() {
  return useQuery({
    queryKey: monitoringHistoryKeys.all,
    queryFn: getMonitoringHistory,
    refetchInterval: 30_000,
  });
}
