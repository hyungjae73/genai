import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import ScreenshotTab from './ScreenshotTab';
import * as api from '../../../services/api';
import type { Screenshot } from '../../../services/api';

// Mock the API module
vi.mock('../../../services/api', () => ({
  getSiteScreenshots: vi.fn(),
  extractData: vi.fn(),
  getExtractedData: vi.fn(),
  updateExtractedData: vi.fn(),
  getScreenshotUrl: vi.fn((id: number) => `http://localhost/api/screenshots/view/${id}`),
  uploadScreenshot: vi.fn(),
  captureScreenshot: vi.fn(),
  deleteScreenshot: vi.fn(),
}));

const mockBaseline: Screenshot = {
  id: 1,
  site_id: 100,
  site_name: 'テストサイト',
  screenshot_type: 'baseline',
  file_path: '/screenshots/baseline.png',
  file_format: 'png',
  crawled_at: '2024-06-01T10:00:00Z',
};

const mockMonitoring: Screenshot = {
  id: 2,
  site_id: 100,
  site_name: 'テストサイト',
  screenshot_type: 'violation',
  file_path: '/screenshots/monitoring.png',
  file_format: 'png',
  crawled_at: '2024-06-15T12:00:00Z',
};

describe('ScreenshotTab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: getExtractedData rejects (no extracted data)
    vi.mocked(api.getExtractedData).mockRejectedValue(new Error('Not found'));
  });

  // Requirement 2.1: ベースラインスクリーンショットの表示
  it('displays the baseline screenshot section with baseline image', async () => {
    vi.mocked(api.getSiteScreenshots).mockResolvedValue([mockBaseline, mockMonitoring]);

    render(<ScreenshotTab siteId={100} />);

    await waitFor(() => {
      const baselineSection = screen.getByTestId('baseline-section');
      expect(baselineSection).toBeInTheDocument();
      expect(baselineSection).toHaveTextContent('ベースラインスクリーンショット');
    });

    // Baseline badge should be visible
    expect(screen.getByText('ベースライン')).toBeInTheDocument();
  });

  // Requirement 2.2: 最新モニタリングキャプチャの表示
  it('displays the monitoring section with latest monitoring capture', async () => {
    vi.mocked(api.getSiteScreenshots).mockResolvedValue([mockBaseline, mockMonitoring]);

    render(<ScreenshotTab siteId={100} />);

    await waitFor(() => {
      const monitoringSection = screen.getByTestId('monitoring-section');
      expect(monitoringSection).toBeInTheDocument();
      expect(monitoringSection).toHaveTextContent('最新モニタリングキャプチャ');
    });

    // Monitoring badge should be visible
    expect(screen.getByText('モニタリング')).toBeInTheDocument();
  });

  // Requirement 2.3: 再キャプチャボタンの存在
  it('displays the re-capture button in the monitoring section', async () => {
    vi.mocked(api.getSiteScreenshots).mockResolvedValue([mockBaseline, mockMonitoring]);

    render(<ScreenshotTab siteId={100} />);

    await waitFor(() => {
      expect(screen.getByText('📸 再キャプチャ')).toBeInTheDocument();
    });
  });

  // Requirement 2.4: 再アップロードボタンの存在
  it('displays the re-upload button in the baseline section', async () => {
    vi.mocked(api.getSiteScreenshots).mockResolvedValue([mockBaseline, mockMonitoring]);

    render(<ScreenshotTab siteId={100} />);

    await waitFor(() => {
      expect(screen.getByText('📤 再アップロード')).toBeInTheDocument();
    });
  });

  // Requirement 2.6: タイプセレクターが非表示
  it('does not display a screenshot type selector in upload modal', async () => {
    vi.mocked(api.getSiteScreenshots).mockResolvedValue([mockBaseline]);

    const { container } = render(<ScreenshotTab siteId={100} />);

    // Wait for data to load
    await waitFor(() => {
      expect(screen.getByText('📤 再アップロード')).toBeInTheDocument();
    });

    // Open upload modal
    fireEvent.click(screen.getByText('📤 再アップロード'));

    await waitFor(() => {
      expect(screen.getByText('ベースラインスクリーンショットのアップロード')).toBeInTheDocument();
    });

    // No screenshot type selector (baseline/violation) should exist in the upload modal
    expect(container.querySelector('select[id="screenshot_type"]')).toBeNull();
    expect(container.querySelector('input[name="screenshot_type"]')).toBeNull();
    // The modal should show a notice about baseline overwrite instead
    expect(screen.getByText(/ベースラインスクリーンショットとして保存/)).toBeInTheDocument();
  });

  it('does not display a screenshot type selector in capture modal', async () => {
    vi.mocked(api.getSiteScreenshots).mockResolvedValue([mockMonitoring]);

    const { container } = render(<ScreenshotTab siteId={100} />);

    await waitFor(() => {
      expect(screen.getByText('📸 再キャプチャ')).toBeInTheDocument();
    });

    // Open capture modal
    fireEvent.click(screen.getByText('📸 再キャプチャ'));

    await waitFor(() => {
      expect(screen.getByText('モニタリングキャプチャ')).toBeInTheDocument();
    });

    // No screenshot type selector should exist in the capture modal
    expect(container.querySelector('select[id="screenshot_type"]')).toBeNull();
    expect(container.querySelector('input[name="screenshot_type"]')).toBeNull();
    // The modal should show a notice about monitoring capture
    expect(screen.getByText(/モニタリングキャプチャとして保存/)).toBeInTheDocument();
  });

  // Requirement 2.1, 2.2: Both sections shown with empty states
  it('displays empty states when no screenshots exist', async () => {
    vi.mocked(api.getSiteScreenshots).mockResolvedValue([]);

    render(<ScreenshotTab siteId={100} />);

    await waitFor(() => {
      expect(screen.getByText('ベースラインスクリーンショットがありません')).toBeInTheDocument();
      expect(screen.getByText('モニタリングキャプチャがありません')).toBeInTheDocument();
    });
  });

  it('displays loading state initially', () => {
    vi.mocked(api.getSiteScreenshots).mockImplementation(() => new Promise(() => {}));

    render(<ScreenshotTab siteId={100} />);

    expect(screen.getByText('読み込み中...')).toBeInTheDocument();
  });

  it('displays error message when API call fails', async () => {
    vi.mocked(api.getSiteScreenshots).mockRejectedValue(new Error('Network error'));

    render(<ScreenshotTab siteId={100} />);

    await waitFor(() => {
      expect(screen.getByText(/エラー:/)).toBeInTheDocument();
    });
  });
});
