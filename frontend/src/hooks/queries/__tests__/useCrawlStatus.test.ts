/**
 * Property-based test for crawl status polling interval logic.
 *
 * **Validates: Requirements 9.5**
 *
 * Feature: production-readiness-improvements, Property 7: タスクステータスポーリング間隔の条件分岐
 *
 * For any Celery task status string:
 *   - PENDING or STARTED → refetchInterval returns 2000
 *   - Terminal statuses (SUCCESS, FAILURE, REVOKED) → returns false
 *   - undefined → returns false
 */
import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { getPollingInterval } from '../useCrawlStatus';

describe('Property 7: Task status polling interval branching', () => {
  it('returns 2000 for PENDING or STARTED statuses', () => {
    fc.assert(
      fc.property(
        fc.constantFrom('PENDING', 'STARTED'),
        (status) => {
          expect(getPollingInterval(status)).toBe(2000);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('returns false for terminal statuses (SUCCESS, FAILURE, REVOKED)', () => {
    fc.assert(
      fc.property(
        fc.constantFrom('SUCCESS', 'FAILURE', 'REVOKED'),
        (status) => {
          expect(getPollingInterval(status)).toBe(false);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('returns false for undefined status', () => {
    expect(getPollingInterval(undefined)).toBe(false);
  });

  it('returns false for any arbitrary string that is not PENDING or STARTED', () => {
    fc.assert(
      fc.property(
        fc.string().filter((s) => s !== 'PENDING' && s !== 'STARTED'),
        (status) => {
          expect(getPollingInterval(status)).toBe(false);
        },
      ),
      { numRuns: 100 },
    );
  });
});
