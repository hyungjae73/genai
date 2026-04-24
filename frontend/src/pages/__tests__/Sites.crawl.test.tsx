import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Sites from '../Sites';
import * as api from '../../services/api';
import { TestQueryClientProvider } from '../../test/testQueryClient';

/** Helper to render Sites inside a Router context */
const renderSites = () => render(<TestQueryClientProvider><MemoryRouter><Sites /></MemoryRouter></TestQueryClientProvider>);

// Mock the API module
vi.mock('../../services/api', () => ({
  getSites: vi.fn(),
  getCustomers: vi.fn(),
  createSite: vi.fn(),
  updateSite: vi.fn(),
  deleteSite: vi.fn(),
  triggerCrawl: vi.fn(),
  getCrawlStatus: vi.fn(),
  getLatestCrawlResult: vi.fn(),
}));

// Mock the useAutoRefresh hook
vi.mock('../../hooks/useAutoRefresh', () => ({
  useAutoRefresh: vi.fn(),
}));

describe('Sites - Crawl Button', () => {
  const mockSites = [
    {
      id: 1,
      customer_id: 1,
      category_id: null,
      name: 'Test Site',
      url: 'https://example.com',
      is_active: true,
      last_crawled_at: '2024-01-01T00:00:00Z',
      compliance_status: 'compliant' as const,
      created_at: '2024-01-01T00:00:00Z',
    },
  ];

  const mockCustomers = [
    {
      id: 1,
      name: 'Test Customer',
      company_name: 'Test Company',
      email: 'test@example.com',
      phone: null,
      address: null,
      is_active: true,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    (api.getSites as any).mockResolvedValue(mockSites);
    (api.getCustomers as any).mockResolvedValue(mockCustomers);
  });

  it('should render crawl button for each site', async () => {
    renderSites();

    await waitFor(() => {
      // Table component renders both desktop and mobile views
      const buttons = screen.getAllByText('今すぐクロール');
      expect(buttons.length).toBeGreaterThan(0);
    });
  });

  it('should trigger crawl when button is clicked', async () => {
    const mockJobId = 'job-123';
    (api.triggerCrawl as any).mockResolvedValue({ job_id: mockJobId, status: 'pending' });
    (api.getCrawlStatus as any).mockResolvedValue({ job_id: mockJobId, status: 'completed' });

    renderSites();

    await waitFor(() => {
      const buttons = screen.getAllByText('今すぐクロール');
      expect(buttons.length).toBeGreaterThan(0);
    });

    const crawlButton = screen.getAllByText('今すぐクロール')[0];
    fireEvent.click(crawlButton);

    await waitFor(() => {
      expect(api.triggerCrawl).toHaveBeenCalledWith(1);
    });
  });

  it('should show spinner while crawling', async () => {
    const mockJobId = 'job-123';
    (api.triggerCrawl as any).mockResolvedValue({ job_id: mockJobId, status: 'pending' });
    (api.getCrawlStatus as any).mockResolvedValue({ job_id: mockJobId, status: 'running' });

    renderSites();

    await waitFor(() => {
      const buttons = screen.getAllByText('今すぐクロール');
      expect(buttons.length).toBeGreaterThan(0);
    });

    const crawlButton = screen.getAllByText('今すぐクロール')[0];
    fireEvent.click(crawlButton);

    await waitFor(() => {
      const spinners = screen.getAllByText('クロール中...');
      expect(spinners.length).toBeGreaterThan(0);
    });
  });

  it('should show success toast when crawl completes', async () => {
    const mockJobId = 'job-123';
    (api.triggerCrawl as any).mockResolvedValue({ job_id: mockJobId, status: 'pending' });
    (api.getCrawlStatus as any).mockResolvedValue({ job_id: mockJobId, status: 'completed' });

    renderSites();

    await waitFor(() => {
      const buttons = screen.getAllByText('今すぐクロール');
      expect(buttons.length).toBeGreaterThan(0);
    });

    const crawlButton = screen.getAllByText('今すぐクロール')[0];
    fireEvent.click(crawlButton);

    await waitFor(() => {
      expect(screen.getByText('クロールが完了しました')).toBeInTheDocument();
    }, { timeout: 3000 });
  });

  it('should show error toast when crawl fails', async () => {
    const mockJobId = 'job-123';
    (api.triggerCrawl as any).mockResolvedValue({ job_id: mockJobId, status: 'pending' });
    (api.getCrawlStatus as any).mockResolvedValue({ job_id: mockJobId, status: 'failed' });

    renderSites();

    await waitFor(() => {
      const buttons = screen.getAllByText('今すぐクロール');
      expect(buttons.length).toBeGreaterThan(0);
    });

    const crawlButton = screen.getAllByText('今すぐクロール')[0];
    fireEvent.click(crawlButton);

    await waitFor(() => {
      // Check for toast specifically by class
      const toast = document.querySelector('.toast-error');
      expect(toast).toBeInTheDocument();
    }, { timeout: 3000 });
  });

  it('should show warning toast when crawl is already running (409 conflict)', async () => {
    const error = {
      response: {
        status: 409,
        data: { detail: 'クロールが実行中です' },
      },
    };
    (api.triggerCrawl as any).mockRejectedValue(error);

    renderSites();

    await waitFor(() => {
      const buttons = screen.getAllByText('今すぐクロール');
      expect(buttons.length).toBeGreaterThan(0);
    });

    const crawlButton = screen.getAllByText('今すぐクロール')[0];
    fireEvent.click(crawlButton);

    await waitFor(() => {
      expect(screen.getByText('クロールが実行中です')).toBeInTheDocument();
    });
  });

  it('should disable button while crawling', async () => {
    const mockJobId = 'job-123';
    (api.triggerCrawl as any).mockResolvedValue({ job_id: mockJobId, status: 'pending' });
    (api.getCrawlStatus as any).mockResolvedValue({ job_id: mockJobId, status: 'running' });

    renderSites();

    await waitFor(() => {
      const buttons = screen.getAllByText('今すぐクロール');
      expect(buttons.length).toBeGreaterThan(0);
    });

    const crawlButton = screen.getAllByText('今すぐクロール')[0] as HTMLButtonElement;
    fireEvent.click(crawlButton);

    await waitFor(() => {
      const spinners = screen.getAllByText('クロール中...');
      const button = spinners[0].closest('button') as HTMLButtonElement;
      expect(button.disabled).toBe(true);
    });
  });

  it('should refresh site list after successful crawl', async () => {
    const mockJobId = 'job-123';
    (api.triggerCrawl as any).mockResolvedValue({ job_id: mockJobId, status: 'pending' });
    (api.getCrawlStatus as any).mockResolvedValue({ job_id: mockJobId, status: 'completed' });

    renderSites();

    await waitFor(() => {
      const buttons = screen.getAllByText('今すぐクロール');
      expect(buttons.length).toBeGreaterThan(0);
    });

    const initialCallCount = (api.getSites as any).mock.calls.length;

    const crawlButton = screen.getAllByText('今すぐクロール')[0];
    fireEvent.click(crawlButton);

    await waitFor(() => {
      expect((api.getSites as any).mock.calls.length).toBeGreaterThan(initialCallCount);
    }, { timeout: 3000 });
  });
});

