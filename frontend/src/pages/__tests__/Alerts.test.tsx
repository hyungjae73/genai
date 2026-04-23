import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import * as fc from 'fast-check';
import Alerts from '../Alerts';
import type { Alert } from '../../services/api';
import * as api from '../../services/api';
import { TestQueryClientProvider } from '../../test/testQueryClient';

vi.mock('../../services/api', () => ({
  getAlerts: vi.fn(),
}));

vi.mock('../../hooks/useAutoRefresh', () => ({
  useAutoRefresh: vi.fn(),
}));

const severities = ['low', 'medium', 'high', 'critical'] as const;

const alertArbitrary: fc.Arbitrary<Alert> = fc.record({
  id: fc.integer({ min: 1, max: 10000 }),
  site_id: fc.integer({ min: 1, max: 100 }),
  site_name: fc.string({ minLength: 1, maxLength: 20 }).filter(s => s.trim().length > 0),
  severity: fc.constantFrom(...severities),
  message: fc.string({ minLength: 1, maxLength: 50 }).filter(s => s.trim().length > 0),
  alert_type: fc.constantFrom('fake_site', 'price_change', 'content_change', 'violation'),
  violation_type: fc.string({ minLength: 1, maxLength: 20 }),
  created_at: fc.constant('2024-01-15T10:00:00Z'),
  is_resolved: fc.boolean(),
  fake_domain: fc.option(fc.domain(), { nil: undefined }),
  legitimate_domain: fc.option(fc.domain(), { nil: undefined }),
  domain_similarity_score: fc.option(fc.double({ min: 0, max: 1, noNaN: true }), { nil: undefined }),
  content_similarity_score: fc.option(fc.double({ min: 0, max: 1, noNaN: true }), { nil: undefined }),
});

/**
 * Property 6: アラート種別フィルタリング
 * **Validates: Requirements 5.2, 5.3**
 *
 * For any list of alerts and any alert type filter selection, the filtered result
 * shall contain only alerts matching the filter criteria.
 */
describe('Property 6: アラート種別フィルタリング', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('filtering by fake_site shows only fake_site alerts', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.array(alertArbitrary, { minLength: 1, maxLength: 15 }).filter(
          arr => arr.some(a => a.alert_type === 'fake_site') && arr.some(a => a.alert_type !== 'fake_site')
        ),
        async (alerts) => {
          // Ensure unique IDs
          const uniqueAlerts = alerts.map((a, i) => ({ ...a, id: i + 1 }));
          vi.mocked(api.getAlerts).mockResolvedValue(uniqueAlerts);

          const { unmount } = render(
            <TestQueryClientProvider>
              <BrowserRouter>
                <Alerts />
              </BrowserRouter>
            </TestQueryClientProvider>
          );

          // Wait for loading to finish
          await screen.findByText('アラート一覧');

          // Select fake_site filter
          const alertTypeSelect = screen.getByDisplayValue('すべて');
          await userEvent.selectOptions(alertTypeSelect, 'fake_site');

          // Get all alert cards
          const alertCards = document.querySelectorAll('.alert-card');
          const fakeSiteCount = uniqueAlerts.filter(a => a.alert_type === 'fake_site').length;

          expect(alertCards.length).toBe(fakeSiteCount);

          // Every displayed card should have the 偽サイト badge
          alertCards.forEach(card => {
            const badge = card.querySelector('.alert-type-badge.fake-site');
            expect(badge).not.toBeNull();
            expect(badge?.textContent).toBe('偽サイト');
          });

          unmount();
        }
      ),
      { numRuns: 20 }
    );
  });

  it('filtering by violation shows only non-fake_site alerts', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.array(alertArbitrary, { minLength: 1, maxLength: 15 }).filter(
          arr => arr.some(a => a.alert_type === 'fake_site') && arr.some(a => a.alert_type !== 'fake_site')
        ),
        async (alerts) => {
          const uniqueAlerts = alerts.map((a, i) => ({ ...a, id: i + 1 }));
          vi.mocked(api.getAlerts).mockResolvedValue(uniqueAlerts);

          const { unmount } = render(
            <TestQueryClientProvider>
              <BrowserRouter>
                <Alerts />
              </BrowserRouter>
            </TestQueryClientProvider>
          );

          await screen.findByText('アラート一覧');

          const alertTypeSelect = screen.getByDisplayValue('すべて');
          await userEvent.selectOptions(alertTypeSelect, 'violation');

          const alertCards = document.querySelectorAll('.alert-card');
          const violationCount = uniqueAlerts.filter(a => a.alert_type !== 'fake_site').length;

          expect(alertCards.length).toBe(violationCount);

          // Every displayed card should have the 契約違反 badge
          alertCards.forEach(card => {
            const badge = card.querySelector('.alert-type-badge.violation');
            expect(badge).not.toBeNull();
            expect(badge?.textContent).toBe('契約違反');
          });

          unmount();
        }
      ),
      { numRuns: 20 }
    );
  });

  it('filtering by all shows all alerts', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.array(alertArbitrary, { minLength: 1, maxLength: 15 }),
        async (alerts) => {
          const uniqueAlerts = alerts.map((a, i) => ({ ...a, id: i + 1 }));
          vi.mocked(api.getAlerts).mockResolvedValue(uniqueAlerts);

          const { unmount } = render(
            <TestQueryClientProvider>
              <BrowserRouter>
                <Alerts />
              </BrowserRouter>
            </TestQueryClientProvider>
          );

          await screen.findByText('アラート一覧');

          // Default is 'all', so all alerts should be shown
          const alertCards = document.querySelectorAll('.alert-card');
          expect(alertCards.length).toBe(uniqueAlerts.length);

          unmount();
        }
      ),
      { numRuns: 20 }
    );
  });
});

