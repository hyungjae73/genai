import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchReviews,
  fetchReviewDetail,
  fetchReviewStats,
  assignReviewer,
  decidePrimary,
  decideSecondary,
} from '../../services/api';
import type { ReviewListParams, AssignReviewerRequest, ReviewDecisionRequest } from '../../services/api';

export const reviewKeys = {
  all: (params?: ReviewListParams) => ['reviews', params ?? {}] as const,
  detail: (id: number) => ['review-detail', id] as const,
  stats: ['review-stats'] as const,
};

export function useReviews(params?: ReviewListParams) {
  return useQuery({
    queryKey: reviewKeys.all(params),
    queryFn: () => fetchReviews(params),
  });
}

export function useReviewDetail(id: number) {
  return useQuery({
    queryKey: reviewKeys.detail(id),
    queryFn: () => fetchReviewDetail(id),
    enabled: id > 0,
  });
}

export function useReviewStats() {
  return useQuery({
    queryKey: reviewKeys.stats,
    queryFn: fetchReviewStats,
  });
}

export function useAssignReviewer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ reviewId, body }: { reviewId: number; body: AssignReviewerRequest }) =>
      assignReviewer(reviewId, body),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ['reviews'] });
      qc.invalidateQueries({ queryKey: reviewKeys.detail(variables.reviewId) });
    },
  });
}

export function useDecidePrimary() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ reviewId, body }: { reviewId: number; body: ReviewDecisionRequest }) =>
      decidePrimary(reviewId, body),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ['reviews'] });
      qc.invalidateQueries({ queryKey: reviewKeys.detail(variables.reviewId) });
      qc.invalidateQueries({ queryKey: reviewKeys.stats });
    },
  });
}

export function useDecideSecondary() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ reviewId, body }: { reviewId: number; body: ReviewDecisionRequest }) =>
      decideSecondary(reviewId, body),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ['reviews'] });
      qc.invalidateQueries({ queryKey: reviewKeys.detail(variables.reviewId) });
      qc.invalidateQueries({ queryKey: reviewKeys.stats });
    },
  });
}
