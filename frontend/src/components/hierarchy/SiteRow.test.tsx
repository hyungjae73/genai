import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import SiteRow from './SiteRow';
import type { Site } from '../../services/api';
import * as api from '../../services/api';

// Mock the API module
vi.mock('../../services/api', () => ({
  triggerCrawl: vi.fn(),
  getCrawlStatus: vi.fn(),
  getLatestCrawlResult: vi.fn(),
}));

describe('SiteRow', () => {
  const mockSite: Site = {
    id: 1,
    customer_id: 1,
    category_id: 1,
    url: 'https://example.com',
    name: 'Test Site',
    is_active: true,
    last_crawled_at: '2024-01-01T00:00:00Z',
    compliance_status: 'compliant',
    created_at: '2024-01-01T00:00:00Z',
  };

  const defaultProps = {
    site: mockSite,
    customerName: 'Test Customer',
    isExpanded: false,
    onToggle: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders site information correctly', () => {
    render(<MemoryRouter><SiteRow {...defaultProps} /></MemoryRouter>);
    
    expect(screen.getByText('Test Site')).toBeInTheDocument();
    expect(screen.getByText('https://example.com')).toBeInTheDocument();
    expect(screen.getByText('準拠')).toBeInTheDocument();
    expect(screen.getByText('有効')).toBeInTheDocument();
  });

  it('displays expand/collapse indicator', () => {
    const { rerender } = render(<MemoryRouter><SiteRow {...defaultProps} /></MemoryRouter>);
    expect(screen.getByText('▶')).toBeInTheDocument();
    
    rerender(<MemoryRouter><SiteRow {...defaultProps} isExpanded={true} /></MemoryRouter>);
    expect(screen.getByText('▼')).toBeInTheDocument();
  });

  it('calls onToggle when header is clicked', () => {
    const onToggle = vi.fn();
    render(<MemoryRouter><SiteRow {...defaultProps} onToggle={onToggle} /></MemoryRouter>);
    
    const header = screen.getByText('Test Site').closest('.site-row-header');
    fireEvent.click(header!);
    
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it('displays site detail panel when expanded', () => {
    render(<MemoryRouter><SiteRow {...defaultProps} isExpanded={true} /></MemoryRouter>);
    
    // Check that the tab navigation is displayed
    expect(screen.getByText('契約条件')).toBeInTheDocument();
    expect(screen.getByText('スクリーンショット')).toBeInTheDocument();
    expect(screen.getByText('検証・比較')).toBeInTheDocument();
    expect(screen.getByText('アラート')).toBeInTheDocument();
  });

  it('displays crawl button', () => {
    render(<MemoryRouter><SiteRow {...defaultProps} /></MemoryRouter>);
    
    expect(screen.getByText('今すぐクロール')).toBeInTheDocument();
  });

  it('triggers crawl when crawl button is clicked', async () => {
    const mockTriggerCrawl = vi.mocked(api.triggerCrawl);
    mockTriggerCrawl.mockResolvedValue({ job_id: 'test-job-id', status: 'pending' });
    
    const mockGetCrawlStatus = vi.mocked(api.getCrawlStatus);
    mockGetCrawlStatus.mockResolvedValue({ 
      job_id: 'test-job-id', 
      status: 'completed',
      result: {
        id: 1,
        site_id: 1,
        url: 'https://example.com',
        status_code: 200,
        screenshot_path: '/path/to/screenshot.png',
        crawled_at: '2024-01-02T00:00:00Z',
      }
    });
    
    const mockGetLatestCrawlResult = vi.mocked(api.getLatestCrawlResult);
    mockGetLatestCrawlResult.mockResolvedValue({
      id: 1,
      site_id: 1,
      url: 'https://example.com',
      status_code: 200,
      screenshot_path: '/path/to/screenshot.png',
      crawled_at: '2024-01-02T00:00:00Z',
    });
    
    render(<MemoryRouter><SiteRow {...defaultProps} /></MemoryRouter>);
    
    const crawlButton = screen.getByText('今すぐクロール');
    fireEvent.click(crawlButton);
    
    expect(mockTriggerCrawl).toHaveBeenCalledWith(1);
    
    // Wait for crawling state to show
    await waitFor(() => {
      expect(screen.getByText(/クロール中/)).toBeInTheDocument();
    });
  });

  it('displays error message when crawl fails', async () => {
    const mockTriggerCrawl = vi.mocked(api.triggerCrawl);
    mockTriggerCrawl.mockRejectedValue(new Error('Crawl failed'));
    
    render(<MemoryRouter><SiteRow {...defaultProps} /></MemoryRouter>);
    
    const crawlButton = screen.getByText('今すぐクロール');
    fireEvent.click(crawlButton);
    
    await waitFor(() => {
      expect(screen.getByText('クロールの開始に失敗しました')).toBeInTheDocument();
    });
  });

  it('displays conflict error when crawl is already running', async () => {
    const mockTriggerCrawl = vi.mocked(api.triggerCrawl);
    const conflictError = new Error('Conflict');
    (conflictError as any).response = { status: 409 };
    mockTriggerCrawl.mockRejectedValue(conflictError);
    
    render(<MemoryRouter><SiteRow {...defaultProps} /></MemoryRouter>);
    
    const crawlButton = screen.getByText('今すぐクロール');
    fireEvent.click(crawlButton);
    
    await waitFor(() => {
      expect(screen.getByText('クロールが実行中です')).toBeInTheDocument();
    });
  });

  it('formats last crawl date correctly', () => {
    render(<MemoryRouter><SiteRow {...defaultProps} /></MemoryRouter>);
    
    // The date should be formatted in Japanese locale
    expect(screen.getByText(/2024/)).toBeInTheDocument();
  });

  it('displays "未実行" when last_crawled_at is null', () => {
    const siteWithoutCrawl = { ...mockSite, last_crawled_at: null };
    render(<MemoryRouter><SiteRow {...defaultProps} site={siteWithoutCrawl} /></MemoryRouter>);
    
    expect(screen.getByText('未実行')).toBeInTheDocument();
  });

  it('displays category or "未分類"', () => {
    const { rerender } = render(<MemoryRouter><SiteRow {...defaultProps} /></MemoryRouter>);
    expect(screen.getByText(/カテゴリ 1/)).toBeInTheDocument();
    
    const siteWithoutCategory = { ...mockSite, category_id: null };
    rerender(<MemoryRouter><SiteRow {...defaultProps} site={siteWithoutCategory} /></MemoryRouter>);
    expect(screen.getByText('未分類')).toBeInTheDocument();
  });

  it('calls onCrawlComplete when crawl completes', async () => {
    const onCrawlComplete = vi.fn();
    
    const mockTriggerCrawl = vi.mocked(api.triggerCrawl);
    mockTriggerCrawl.mockResolvedValue({ job_id: 'test-job-id', status: 'pending' });
    
    const mockGetCrawlStatus = vi.mocked(api.getCrawlStatus);
    mockGetCrawlStatus.mockResolvedValue({ 
      job_id: 'test-job-id', 
      status: 'completed',
      result: {
        id: 1,
        site_id: 1,
        url: 'https://example.com',
        status_code: 200,
        screenshot_path: '/path/to/screenshot.png',
        crawled_at: '2024-01-02T00:00:00Z',
      }
    });
    
    const mockGetLatestCrawlResult = vi.mocked(api.getLatestCrawlResult);
    mockGetLatestCrawlResult.mockResolvedValue({
      id: 1,
      site_id: 1,
      url: 'https://example.com',
      status_code: 200,
      screenshot_path: '/path/to/screenshot.png',
      crawled_at: '2024-01-02T00:00:00Z',
    });
    
    render(<MemoryRouter><SiteRow {...defaultProps} onCrawlComplete={onCrawlComplete} /></MemoryRouter>);
    
    const crawlButton = screen.getByText('今すぐクロール');
    fireEvent.click(crawlButton);
    
    await waitFor(() => {
      expect(onCrawlComplete).toHaveBeenCalled();
    }, { timeout: 3000 });
  });
});
