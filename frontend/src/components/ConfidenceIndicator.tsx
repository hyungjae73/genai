import React from 'react';
import { getConfidenceColor, getConfidenceLevel } from './confidenceUtils';

// Re-export for backward compatibility
export { getConfidenceColor, getConfidenceLevel, sortByConfidenceAsc } from './confidenceUtils';

export interface ConfidenceIndicatorProps {
  score: number;
  fieldName?: string;
  compact?: boolean;
}

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
