import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getSites, getSite, createSite, updateSite, deleteSite } from '../../services/api';

export const siteKeys = {
  all: ['sites'] as const,
  detail: (id: number) => ['sites', id] as const,
};

export function useSites() {
  return useQuery({
    queryKey: siteKeys.all,
    queryFn: getSites,
  });
}

export function useSite(id: number) {
  return useQuery({
    queryKey: siteKeys.detail(id),
    queryFn: () => getSite(id),
    enabled: id > 0,
  });
}

export function useCreateSite() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createSite,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: siteKeys.all });
    },
  });
}

export function useUpdateSite() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Parameters<typeof updateSite>[1] }) =>
      updateSite(id, data),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: siteKeys.all });
      qc.invalidateQueries({ queryKey: siteKeys.detail(variables.id) });
    },
  });
}

export function useDeleteSite() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteSite,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: siteKeys.all });
    },
  });
}
