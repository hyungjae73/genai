import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import CrawlResultModal from './CrawlResultModal';
import * as api from '../../services/api';

vi.mock('../../services/api');

describe('CrawlResultModal', () => {
  const mockOnClose = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('displays loading state initially', () => {
    vi.mocked(api.getCrawlStatus).mockImplementation(() => new Promise(() => {}));
    
    render(<CrawlResultModal jobId="test-job-123" onClose={mockOnClose} />);
    
    expect(screen.getByText('結果を読み込み中...')).toBeInTheDocument();
  });

  it('displays error when crawl status fetch fails', async () => {
    vi.mocked(api.getCrawlStatus).mockRejectedValue(new Error('Network error'));
    
    render(<CrawlResultModal jobId="test-job-123" onClose={mockOnClose} />);
    
    await waitFor(() => {
      expect(screen.getByText('結果の取得に失敗しました')).toBeInTheDocument();
    });
  });

  it('displays error when crawl failed', async () => {
    vi.mocked(api.getCrawlStatus).mockResolvedValue({
      job_id: 'test-job-123',
      status: 'failed',
      result: null
    });
    
    render(<CrawlResultModal jobId="test-job-123" onClose={mockOnClose} />);
    
    await waitFor(() => {
      expect(screen.getByText('クロールに失敗しました')).toBeInTheDocument();
    });
  });

  it('displays success message when no violations detected', async () => {
    vi.mocked(api.getCrawlStatus).mockResolvedValue({
      job_id: 'test-job-123',
      status: 'completed',
      result: {
        site_id: 1,
        url: 'https://example.com',
        status: 'success',
        violations: [],
        alerts_sent: false,
        error: null
      }
    });
    
    render(<CrawlResultModal jobId="test-job-123" onClose={mockOnClose} />);
    
    await waitFor(() => {
      expect(screen.getByText('違反は検出されませんでした')).toBeInTheDocument();
      expect(screen.getByText('https://example.com')).toBeInTheDocument();
    });
  });

  it('displays violations when detected', async () => {
    vi.mocked(api.getCrawlStatus).mockResolvedValue({
      job_id: 'test-job-123',
      status: 'completed',
      result: {
        site_id: 1,
        url: 'https://example.com',
        status: 'success',
        violations: [
          {
            type: 'price_mismatch',
            severity: 'high',
            field: 'price',
            message: '価格が契約条件と一致しません'
          },
          {
            type: 'payment_method_missing',
            severity: 'medium',
            field: 'payment_methods',
            message: '必須の支払い方法が見つかりません'
          }
        ],
        alerts_sent: true,
        error: null
      }
    });
    
    render(<CrawlResultModal jobId="test-job-123" onClose={mockOnClose} />);
    
    await waitFor(() => {
      expect(screen.getByText('検出された違反 (2件)')).toBeInTheDocument();
      expect(screen.getByText('価格が契約条件と一致しません')).toBeInTheDocument();
      expect(screen.getByText('必須の支払い方法が見つかりません')).toBeInTheDocument();
      expect(screen.getByText('アラートが送信されました')).toBeInTheDocument();
    });
  });

  it('displays error message from result', async () => {
    vi.mocked(api.getCrawlStatus).mockResolvedValue({
      job_id: 'test-job-123',
      status: 'completed',
      result: {
        site_id: 1,
        url: 'https://example.com',
        status: 'error',
        violations: [],
        alerts_sent: false,
        error: 'Connection timeout'
      }
    });
    
    render(<CrawlResultModal jobId="test-job-123" onClose={mockOnClose} />);
    
    await waitFor(() => {
      expect(screen.getByText('Connection timeout')).toBeInTheDocument();
    });
  });

  it('closes modal when close button is clicked', async () => {
    vi.mocked(api.getCrawlStatus).mockResolvedValue({
      job_id: 'test-job-123',
      status: 'completed',
      result: {
        site_id: 1,
        url: 'https://example.com',
        status: 'success',
        violations: [],
        alerts_sent: false,
        error: null
      }
    });
    
    render(<CrawlResultModal jobId="test-job-123" onClose={mockOnClose} />);
    
    await waitFor(() => {
      expect(screen.getByText('違反は検出されませんでした')).toBeInTheDocument();
    });
    
    const closeButton = screen.getByText('×');
    await userEvent.click(closeButton);
    
    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  it('closes modal when footer close button is clicked', async () => {
    vi.mocked(api.getCrawlStatus).mockResolvedValue({
      job_id: 'test-job-123',
      status: 'completed',
      result: {
        site_id: 1,
        url: 'https://example.com',
        status: 'success',
        violations: [],
        alerts_sent: false,
        error: null
      }
    });
    
    render(<CrawlResultModal jobId="test-job-123" onClose={mockOnClose} />);
    
    await waitFor(() => {
      expect(screen.getByText('違反は検出されませんでした')).toBeInTheDocument();
    });
    
    const closeButton = screen.getByText('閉じる');
    await userEvent.click(closeButton);
    
    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  it('closes modal when overlay is clicked', async () => {
    vi.mocked(api.getCrawlStatus).mockResolvedValue({
      job_id: 'test-job-123',
      status: 'completed',
      result: {
        site_id: 1,
        url: 'https://example.com',
        status: 'success',
        violations: [],
        alerts_sent: false,
        error: null
      }
    });
    
    const { container } = render(<CrawlResultModal jobId="test-job-123" onClose={mockOnClose} />);
    
    await waitFor(() => {
      expect(screen.getByText('違反は検出されませんでした')).toBeInTheDocument();
    });
    
    const overlay = container.querySelector('.modal-overlay');
    if (overlay) {
      await userEvent.click(overlay);
      expect(mockOnClose).toHaveBeenCalledTimes(1);
    }
  });

  it('displays severity badges correctly', async () => {
    vi.mocked(api.getCrawlStatus).mockResolvedValue({
      job_id: 'test-job-123',
      status: 'completed',
      result: {
        site_id: 1,
        url: 'https://example.com',
        status: 'success',
        violations: [
          { type: 'test1', severity: 'low', field: 'field1', message: 'msg1' },
          { type: 'test2', severity: 'medium', field: 'field2', message: 'msg2' },
          { type: 'test3', severity: 'high', field: 'field3', message: 'msg3' },
          { type: 'test4', severity: 'critical', field: 'field4', message: 'msg4' }
        ],
        alerts_sent: false,
        error: null
      }
    });
    
    render(<CrawlResultModal jobId="test-job-123" onClose={mockOnClose} />);
    
    await waitFor(() => {
      expect(screen.getByText('低')).toBeInTheDocument();
      expect(screen.getByText('中')).toBeInTheDocument();
      expect(screen.getByText('高')).toBeInTheDocument();
      expect(screen.getByText('重大')).toBeInTheDocument();
    });
  });
});
