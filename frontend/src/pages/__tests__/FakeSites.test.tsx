import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import * as fc from 'fast-check';
import FakeSites from '../FakeSites';
import App from '../../App';
import type { Alert } from '../../services/api';
import * as api from '../../services/api';

vi.mock('../../services/api', () => ({
  getAlerts: vi.fn(),
  getStatistics: vi.fn(),
  getMonitoringHistory: vi.fn(),
  getSites: vi.fn(),
}));

vi.mock('../../hooks/useAutoRefresh', () => ({
  useAutoRefresh: vi.fn(),
}));

// Mock chart.js to avoid canvas issues in jsdom (needed when rendering App with Dashboard)
vi.mock('react-chartjs-2', () => ({
  Line: () => <div data-testid="mock-chart">Chart</div>,
}));

vi.mock('chart.js', () => ({
  Chart: { register: vi.fn() },
  CategoryScale: vi.fn(),
  LinearScale: vi.fn(),
  PointElement: vi.fn(),
  LineElement: vi.fn(),
  Title: vi.fn(),
  Tooltip: vi.fn(),
  Legend: vi.fn(),
}));

const severities = ['low', 'medium', 'high', 'critical'] as const;

const fakeSiteAlertArbitrary: fc.Arbitrary<Alert> = fc.record({
  id: fc.integer({ min: 1, max: 10000 }),
  site_id: fc.integer({ min: 1, max: 100 }),
  site_name: fc.string({ minLength: 1, maxLength: 20 }).filter(s => s.trim().length > 0),
  severity: fc.constantFrom(...severities),
  message: fc.string({ minLength: 1, maxLength: 50 }).filter(s => s.trim().length > 0),
  alert_type: fc.constant('fake_site' as string),
  violation_type: fc.constant('fake_site' as string),
  created_at: fc.constant('2024-01-15T10:00:00Z'),
  is_resolved: fc.boolean(),
  fake_domain: fc.domain().map(d => d as string | undefined),
  legitimate_domain: fc.domain().map(d => d as string | undefined),
  domain_similarity_score: fc.double({ min: 0, max: 1, noNaN: true }).map(d => d as number | undefined),
  content_similarity_score: fc.double({ min: 0, max: 1, noNaN: true }).map(d => d as number | undefined),
});

/**
 * Property 8: 偽サイトアラート表示の完全性
 * **Validates: Requirements 6.4**
 *
 * For any fake site alert displayed on the 偽サイト検知ページ, the rendered output
 * shall include the detected fake domain name, similarity score, detection datetime,
 * and resolution status.
 */
