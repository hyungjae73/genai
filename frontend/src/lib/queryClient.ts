import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30 * 1000,       // 30秒
      gcTime: 5 * 60 * 1000,      // 5分
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});
