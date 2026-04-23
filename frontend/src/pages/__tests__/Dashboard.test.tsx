import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import Dashboard from '../Dashboard';
import { TestQueryClientProvider } from '../../test/testQueryClient';
import * as api from '../../services/api';

// Mock chart.js to avoid canvas issues in jsdom
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

vi.mock('../../services/api', () => ({
  getStatistics: vi.fn(),
  getMonitoringHistory: vi.fn(),
}));

vi.mock('../../hooks/useAutoRefresh', () => ({
  useAutoRefresh: vi.fn(),
}));

const mockStatistics: api.Statistics = {
  total_sites: 10,
  active_sites: 8,
  total_violations: 5,
  high_severity_violations: 2,
  success_rate: 95.5,
  last_crawl: '2024-01-15T10:00:00Z',
  fake_site_alerts: 3,
  unresolved_fake_site_alerts: 1,
};

describe('Dashboard - Fake Site Stats Cards', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getStatistics).mockResolvedValue(mockStatistics);
    vi.mocked(api.getMonitoringHistory).mockResolvedValue([]);
  });

  it('should display fake site alert count', async () => {
    render(
      <TestQueryClientProvider>
        <BrowserRouter>
          <Dashboard />
        </BrowserRouter>
      </TestQueryClientProvider>
    );

    expect(await screen.findByText('偽サイト検知')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('should display unresolved fake site alert count', async () => {
    render(
      <TestQueryClientProvider>
        <BrowserRouter>
          <Dashboard />
        </BrowserRouter>
      </TestQueryClientProvider>
    );

    expect(await screen.findByText('偽サイト検知')).toBeInTheDocument();
    expect(screen.getByText('未解決: 1')).toBeInTheDocument();
  });

  it('should default to 0 when fake_site_alerts is undefined', async () => {
    const statsWithoutFake = { ...mockStatistics } as Record<string, unknown>;
    delete statsWithoutFake.fake_site_alerts;
    delete statsWithoutFake.unresolved_fake_site_alerts;
    vi.mocked(api.getStatistics).mockResolvedValue(statsWithoutFake as unknown as api.Statistics);

    render(
      <TestQueryClientProvider>
        <BrowserRouter>
          <Dashboard />
        </BrowserRouter>
      </TestQueryClientProvider>
    );

    expect(await screen.findByText('偽サイト検知')).toBeInTheDocument();
    expect(screen.getByText('未解決: 0')).toBeInTheDocument();
  });
});

describe('Dashboard - Help Modal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getStatistics).mockResolvedValue(mockStatistics);
    vi.mocked(api.getMonitoringHistory).mockResolvedValue([]);
  });

  it('should display help button with correct aria-label', async () => {
    render(
      <TestQueryClientProvider>
        <BrowserRouter>
          <Dashboard />
        </BrowserRouter>
      </TestQueryClientProvider>
    );

    const helpButton = await screen.findByRole('button', { name: 'ヘルプを表示' });
    expect(helpButton).toBeInTheDocument();
    expect(helpButton).toHaveTextContent('?');
  });

  it('should open help modal with dashboard content when help button is clicked', async () => {
    render(
      <TestQueryClientProvider>
        <BrowserRouter>
          <Dashboard />
        </BrowserRouter>
      </TestQueryClientProvider>
    );

    const helpButton = await screen.findByRole('button', { name: 'ヘルプを表示' });
    await userEvent.click(helpButton);

    expect(screen.getByText('統計ダッシュボードの使い方')).toBeInTheDocument();
    expect(screen.getByText('監視状況の全体像を把握したい')).toBeInTheDocument();
    expect(screen.getByText(/統計カード/)).toBeInTheDocument();
    expect(screen.getByText(/違反数推移グラフ/)).toBeInTheDocument();
    expect(screen.getByText(/30秒ごとに自動更新/)).toBeInTheDocument();
  });
});

