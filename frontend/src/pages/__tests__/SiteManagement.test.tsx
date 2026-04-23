import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import SiteManagement from '../SiteManagement';
import App from '../../App';
import * as api from '../../services/api';
import { TestQueryClientProvider } from '../../test/testQueryClient';

// Mock API calls used by SiteManagement
vi.mock('../../services/api', () => ({
  getCustomers: vi.fn(),
  getSites: vi.fn(),
  getCategories: vi.fn(),
  // Needed when rendering full App (Dashboard, Alerts, etc.)
  getStatistics: vi.fn(),
  getMonitoringHistory: vi.fn(),
  getAlerts: vi.fn(),
}));

vi.mock('../../hooks/useAutoRefresh', () => ({
  useAutoRefresh: vi.fn(),
}));

// Mock AuthContext so ProtectedRoute allows access
vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 1, username: 'admin', role: 'admin' },
    accessToken: 'test-token',
    isAuthenticated: true,
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
    refreshToken: vi.fn(),
    hasRole: (...roles: string[]) => roles.includes('admin'),
  }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
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

/**
 * Task 2.3: リネームとルーティングのユニットテスト
 * **Validates: Requirements 1.1, 1.3, 1.4, 2.7, 3.7**
 */
describe('SiteManagement - ページタイトル', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getCustomers).mockResolvedValue([]);
    vi.mocked(api.getSites).mockResolvedValue([]);
    vi.mocked(api.getCategories).mockResolvedValue([]);
  });

  it('should display "サイト管理" as the page title in <h1>', async () => {
    render(
      <TestQueryClientProvider>
        <MemoryRouter>
          <SiteManagement />
        </MemoryRouter>
      </TestQueryClientProvider>
    );

    const heading = await screen.findByRole('heading', { level: 1 });
    expect(heading).toHaveTextContent('サイト管理');
  });
});

describe('SiteManagement - ルーティング', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getCustomers).mockResolvedValue([]);
    vi.mocked(api.getSites).mockResolvedValue([]);
    vi.mocked(api.getCategories).mockResolvedValue([]);
    vi.mocked(api.getStatistics).mockResolvedValue({
      total_sites: 0, active_sites: 0, total_violations: 0,
      high_severity_violations: 0, success_rate: 0, last_crawl: null,
      fake_site_alerts: 0, unresolved_fake_site_alerts: 0,
    });
    vi.mocked(api.getMonitoringHistory).mockResolvedValue([]);
    vi.mocked(api.getAlerts).mockResolvedValue([]);
  });

  it('renders SiteManagement page at /site-management', async () => {
    window.history.pushState({}, '', '/site-management');

    render(<App />);

    expect(await screen.findByText('サイト管理')).toBeInTheDocument();
  });

  it('redirects /hierarchy to /site-management', async () => {
    window.history.pushState({}, '', '/hierarchy');

    render(<App />);

    expect(await screen.findByRole('heading', { name: /サイト管理/ })).toBeInTheDocument();
  });

  it('redirects /screenshots to /site-management', async () => {
    window.history.pushState({}, '', '/screenshots');

    render(<App />);

    expect(await screen.findByRole('heading', { name: /サイト管理/ })).toBeInTheDocument();
  });

  it('redirects /verification to /site-management', async () => {
    window.history.pushState({}, '', '/verification');

    render(<App />);

    expect(await screen.findByRole('heading', { name: /サイト管理/ })).toBeInTheDocument();
  });
});


/**
 * Task 9.3: SiteManagement ページにヘルプモーダルを追加
 * **Validates: Requirements 6.1, 6.2, 6.5**
 */
describe('SiteManagement - ヘルプモーダル', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getCustomers).mockResolvedValue([]);
    vi.mocked(api.getSites).mockResolvedValue([]);
    vi.mocked(api.getCategories).mockResolvedValue([]);
  });

  it('should display a help button with aria-label "ヘルプを表示"', async () => {
    render(
      <TestQueryClientProvider>
        <MemoryRouter>
          <SiteManagement />
        </MemoryRouter>
      </TestQueryClientProvider>
    );

    await screen.findByRole('heading', { level: 1 });
    const helpButton = screen.getByRole('button', { name: 'ヘルプを表示' });
    expect(helpButton).toBeInTheDocument();
    expect(helpButton).toHaveTextContent('?');
  });

  it('should open help modal with site management content when help button is clicked', async () => {
    const user = userEvent.setup();

    render(
      <TestQueryClientProvider>
        <MemoryRouter>
          <SiteManagement />
        </MemoryRouter>
      </TestQueryClientProvider>
    );

    await screen.findByRole('heading', { level: 1 });
    const helpButton = screen.getByRole('button', { name: 'ヘルプを表示' });
    await user.click(helpButton);

    expect(screen.getByText('サイト管理の使い方')).toBeInTheDocument();
    expect(screen.getByText(/顧客→サイトの階層構造でサイトを管理/)).toBeInTheDocument();
    expect(screen.getByText('できること')).toBeInTheDocument();
    expect(screen.getByText('詳細タブ')).toBeInTheDocument();
  });
});
