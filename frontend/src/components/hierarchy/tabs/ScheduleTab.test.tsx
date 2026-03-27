import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import ScheduleTab from './ScheduleTab';
import * as schedulesApi from '../../../api/schedules';
import * as api from '../../../services/api';
import type { CrawlScheduleData } from '../../../api/schedules';

vi.mock('../../../api/schedules', () => ({
  getSchedule: vi.fn(),
  createSchedule: vi.fn(),
  updateSchedule: vi.fn(),
  updateSiteSettings: vi.fn(),
}));

vi.mock('../../../services/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn() },
  triggerCrawl: vi.fn(),
}));

const mockSchedule: CrawlScheduleData = {
  site_id: 100,
  priority: 'normal',
  interval_minutes: 1440,
  next_crawl_at: '2024-06-15T12:00:00Z',
  last_etag: '"abc123"',
  last_modified: 'Wed, 15 Jun 2024 12:00:00 GMT',
};

describe('ScheduleTab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // Requirement 24.1-24.2: Schedule form rendering
  it('renders schedule form with priority, interval, and next crawl time', async () => {
    vi.mocked(schedulesApi.getSchedule).mockResolvedValue(mockSchedule);

    render(<ScheduleTab siteId={100} />);

    await waitFor(() => {
      expect(screen.getByText('スケジュール情報')).toBeInTheDocument();
    });

    expect(screen.getByLabelText('優先度')).toBeInTheDocument();
    expect(screen.getByLabelText('クロール間隔（分）')).toBeInTheDocument();
    expect(screen.getByTestId('next-crawl-time')).toBeInTheDocument();
  });

  // Requirement 24.6: Delta crawl info read-only display
  it('renders delta crawl info as read-only', async () => {
    vi.mocked(schedulesApi.getSchedule).mockResolvedValue(mockSchedule);

    render(<ScheduleTab siteId={100} />);

    await waitFor(() => {
      expect(screen.getByText('デルタクロール情報')).toBeInTheDocument();
    });

    expect(screen.getByTestId('etag-value')).toHaveTextContent('"abc123"');
    expect(screen.getByTestId('last-modified-value')).toHaveTextContent('Wed, 15 Jun 2024 12:00:00 GMT');
  });

  // Requirement 24.5: "Run Now" button
  it('renders "Run Now" button and triggers crawl on click', async () => {
    vi.mocked(schedulesApi.getSchedule).mockResolvedValue(mockSchedule);
    vi.mocked(api.triggerCrawl).mockResolvedValue({ job_id: '123', status: 'queued' });

    render(<ScheduleTab siteId={100} />);

    await waitFor(() => {
      expect(screen.getByText('今すぐ実行')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('今すぐ実行'));

    await waitFor(() => {
      expect(api.triggerCrawl).toHaveBeenCalledWith(100);
    });
  });

  // Requirement 24.8: Default values when no schedule exists
  it('shows create form with defaults when no schedule exists', async () => {
    vi.mocked(schedulesApi.getSchedule).mockRejectedValue(new Error('Not found'));

    render(<ScheduleTab siteId={100} />);

    await waitFor(() => {
      expect(screen.getByText('スケジュール情報')).toBeInTheDocument();
    });

    const prioritySelect = screen.getByLabelText('優先度') as HTMLSelectElement;
    expect(prioritySelect.value).toBe('normal');

    const intervalInput = screen.getByLabelText('クロール間隔（分）') as HTMLInputElement;
    expect(intervalInput.value).toBe('1440');
  });

  // Requirement 24a.1: Plugin settings section collapsed by default
  it('renders plugin settings section collapsed by default', async () => {
    vi.mocked(schedulesApi.getSchedule).mockResolvedValue(mockSchedule);

    render(<ScheduleTab siteId={100} />);

    await waitFor(() => {
      expect(screen.getByText('プラグイン設定（上級）')).toBeInTheDocument();
    });

    expect(screen.queryByTestId('plugin-settings')).not.toBeInTheDocument();
  });

  // Requirement 24a.2: Expand plugin settings
  it('expands plugin settings on click and shows all plugins with toggles', async () => {
    vi.mocked(schedulesApi.getSchedule).mockResolvedValue(mockSchedule);

    render(<ScheduleTab siteId={100} />);

    await waitFor(() => {
      expect(screen.getByText('プラグイン設定（上級）')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('プラグイン設定（上級）'));

    await waitFor(() => {
      expect(screen.getByTestId('plugin-settings')).toBeInTheDocument();
    });

    // All 12 plugins should be listed
    expect(screen.getByText('LocalePlugin')).toBeInTheDocument();
    expect(screen.getByText('AlertPlugin')).toBeInTheDocument();
    expect(screen.getByText('OCRPlugin')).toBeInTheDocument();

    // Toggle switches should exist
    const switches = screen.getAllByRole('switch');
    expect(switches.length).toBe(12);
  });

  // Requirement 24a.6: Global default notice
  it('shows "follows global settings" when plugin_config is null', async () => {
    vi.mocked(schedulesApi.getSchedule).mockResolvedValue(mockSchedule);

    render(<ScheduleTab siteId={100} />);

    await waitFor(() => {
      expect(screen.getByText('プラグイン設定（上級）')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('プラグイン設定（上級）'));

    await waitFor(() => {
      expect(screen.getByText('グローバル設定に従う')).toBeInTheDocument();
    });
  });

  // Requirement 24a.7: "Reset to default" button
  it('shows "Reset to default" button in plugin settings', async () => {
    vi.mocked(schedulesApi.getSchedule).mockResolvedValue(mockSchedule);

    render(<ScheduleTab siteId={100} />);

    await waitFor(() => {
      fireEvent.click(screen.getByText('プラグイン設定（上級）'));
    });

    await waitFor(() => {
      expect(screen.getByText('デフォルトに戻す')).toBeInTheDocument();
    });
  });

  // Requirement 25.5: PreCaptureScript textarea placeholder
  it('renders PreCaptureScript textarea with placeholder', async () => {
    vi.mocked(schedulesApi.getSchedule).mockResolvedValue(mockSchedule);

    render(<ScheduleTab siteId={100} />);

    await waitFor(() => {
      expect(screen.getByText('プレキャプチャスクリプト')).toBeInTheDocument();
    });

    const textarea = screen.getByTestId('pre-capture-script') as HTMLTextAreaElement;
    expect(textarea.placeholder).toContain('action');
    expect(textarea.placeholder).toContain('click');
    expect(textarea.placeholder).toContain('.lang-ja');
  });

  // Requirement 25.4: JSON validation error
  it('shows validation error for invalid JSON in PreCaptureScript', async () => {
    vi.mocked(schedulesApi.getSchedule).mockResolvedValue(mockSchedule);

    render(<ScheduleTab siteId={100} />);

    await waitFor(() => {
      expect(screen.getByTestId('pre-capture-script')).toBeInTheDocument();
    });

    const textarea = screen.getByTestId('pre-capture-script');
    fireEvent.change(textarea, { target: { value: '{invalid json' } });

    // Click save to trigger validation
    fireEvent.click(screen.getByText('保存'));

    await waitFor(() => {
      expect(screen.getByTestId('script-error')).toHaveTextContent('JSON形式が不正です');
    });
  });

  // Requirement 25.3: Empty value → null
  it('sends null when PreCaptureScript is empty on save', async () => {
    vi.mocked(schedulesApi.getSchedule).mockResolvedValue(mockSchedule);
    vi.mocked(schedulesApi.updateSchedule).mockResolvedValue(mockSchedule);
    vi.mocked(schedulesApi.updateSiteSettings).mockResolvedValue(undefined);

    render(<ScheduleTab siteId={100} />);

    await waitFor(() => {
      expect(screen.getByText('保存')).toBeInTheDocument();
    });

    // Leave textarea empty and save
    fireEvent.click(screen.getByText('保存'));

    await waitFor(() => {
      expect(schedulesApi.updateSiteSettings).toHaveBeenCalledWith(100, expect.objectContaining({
        pre_capture_script: null,
      }));
    });
  });

  it('displays loading state initially', () => {
    vi.mocked(schedulesApi.getSchedule).mockImplementation(() => new Promise(() => {}));

    render(<ScheduleTab siteId={100} />);

    expect(screen.getByText('読み込み中...')).toBeInTheDocument();
  });
});
