import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getCrawlStatus } from '../../services/api';
import { siteKeys } from './useSites';
import { alertKeys } from './useAlerts';

export const crawlStatusKeys = {
  job: (jobId: string | null) => ['crawl-status', jobId] as const,
};

/**
 * Determine the refetch interval based on Celery task status.
 *
 * Exported for property-based testing (Property 7).
 */
export function getPollingInterval(status: string | undefined): number | false {
  if (status === 'PENDING' || status === 'STARTED') {
    return 2000;
  }
  return false;
}

export function useCrawlStatus(jobId: string | null) {
  const qc = useQueryClient();

  return useQuery({
    queryKey: crawlStatusKeys.job(jobId),
    queryFn: () => getCrawlStatus(jobId!),
    enabled: !!jobId,
    staleTime: 0,
    refetchInterval: (query) => {
      const status = query.state.data?.status;

      if (status === 'SUCCESS') {
        qc.invalidateQueries({ queryKey: siteKeys.all });
        qc.invalidateQueries({ queryKey: alertKeys.all });
        return false;
      }

      return getPollingInterval(status);
    },
  });
}
