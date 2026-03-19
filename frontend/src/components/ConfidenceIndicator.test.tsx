/**
 * Unit tests for ConfidenceIndicator component.
 *
 * Tests cover:
 * - Color coding thresholds (green ≥0.8, yellow 0.5–0.8, red <0.5)
 * - Confidence level labels (高/中/低)
 * - Compact mode rendering
 * - Field name display
 * - sortByConfidenceAsc utility
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ConfidenceIndicator, {
  getConfidenceColor,
  getConfidenceLevel,
  sortByConfidenceAsc,
} from './ConfidenceIndicator';

/* ------------------------------------------------------------------ */
/*  getConfidenceColor                                                 */
/* ------------------------------------------------------------------ */
describe('getConfidenceColor', () => {
  it('returns green for score >= 0.8', () => {
    expect(getConfidenceColor(0.8)).toBe('var(--success-color, #10b981)');
    expect(getConfidenceColor(0.95)).toBe('var(--success-color, #10b981)');
    expect(getConfidenceColor(1.0)).toBe('var(--success-color, #10b981)');
  });

  it('returns yellow for score >= 0.5 and < 0.8', () => {
    expect(getConfidenceColor(0.5)).toBe('var(--warning-color, #f59e0b)');
    expect(getConfidenceColor(0.65)).toBe('var(--warning-color, #f59e0b)');
    expect(getConfidenceColor(0.79)).toBe('var(--warning-color, #f59e0b)');
  });

  it('returns red for score < 0.5', () => {
    expect(getConfidenceColor(0.0)).toBe('var(--danger-color, #ef4444)');
    expect(getConfidenceColor(0.3)).toBe('var(--danger-color, #ef4444)');
    expect(getConfidenceColor(0.49)).toBe('var(--danger-color, #ef4444)');
  });
});

/* ------------------------------------------------------------------ */
/*  getConfidenceLevel                                                 */
/* ------------------------------------------------------------------ */
describe('getConfidenceLevel', () => {
  it('returns 高 for high confidence', () => {
    expect(getConfidenceLevel(0.8)).toBe('高');
    expect(getConfidenceLevel(1.0)).toBe('高');
  });

  it('returns 中 for medium confidence', () => {
    expect(getConfidenceLevel(0.5)).toBe('中');
    expect(getConfidenceLevel(0.79)).toBe('中');
  });

  it('returns 低 for low confidence', () => {
    expect(getConfidenceLevel(0.0)).toBe('低');
    expect(getConfidenceLevel(0.49)).toBe('低');
  });
});

/* ------------------------------------------------------------------ */
/*  ConfidenceIndicator component                                      */
/* ------------------------------------------------------------------ */
describe('ConfidenceIndicator', () => {
  it('renders percentage and level label', () => {
    render(<ConfidenceIndicator score={0.85} />);
    expect(screen.getByText('85% (高)')).toBeInTheDocument();
  });

  it('renders field name when provided and not compact', () => {
    render(<ConfidenceIndicator score={0.6} fieldName="product_name" />);
    expect(screen.getByText('product_name')).toBeInTheDocument();
  });

  it('hides field name in compact mode', () => {
    render(<ConfidenceIndicator score={0.6} fieldName="product_name" compact />);
    expect(screen.queryByText('product_name')).not.toBeInTheDocument();
  });

  it('shows correct title with field name', () => {
    render(<ConfidenceIndicator score={0.92} fieldName="price" />);
    const indicator = screen.getByTitle('price: 92% (高)');
    expect(indicator).toBeInTheDocument();
  });

  it('shows correct title without field name', () => {
    render(<ConfidenceIndicator score={0.45} />);
    const indicator = screen.getByTitle('45% (低)');
    expect(indicator).toBeInTheDocument();
  });

  it('applies green background for high confidence', () => {
    render(<ConfidenceIndicator score={0.9} />);
    const badge = screen.getByText('90% (高)');
    expect(badge).toHaveStyle({ backgroundColor: 'var(--success-color, #10b981)' });
  });

  it('applies yellow background for medium confidence', () => {
    render(<ConfidenceIndicator score={0.65} />);
    const badge = screen.getByText('65% (中)');
    expect(badge).toHaveStyle({ backgroundColor: 'var(--warning-color, #f59e0b)' });
  });

  it('applies red background for low confidence', () => {
    render(<ConfidenceIndicator score={0.3} />);
    const badge = screen.getByText('30% (低)');
    expect(badge).toHaveStyle({ backgroundColor: 'var(--danger-color, #ef4444)' });
  });

  it('rounds percentage to integer', () => {
    render(<ConfidenceIndicator score={0.856} />);
    expect(screen.getByText('86% (高)')).toBeInTheDocument();
  });
});

/* ------------------------------------------------------------------ */
/*  sortByConfidenceAsc                                                */
/* ------------------------------------------------------------------ */
describe('sortByConfidenceAsc', () => {
  it('sorts items by confidence ascending', () => {
    const items = [
      { name: 'high', score: 0.9 },
      { name: 'low', score: 0.2 },
      { name: 'mid', score: 0.6 },
    ];
    const sorted = sortByConfidenceAsc(items, (i) => i.score);
    expect(sorted.map((i) => i.name)).toEqual(['low', 'mid', 'high']);
  });

  it('places null/undefined scores first', () => {
    const items = [
      { name: 'known', score: 0.5 as number | null },
      { name: 'unknown', score: null },
    ];
    const sorted = sortByConfidenceAsc(items, (i) => i.score);
    expect(sorted[0].name).toBe('unknown');
    expect(sorted[1].name).toBe('known');
  });

  it('does not mutate the original array', () => {
    const items = [
      { name: 'b', score: 0.8 },
      { name: 'a', score: 0.3 },
    ];
    const sorted = sortByConfidenceAsc(items, (i) => i.score);
    expect(sorted).not.toBe(items);
    expect(items[0].name).toBe('b'); // original unchanged
  });
});
