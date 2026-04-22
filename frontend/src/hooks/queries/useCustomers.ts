import { useQuery } from '@tanstack/react-query';
import { getCustomers } from '../../services/api';

export const customerKeys = {
  all: ['customers'] as const,
};

export function useCustomers(activeOnly?: boolean) {
  return useQuery({
    queryKey: customerKeys.all,
    queryFn: () => getCustomers(activeOnly),
  });
}