/**
 * Property 7: TakeDownバナーの条件付き表示
 * **Validates: Requirements 7.1, 7.4**
 *
 * For any alert where alert_type='fake_site', the TakeDown warning banner
 * is shown only when is_resolved=false, and hidden when is_resolved=true.
 */
describe('Property 7: TakeDownバナーの条件付き表示', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('TakeDown banner shows only for unresolved fake_site alerts', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.array(alertArbitrary, { minLength: 1, maxLength: 15 }).map(
          arr => arr.map((a, i) => ({ ...a, id: i + 1 }))
        ),
        async (alerts) => {
          vi.mocked(api.getAlerts).mockResolvedValue(alerts);

          const { unmount } = render(
            <TestQueryClientProvider>
              <BrowserRouter>
                <Alerts />
              </BrowserRouter>
            </TestQueryClientProvider>
          );

          await screen.findByText('アラート一覧');

          const expectedBannerCount = alerts.filter(
            a => a.alert_type === 'fake_site' && !a.is_resolved
          ).length;

          const banners = document.querySelectorAll('.takedown-banner');
          expect(banners.length).toBe(expectedBannerCount);

          // Each banner should contain the required text
          banners.forEach(banner => {
            expect(banner.textContent).toContain('TakeDown対応が必要');
          });

          unmount();
        }
      ),
      { numRuns: 20 }
    );
  });

  it('TakeDown banner is hidden when is_resolved=true for fake_site alerts', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.array(alertArbitrary, { minLength: 1, maxLength: 10 }).map(
          arr => arr.map((a, i) => ({
            ...a,
            id: i + 1,
            alert_type: 'fake_site' as const,
            is_resolved: true,
          }))
        ),
        async (alerts) => {
          vi.mocked(api.getAlerts).mockResolvedValue(alerts);

          const { unmount } = render(
            <TestQueryClientProvider>
              <BrowserRouter>
                <Alerts />
              </BrowserRouter>
            </TestQueryClientProvider>
          );

          await screen.findByText('アラート一覧');

          // All alerts are resolved fake_site, so no banners should show
          const banners = document.querySelectorAll('.takedown-banner');
          expect(banners.length).toBe(0);

          unmount();
        }
      ),
      { numRuns: 20 }
    );
  });

  it('TakeDown banner displays fake_domain and similarity scores', async () => {
    const fakeSiteAlert: Alert = {
      id: 1,
      site_id: 1,
      site_name: 'Test Site',
      severity: 'critical',
      message: 'Fake site detected',
      alert_type: 'fake_site',
      violation_type: 'fake_site',
      created_at: '2024-01-15T10:00:00Z',
      is_resolved: false,
      fake_domain: 'examp1e.com',
      legitimate_domain: 'example.com',
      domain_similarity_score: 0.85,
      content_similarity_score: 0.92,
    };

    vi.mocked(api.getAlerts).mockResolvedValue([fakeSiteAlert]);

    render(
            <TestQueryClientProvider>
              <BrowserRouter>
                <Alerts />
              </BrowserRouter>
            </TestQueryClientProvider>
          );

    await screen.findByText('アラート一覧');

    const banner = document.querySelector('.takedown-banner');
    expect(banner).not.toBeNull();
    expect(banner?.textContent).toContain('TakeDown対応が必要');
    expect(banner?.textContent).toContain('examp1e.com');
    expect(banner?.textContent).toContain('0.85');
    expect(banner?.textContent).toContain('0.92');
  });
});
