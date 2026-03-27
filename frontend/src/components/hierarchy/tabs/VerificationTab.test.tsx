import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import VerificationTab from './VerificationTab';
import * as api from '../../../services/api';
import type { VerificationResult } from '../../../services/api';

// Mock the API module
vi.mock('../../../services/api', () => ({
  triggerVerification: vi.fn(),
  getVerificationResults: vi.fn(),
  getVerificationStatus: vi.fn(),
}));

const mockResult: VerificationResult = {
  id: 1,
  site_id: 100,
  site_name: 'テストサイト',
  html_data: { price: '1000円', payment_method: 'クレジットカード' },
  ocr_data: { price: '1000円', payment_method: 'クレジットカード決済' },
  discrepancies: [
    {
      field_name: 'payment_method',
      html_value: 'クレジットカード',
      ocr_value: 'クレジットカード決済',
      difference_type: 'value_mismatch',
      severity: 'high',
    },
    {
      field_name: 'fee',
      html_value: '100円',
      ocr_value: '200円',
      difference_type: 'value_mismatch',
      severity: 'medium',
    },
  ],
  html_violations: [],
  ocr_violations: [],
  screenshot_path: '/screenshots/test.png',
  ocr_confidence: 0.95,
  status: 'completed',
  error_message: null,
  created_at: '2024-06-01T10:00:00Z',
};

const mockResultNoDiscrepancies: VerificationResult = {
  ...mockResult,
  id: 2,
  discrepancies: [],
  created_at: '2024-05-15T08:00:00Z',
};

describe('VerificationTab', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // Requirement 3.1: サイトセレクターが非表示であること
  it('does not display a site selector (siteId is received via props)', async () => {
    vi.mocked(api.getVerificationResults).mockResolvedValue({
      results: [mockResult],
      total: 1,
      limit: 10,
      offset: 0,
    });

    const { container } = render(<VerificationTab siteId={100} />);

    await waitFor(() => {
      expect(screen.getByText('検証実行')).toBeInTheDocument();
    });

    // No site selector should exist
    expect(container.querySelector('select')).toBeNull();
    expect(screen.queryByText('サイト選択')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('サイト')).not.toBeInTheDocument();
  });

  // Requirement 3.2: 検証実行ボタンの存在
  it('displays the "検証実行" button', async () => {
    vi.mocked(api.getVerificationResults).mockResolvedValue({
      results: [mockResult],
      total: 1,
      limit: 10,
      offset: 0,
    });

    render(<VerificationTab siteId={100} />);

    await waitFor(() => {
      expect(screen.getByText('検証実行')).toBeInTheDocument();
    });
  });

  // Requirement 3.3: 比較テーブル表示（HTML値、OCR値、ステータス）
  it('displays the comparison table with HTML values, OCR values, and status', async () => {
    vi.mocked(api.getVerificationResults).mockResolvedValue({
      results: [mockResult],
      total: 1,
      limit: 10,
      offset: 0,
    });

    render(<VerificationTab siteId={100} />);

    await waitFor(() => {
      // Table element with aria-label
      expect(screen.getByRole('table', { name: '検証比較テーブル' })).toBeInTheDocument();
    });

    // Column headers in <th> elements
    const table = screen.getByRole('table', { name: '検証比較テーブル' });
    const headers = table.querySelectorAll('th');
    const headerTexts = Array.from(headers).map(h => h.textContent);
    expect(headerTexts).toContain('フィールド名');
    expect(headerTexts).toContain('HTML値');
    expect(headerTexts).toContain('OCR値');
    expect(headerTexts).toContain('ステータス');

    // Field data rows in the table
    const rows = table.querySelectorAll('tbody tr');
    expect(rows.length).toBe(2); // price and payment_method
  });

  // Requirement 3.4: 差異リスト・重要度バッジ表示
  it('displays discrepancies with severity badges', async () => {
    vi.mocked(api.getVerificationResults).mockResolvedValue({
      results: [mockResult],
      total: 1,
      limit: 10,
      offset: 0,
    });

    const { container } = render(<VerificationTab siteId={100} />);

    await waitFor(() => {
      expect(screen.getByText('検出された差異')).toBeInTheDocument();
    });

    // Discrepancy field names within the discrepancy section
    const fieldNames = container.querySelectorAll('.verification-tab-field-name');
    const fieldTexts = Array.from(fieldNames).map(el => el.textContent);
    expect(fieldTexts).toContain('payment_method');
    expect(fieldTexts).toContain('fee');

    // Severity badges (Badge component renders with role="status")
    const badges = screen.getAllByRole('status');
    const severityBadges = badges.filter(
      b => b.textContent === 'high' || b.textContent === 'medium'
    );
    expect(severityBadges.length).toBeGreaterThanOrEqual(2);
  });

  // Requirement 3.5: 履歴一覧の表示
  it('displays historical verification results', async () => {
    vi.mocked(api.getVerificationResults).mockResolvedValue({
      results: [mockResult, mockResultNoDiscrepancies],
      total: 2,
      limit: 10,
      offset: 0,
    });

    render(<VerificationTab siteId={100} />);

    await waitFor(() => {
      expect(screen.getByText('過去の検証結果')).toBeInTheDocument();
    });
  });

  // Requirement 3.6: CSVエクスポートボタンの存在
  it('displays the CSV export button when a result is available', async () => {
    vi.mocked(api.getVerificationResults).mockResolvedValue({
      results: [mockResult],
      total: 1,
      limit: 10,
      offset: 0,
    });

    render(<VerificationTab siteId={100} />);

    await waitFor(() => {
      expect(screen.getByText('CSV出力')).toBeInTheDocument();
    });
  });

  // Empty state: no results
  it('displays empty state when no verification results exist', async () => {
    vi.mocked(api.getVerificationResults).mockResolvedValue({
      results: [],
      total: 0,
      limit: 10,
      offset: 0,
    });

    render(<VerificationTab siteId={100} />);

    await waitFor(() => {
      expect(screen.getByText(/検証結果がありません/)).toBeInTheDocument();
    });
  });

  it('displays loading state initially', () => {
    vi.mocked(api.getVerificationResults).mockImplementation(() => new Promise(() => {}));

    render(<VerificationTab siteId={100} />);

    expect(screen.getByText('読み込み中...')).toBeInTheDocument();
  });
});
