/**
 * Tests for VisualConfirmationPanel component.
 *
 * Covers:
 * - Screenshot display with zoom controls
 * - Raw HTML display with search/highlight
 * - Manual input form with validation
 * - Save flow and error handling
 * - Extraction status labels
 *
 * Validates: Requirements 29.2, 29.3, 29.4, 29.5, 29.7
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import VisualConfirmationPanel from './VisualConfirmationPanel';

/* ---- Mocks ---- */

vi.mock('react-zoom-pan-pinch', () => ({
  TransformWrapper: ({ children }: { children: (u: Record<string, () => void>) => React.ReactNode }) =>
    children({ zoomIn: vi.fn(), zoomOut: vi.fn(), resetTransform: vi.fn() }),
  TransformComponent: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="transform-component">{children}</div>
  ),
}));

vi.mock('../api/extractedData', () => ({
  saveManualExtraction: vi.fn(),
}));

import { saveManualExtraction } from '../api/extractedData';

const mockSave = vi.mocked(saveManualExtraction);

const defaultProps = {
  crawlResultId: 10,
  screenshotUrl: '/screenshots/test.png',
  rawHtml: '<html><body><h1>Test</h1></body></html>',
  extractionStatus: 'no_data' as const,
};

describe('VisualConfirmationPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSave.mockResolvedValue({} as never);
  });

  /* ---------------------------------------------------------------- */
  /*  Header & status labels                                           */
  /* ---------------------------------------------------------------- */
  it('displays warning header with no_data status label', () => {
    render(<VisualConfirmationPanel {...defaultProps} extractionStatus="no_data" />);
    expect(screen.getByText(/目視確認モード/)).toBeInTheDocument();
    expect(screen.getByText(/抽出データなし/)).toBeInTheDocument();
  });

  it('displays partial status label', () => {
    render(<VisualConfirmationPanel {...defaultProps} extractionStatus="partial" />);
    expect(screen.getByText(/部分抽出/)).toBeInTheDocument();
  });

  it('displays complete status label', () => {
    render(<VisualConfirmationPanel {...defaultProps} extractionStatus="complete" />);
    expect(screen.getByText(/抽出完了/)).toBeInTheDocument();
  });

  /* ---------------------------------------------------------------- */
  /*  Screenshot tab (Req 29.2, 29.4)                                  */
  /* ---------------------------------------------------------------- */
  it('shows screenshot tab by default with zoom controls', () => {
    render(<VisualConfirmationPanel {...defaultProps} />);
    expect(screen.getByRole('tab', { name: 'スクリーンショット' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByAltText('ページスクリーンショット')).toBeInTheDocument();
    expect(screen.getByLabelText('ズームイン')).toBeInTheDocument();
    expect(screen.getByLabelText('ズームアウト')).toBeInTheDocument();
    expect(screen.getByLabelText('リセット')).toBeInTheDocument();
  });

  it('shows empty message when no screenshot URL', () => {
    render(<VisualConfirmationPanel {...defaultProps} screenshotUrl={null} />);
    expect(screen.getByText('スクリーンショットがありません')).toBeInTheDocument();
  });

  /* ---------------------------------------------------------------- */
  /*  Raw HTML tab (Req 29.3, 29.5)                                    */
  /* ---------------------------------------------------------------- */
  it('switches to HTML tab and displays raw HTML content', () => {
    render(<VisualConfirmationPanel {...defaultProps} />);
    fireEvent.click(screen.getByRole('tab', { name: '生HTML' }));

    expect(screen.getByRole('tab', { name: '生HTML' })).toHaveAttribute('aria-selected', 'true');
    // The raw HTML is escaped and rendered inside a <pre> — check the pre element exists
    const pre = document.querySelector('.visual-confirmation__html-content');
    expect(pre).not.toBeNull();
    // The innerHTML should contain escaped angle brackets
    expect(pre?.innerHTML).toContain('&lt;html&gt;');
  });

  it('shows empty message when no raw HTML', () => {
    render(<VisualConfirmationPanel {...defaultProps} rawHtml={null} />);
    fireEvent.click(screen.getByRole('tab', { name: '生HTML' }));
    expect(screen.getByText('HTMLデータがありません')).toBeInTheDocument();
  });

  it('highlights search matches in HTML view', () => {
    render(<VisualConfirmationPanel {...defaultProps} rawHtml="<div>price is 1000 yen</div>" />);
    fireEvent.click(screen.getByRole('tab', { name: '生HTML' }));

    const searchInput = screen.getByPlaceholderText('HTMLを検索...');
    fireEvent.change(searchInput, { target: { value: '1000' } });

    // The <mark> tag should wrap the match
    const pre = document.querySelector('.visual-confirmation__html-content');
    expect(pre?.innerHTML).toContain('<mark>1000</mark>');
  });

  /* ---------------------------------------------------------------- */
  /*  Manual input form (Req 29.7)                                     */
  /* ---------------------------------------------------------------- */
  it('renders manual input form with all fields', () => {
    render(<VisualConfirmationPanel {...defaultProps} />);
    expect(screen.getByLabelText(/商品名/)).toBeInTheDocument();
    expect(screen.getByLabelText(/価格/)).toBeInTheDocument();
    expect(screen.getByLabelText(/通貨/)).toBeInTheDocument();
    expect(screen.getByLabelText(/支払方法/)).toBeInTheDocument();
    expect(screen.getByLabelText(/追加手数料/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '保存' })).toBeInTheDocument();
  });

  it('defaults currency to JPY', () => {
    render(<VisualConfirmationPanel {...defaultProps} />);
    expect(screen.getByLabelText(/通貨/)).toHaveValue('JPY');
  });

  /* ---------------------------------------------------------------- */
  /*  Validation                                                       */
  /* ---------------------------------------------------------------- */
  it('shows validation error when product_name is empty on save', async () => {
    render(<VisualConfirmationPanel {...defaultProps} />);
    fireEvent.click(screen.getByRole('button', { name: '保存' }));

    await waitFor(() => {
      expect(screen.getByText('商品名は必須です')).toBeInTheDocument();
    });
    expect(mockSave).not.toHaveBeenCalled();
  });

  it('shows validation error for invalid price', async () => {
    render(<VisualConfirmationPanel {...defaultProps} />);
    fireEvent.change(screen.getByLabelText(/商品名/), { target: { value: 'テスト商品' } });
    fireEvent.change(screen.getByLabelText(/価格/), { target: { value: 'abc' } });
    fireEvent.click(screen.getByRole('button', { name: '保存' }));

    await waitFor(() => {
      expect(screen.getByText(/価格は0以上の数値/)).toBeInTheDocument();
    });
    expect(mockSave).not.toHaveBeenCalled();
  });

  it('shows validation error for negative price', async () => {
    render(<VisualConfirmationPanel {...defaultProps} />);
    fireEvent.change(screen.getByLabelText(/商品名/), { target: { value: 'テスト商品' } });
    fireEvent.change(screen.getByLabelText(/価格/), { target: { value: '-100' } });
    fireEvent.click(screen.getByRole('button', { name: '保存' }));

    await waitFor(() => {
      expect(screen.getByText(/価格は0以上の数値/)).toBeInTheDocument();
    });
    expect(mockSave).not.toHaveBeenCalled();
  });

  it('clears validation error when field is corrected', async () => {
    render(<VisualConfirmationPanel {...defaultProps} />);
    fireEvent.click(screen.getByRole('button', { name: '保存' }));

    await waitFor(() => {
      expect(screen.getByText('商品名は必須です')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/商品名/), { target: { value: 'テスト' } });
    expect(screen.queryByText('商品名は必須です')).not.toBeInTheDocument();
  });

  /* ---------------------------------------------------------------- */
  /*  Save flow                                                        */
  /* ---------------------------------------------------------------- */
  it('calls saveManualExtraction with form data on valid save', async () => {
    const onSaved = vi.fn();
    render(<VisualConfirmationPanel {...defaultProps} onSaved={onSaved} />);

    fireEvent.change(screen.getByLabelText(/商品名/), { target: { value: 'テスト商品' } });
    fireEvent.change(screen.getByLabelText(/価格/), { target: { value: '1500' } });
    fireEvent.change(screen.getByLabelText(/支払方法/), { target: { value: 'クレジットカード, 銀行振込' } });
    fireEvent.click(screen.getByRole('button', { name: '保存' }));

    await waitFor(() => {
      expect(mockSave).toHaveBeenCalledWith(10, {
        product_name: 'テスト商品',
        price: '1500',
        currency: 'JPY',
        payment_methods: ['クレジットカード', '銀行振込'],
        additional_fees: '',
      });
    });
    expect(onSaved).toHaveBeenCalled();
    expect(screen.getByText('保存しました')).toBeInTheDocument();
  });

  it('disables form fields after successful save', async () => {
    render(<VisualConfirmationPanel {...defaultProps} />);
    fireEvent.change(screen.getByLabelText(/商品名/), { target: { value: 'テスト' } });
    fireEvent.click(screen.getByRole('button', { name: '保存' }));

    await waitFor(() => {
      expect(screen.getByText('保存しました')).toBeInTheDocument();
    });

    expect(screen.getByLabelText(/商品名/)).toBeDisabled();
    expect(screen.getByLabelText(/価格/)).toBeDisabled();
    expect(screen.getByRole('button', { name: '保存' })).toBeDisabled();
  });

  it('shows error message when save fails', async () => {
    mockSave.mockRejectedValue(new Error('ネットワークエラー'));
    render(<VisualConfirmationPanel {...defaultProps} />);

    fireEvent.change(screen.getByLabelText(/商品名/), { target: { value: 'テスト' } });
    fireEvent.click(screen.getByRole('button', { name: '保存' }));

    await waitFor(() => {
      expect(screen.getByText('ネットワークエラー')).toBeInTheDocument();
    });
    // Form should still be editable after error
    expect(screen.getByLabelText(/商品名/)).not.toBeDisabled();
  });

  it('allows saving with empty price (optional field)', async () => {
    render(<VisualConfirmationPanel {...defaultProps} />);
    fireEvent.change(screen.getByLabelText(/商品名/), { target: { value: 'テスト' } });
    fireEvent.click(screen.getByRole('button', { name: '保存' }));

    await waitFor(() => {
      expect(mockSave).toHaveBeenCalled();
    });
  });
});