describe('Property 8: 偽サイトアラート表示の完全性', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('displays all required fields for each fake site alert', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.array(fakeSiteAlertArbitrary, { minLength: 1, maxLength: 10 }).map(
          arr => arr.map((a, i) => ({ ...a, id: i + 1 }))
        ),
        async (alerts) => {
          vi.mocked(api.getAlerts).mockResolvedValue(alerts);

          const { unmount } = render(
            <BrowserRouter>
              <FakeSites />
            </BrowserRouter>
          );

          await screen.findByText('偽サイト検知');

          // Table component renders .table-card elements in card mobile view
          const alertCards = document.querySelectorAll('.table-card');
          expect(alertCards.length).toBe(alerts.length);

          alertCards.forEach((card, index) => {
            const alert = alerts[index];
            const cardText = card.textContent || '';

            // Verify fake_domain is displayed
            if (alert.fake_domain) {
              expect(cardText).toContain(alert.fake_domain);
            }

            // Verify legitimate_domain is displayed
            if (alert.legitimate_domain) {
              expect(cardText).toContain(alert.legitimate_domain);
            }

            // Verify domain_similarity_score is displayed
            if (alert.domain_similarity_score !== undefined) {
              expect(cardText).toContain(String(alert.domain_similarity_score));
            }

            // Verify content_similarity_score is displayed
            if (alert.content_similarity_score !== undefined) {
              expect(cardText).toContain(String(alert.content_similarity_score));
            }

            // Verify created_at (datetime) is displayed
            const dateStr = new Date(alert.created_at).toLocaleString();
            expect(cardText).toContain(dateStr);

            // Verify resolution status is displayed
            if (alert.is_resolved) {
              expect(cardText).toContain('解決済み');
            } else {
              expect(cardText).toContain('未解決');
            }
          });

          unmount();
        }
      ),
      { numRuns: 20 }
    );
  });

  it('shows loading state initially', () => {
    vi.mocked(api.getAlerts).mockReturnValue(new Promise(() => {}));

    render(
      <BrowserRouter>
        <FakeSites />
      </BrowserRouter>
    );

    expect(screen.getByText('読み込み中...')).toBeInTheDocument();
  });

  it('shows error state on fetch failure', async () => {
    vi.mocked(api.getAlerts).mockRejectedValue(new Error('Network error'));

    render(
      <BrowserRouter>
        <FakeSites />
      </BrowserRouter>
    );

    await screen.findByText('偽サイトアラートの取得に失敗しました');
  });

  it('shows empty state when no fake site alerts exist', async () => {
    vi.mocked(api.getAlerts).mockResolvedValue([]);

    render(
      <BrowserRouter>
        <FakeSites />
      </BrowserRouter>
    );

    await screen.findByText('偽サイトアラートはありません');
  });

  it('filters out non-fake_site alerts', async () => {
    const mixedAlerts: Alert[] = [
      {
        id: 1, site_id: 1, site_name: 'Site A', severity: 'critical',
        message: 'Fake detected', alert_type: 'fake_site', violation_type: 'fake_site',
        created_at: '2024-01-15T10:00:00Z', is_resolved: false,
        fake_domain: 'fake.com', legitimate_domain: 'real.com',
        domain_similarity_score: 0.9, content_similarity_score: 0.8,
      },
      {
        id: 2, site_id: 2, site_name: 'Site B', severity: 'high',
        message: 'Price changed', alert_type: 'price_change', violation_type: 'price',
        created_at: '2024-01-15T11:00:00Z', is_resolved: false,
      },
    ];

    vi.mocked(api.getAlerts).mockResolvedValue(mixedAlerts);

    render(
      <BrowserRouter>
        <FakeSites />
      </BrowserRouter>
    );

    await screen.findByText('偽サイト検知');

    // Table component renders .table-card elements in card mobile view
    const alertCards = document.querySelectorAll('.table-card');
    expect(alertCards.length).toBe(1);
    expect(alertCards[0].textContent).toContain('fake.com');
  });
});

/**
 * Task 13.4: ナビゲーションとルーティングのユニットテスト
 * **Validates: Requirements 6.1, 6.2**
 */
describe('ナビゲーションとルーティング', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getAlerts).mockResolvedValue([]);
    vi.mocked(api.getStatistics).mockResolvedValue({
      total_sites: 0, active_sites: 0, total_violations: 0,
      high_severity_violations: 0, success_rate: 0, last_crawl: null,
      fake_site_alerts: 0, unresolved_fake_site_alerts: 0,
    });
    vi.mocked(api.getMonitoringHistory).mockResolvedValue([]);
    vi.mocked(api.getSites).mockResolvedValue([]);
  });

  it('nav link "偽サイト検知" exists in the global navigation', async () => {
    // App includes its own BrowserRouter, so render directly
    render(<App />);

    const navLink = screen.getByRole('link', { name: '偽サイト検知' });
    expect(navLink).toBeInTheDocument();
    expect(navLink.getAttribute('href')).toBe('/fake-sites');
  });

  it('navigating to /fake-sites renders the FakeSites component', async () => {
    // Push to /fake-sites before rendering App (which uses BrowserRouter)
    window.history.pushState({}, '', '/fake-sites');

    render(<App />);

    await screen.findByText('偽サイト検知');
    expect(screen.getByText('偽サイト検知', { selector: 'h1' })).toBeInTheDocument();
  });
});
