import { useQuery } from '@tanstack/react-query';
import { getAlerts, getSiteAlerts } from '../../services/api';

export const alertKeys = {
  all: ['alerts'] as const,
  bySite: (siteId: number) => ['alerts', { siteId }] as const,
};

export function useAlerts() {
  return useQuery({
    queryKey: alertKeys.all,
    queryFn: getAlerts,
  });
}

export function useSiteAlerts(siteId: number, isResolved?: boolean) {
  return useQuery({
    queryKey: alertKeys.bySite(siteId),
    queryFn: () => getSiteAlerts(siteId, isResolved),
    enabled: siteId > 0,
  });
}
