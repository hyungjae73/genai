import React from 'react';

/* ------------------------------------------------------------------ */
/*  ConfidenceIndicator – reusable confidence score display            */
/* ------------------------------------------------------------------ */

export interface ConfidenceIndicatorProps {
  /** Confidence score between 0.0 and 1.0 */
  score: number;
  /** Optional field name label */
  fieldName?: string;
  /** Compact mode shows only the badge without label */
  compact?: boolean;
}

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

const ConfidenceIndicator: React.FC<ConfidenceIndicatorProps> = ({
  score,
  fieldName,
  compact = false,
}) => {
  const color = getConfidenceColor(score);
  const level = getConfidenceLevel(score);
  const percentage = (score * 100).toFixed(0);

  return (
    <span
      className="confidence-indicator"
      title={fieldName ? `${fieldName}: ${percentage}% (${level})` : `${percentage}% (${level})`}
      style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}
    >
      <span
        className="confidence-indicator__badge"
        style={{
          backgroundColor: color,
          color: '#fff',
          padding: compact ? '0.1rem 0.35rem' : '0.2rem 0.5rem',
          borderRadius: '4px',
          fontSize: compact ? '0.7rem' : '0.75rem',
          fontWeight: 600,
          whiteSpace: 'nowrap',
        }}
      >
        {percentage}% ({level})
      </span>
      {!compact && fieldName && (
        <span
          className="confidence-indicator__label"
          style={{ fontSize: '0.75rem', color: 'var(--text-secondary, #6b7280)' }}
        >
          {fieldName}
        </span>
      )}
    </span>
  );
};

export default ConfidenceIndicator;

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
