/** Color coding: green ≥0.8, yellow 0.5–0.8, red <0.5 */
export const getConfidenceColor = (score: number): string => {
  if (score >= 0.8) return 'var(--success-color, #10b981)';
  if (score >= 0.5) return 'var(--warning-color, #f59e0b)';
  return 'var(--danger-color, #ef4444)';
};

export const getConfidenceLevel = (score: number): string => {
  if (score >= 0.8) return '高';
  if (score >= 0.5) return '中';
  return '低';
};

/**
 * Utility: sort data fields by confidence score ascending (lowest first).
 * Fields with undefined/null scores are placed first (need most review).
 */
export function sortByConfidenceAsc<T>(
  items: T[],
  getScore: (item: T) => number | undefined | null,
): T[] {
  return [...items].sort((a, b) => {
    const sa = getScore(a) ?? -1;
    const sb = getScore(b) ?? -1;
    return sa - sb;
  });
}
