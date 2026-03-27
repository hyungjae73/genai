import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { classifyBreakpoint, Breakpoint } from '../hooks/useMediaQuery';

// Feature: figma-ux-improvement, Property 8: Breakpoint Classification

const VALID_BREAKPOINTS: Breakpoint[] = ['mobile', 'tablet', 'desktop'];

describe('Property 8: Breakpoint Classification', () => {
  /**
   * Validates: Requirements 5.1
   *
   * For any positive integer viewport width, classifyBreakpoint returns
   * exactly one category (mobile: <768px, tablet: 768-1023px, desktop: ≥1024px).
   */
  it('should return exactly one valid breakpoint for any positive integer width', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 100000 }),
        (width: number) => {
          const result = classifyBreakpoint(width);

          // Result must be one of the valid breakpoints
          expect(VALID_BREAKPOINTS).toContain(result);

          // Result must match the expected category based on breakpoint rules
          if (width < 768) {
            expect(result).toBe('mobile');
          } else if (width >= 768 && width <= 1023) {
            expect(result).toBe('tablet');
          } else {
            expect(result).toBe('desktop');
          }
        }
      ),
      { numRuns: 200 }
    );
  });

  it('should be a total function (returns a value for every positive integer)', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 100000 }),
        (width: number) => {
          const result = classifyBreakpoint(width);
          expect(result).toBeDefined();
          expect(typeof result).toBe('string');
          expect(result.length).toBeGreaterThan(0);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('should classify boundary values correctly', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(1, 767, 768, 1023, 1024),
        (width: number) => {
          const result = classifyBreakpoint(width);
          if (width < 768) {
            expect(result).toBe('mobile');
          } else if (width <= 1023) {
            expect(result).toBe('tablet');
          } else {
            expect(result).toBe('desktop');
          }
        }
      ),
      { numRuns: 100 }
    );
  });
});