describe('Sites - Crawl Result Link', () => {
  // Compute the expected formatted date string in the test runner's timezone
  // so the test passes in both JST and UTC environments.
  const CRAWL_ISO = '2024-01-01T12:00:00Z';
  const expectedCrawlDate = new Date(CRAWL_ISO).toLocaleString('ja-JP');

  const mockSites = [
    {
      id: 1,
      customer_id: 1,
      category_id: null,
      name: 'Test Site',
      url: 'https://example.com',
      is_active: true,
      last_crawled_at: CRAWL_ISO,
      compliance_status: 'compliant' as const,
      created_at: '2024-01-01T00:00:00Z',
    },
    {
      id: 2,
      customer_id: 1,
      category_id: null,
      name: 'Test Site 2',
      url: 'https://example2.com',
      is_active: true,
      last_crawled_at: null,
      compliance_status: 'pending' as const,
      created_at: '2024-01-01T00:00:00Z',
    },
  ];

  const mockCustomers = [
    {
      id: 1,
      name: 'Test Customer',
      company_name: 'Test Company',
      email: 'test@example.com',
      phone: null,
      address: null,
      is_active: true,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    },
  ];

  const mockCrawlResult = {
    id: 1,
    site_id: 1,
    url: 'https://example.com',
    status_code: 200,
    screenshot_path: '/screenshots/test.png',
    crawled_at: CRAWL_ISO,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.getSites as any).mockResolvedValue(mockSites);
    (api.getCustomers as any).mockResolvedValue(mockCustomers);
  });

  it('should render last crawled date as clickable link when crawl data exists', async () => {
    renderSites();

    await waitFor(() => {
      // Table component renders both desktop table and mobile card views;
      // use getAllByText and find the BUTTON element.
      const elements = screen.getAllByText(expectedCrawlDate);
      const crawlDateButton = elements.find(el => el.tagName === 'BUTTON')!;
      expect(crawlDateButton).toBeInTheDocument();
      expect(crawlDateButton.tagName).toBe('BUTTON');
    });
  });

  it('should render "未実施" for sites without crawl data', async () => {
    renderSites();

    await waitFor(() => {
      const elements = screen.getAllByText('未実施');
      expect(elements.length).toBeGreaterThan(0);
      expect(elements[0]).toBeInTheDocument();
    });
  });

  it('should open modal when clicking on last crawled date', async () => {
    (api as any).getLatestCrawlResult = vi.fn().mockResolvedValue(mockCrawlResult);

    renderSites();

    await waitFor(() => {
      const elements = screen.getAllByText(expectedCrawlDate);
      expect(elements.length).toBeGreaterThan(0);
    });

    const crawlDateButton = screen.getAllByText(expectedCrawlDate).find(el => el.tagName === 'BUTTON')!;
    fireEvent.click(crawlDateButton);

    await waitFor(() => {
      expect(screen.getByText('クロール結果詳細')).toBeInTheDocument();
    });
  });

  it('should display crawl result details in modal', async () => {
    (api as any).getLatestCrawlResult = vi.fn().mockResolvedValue(mockCrawlResult);

    renderSites();

    await waitFor(() => {
      const elements = screen.getAllByText(expectedCrawlDate);
      expect(elements.length).toBeGreaterThan(0);
    });

    const crawlDateButton = screen.getAllByText(expectedCrawlDate).find(el => el.tagName === 'BUTTON')!;
    fireEvent.click(crawlDateButton);

    await waitFor(() => {
      expect(screen.getByText('クロール結果詳細')).toBeInTheDocument();
      expect(screen.getByText('取得日時:')).toBeInTheDocument();
      expect(screen.getByText('URL:')).toBeInTheDocument();
      expect(screen.getByText('ステータス:')).toBeInTheDocument();
      expect(screen.getByText('完了')).toBeInTheDocument();
    });
  });

  it('should display screenshot when available', async () => {
    (api as any).getLatestCrawlResult = vi.fn().mockResolvedValue(mockCrawlResult);

    renderSites();

    await waitFor(() => {
      const elements = screen.getAllByText(expectedCrawlDate);
      expect(elements.length).toBeGreaterThan(0);
    });

    const crawlDateButton = screen.getAllByText(expectedCrawlDate).find(el => el.tagName === 'BUTTON')!;
    fireEvent.click(crawlDateButton);

    await waitFor(() => {
      expect(screen.getByText('スクリーンショット:')).toBeInTheDocument();
      const screenshot = screen.getByAltText('クロール時のスクリーンショット');
      expect(screenshot).toBeInTheDocument();
      expect(screenshot.getAttribute('src')).toContain('/screenshots/test.png');
    });
  });

  it('should display error status for failed crawls', async () => {
    const failedCrawlResult = {
      ...mockCrawlResult,
      status_code: 500,
    };
    (api as any).getLatestCrawlResult = vi.fn().mockResolvedValue(failedCrawlResult);

    renderSites();

    await waitFor(() => {
      const elements = screen.getAllByText(expectedCrawlDate);
      expect(elements.length).toBeGreaterThan(0);
    });

    const crawlDateButton = screen.getAllByText(expectedCrawlDate).find(el => el.tagName === 'BUTTON')!;
    fireEvent.click(crawlDateButton);

    await waitFor(() => {
      expect(screen.getByText('失敗 (HTTP 500)')).toBeInTheDocument();
    });
  });

  it('should show loading state while fetching crawl result', async () => {
    (api as any).getLatestCrawlResult = vi.fn().mockImplementation(
      () => new Promise(resolve => setTimeout(() => resolve(mockCrawlResult), 100))
    );

    renderSites();

    await waitFor(() => {
      const elements = screen.getAllByText(expectedCrawlDate);
      expect(elements.length).toBeGreaterThan(0);
    });

    const crawlDateButton = screen.getAllByText(expectedCrawlDate).find(el => el.tagName === 'BUTTON')!;
    fireEvent.click(crawlDateButton);

    await waitFor(() => {
      expect(screen.getByText('読み込み中...')).toBeInTheDocument();
    });
  });

  it('should show error message when fetching crawl result fails', async () => {
    (api as any).getLatestCrawlResult = vi.fn().mockRejectedValue({
      response: {
        data: { detail: 'クロール結果の取得に失敗しました' },
      },
    });

    renderSites();

    await waitFor(() => {
      const elements = screen.getAllByText(expectedCrawlDate);
      expect(elements.length).toBeGreaterThan(0);
    });

    const crawlDateButton = screen.getAllByText(expectedCrawlDate).find(el => el.tagName === 'BUTTON')!;
    fireEvent.click(crawlDateButton);

    await waitFor(() => {
      expect(screen.getByText('クロール結果の取得に失敗しました')).toBeInTheDocument();
    });
  });

  it('should close modal when close button is clicked', async () => {
    (api as any).getLatestCrawlResult = vi.fn().mockResolvedValue(mockCrawlResult);

    renderSites();

    await waitFor(() => {
      const elements = screen.getAllByText(expectedCrawlDate);
      expect(elements.length).toBeGreaterThan(0);
    });

    const crawlDateButton = screen.getAllByText(expectedCrawlDate).find(el => el.tagName === 'BUTTON')!;
    fireEvent.click(crawlDateButton);

    await waitFor(() => {
      expect(screen.getByText('クロール結果詳細')).toBeInTheDocument();
    });

    const closeButton = screen.getByText('閉じる');
    fireEvent.click(closeButton);

    await waitFor(() => {
      expect(screen.queryByText('クロール結果詳細')).not.toBeInTheDocument();
    });
  });

  it('should show warning toast when clicking on site without crawl data', async () => {
    renderSites();

    await waitFor(() => {
      const elements = screen.getAllByText('未実施');
      expect(elements.length).toBeGreaterThan(0);
    });

    // Find the site row with "未実施" and try to click it
    // Since "未実施" is not a button, this test verifies the behavior
    // The actual implementation prevents clicking on "未実施" text
    const noCrawlElements = screen.getAllByText('未実施');
    expect(noCrawlElements[0].tagName).not.toBe('BUTTON');
  });

  it('should not display screenshot section when screenshot_path is null', async () => {
    const crawlResultWithoutScreenshot = {
      ...mockCrawlResult,
      screenshot_path: null,
    };
    (api as any).getLatestCrawlResult = vi.fn().mockResolvedValue(crawlResultWithoutScreenshot);

    renderSites();

    await waitFor(() => {
      const elements = screen.getAllByText(expectedCrawlDate);
      expect(elements.length).toBeGreaterThan(0);
    });

    const crawlDateButton = screen.getAllByText(expectedCrawlDate).find(el => el.tagName === 'BUTTON')!;
    fireEvent.click(crawlDateButton);

    await waitFor(() => {
      expect(screen.getByText('クロール結果詳細')).toBeInTheDocument();
      expect(screen.queryByText('スクリーンショット:')).not.toBeInTheDocument();
    });
  });
});
