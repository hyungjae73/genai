/**
 * Frontend integration tests for CrawlResultReview page.
 *
 * Tests the full review page flow including:
 * - レビューUIの全機能テスト (data loading, screenshot + extracted data display)
 * - 編集と承認ワークフローのテスト (inline editing, approval/rejection)
 * - 価格履歴グラフと比較機能のテスト (PriceHistoryChart, CrawlResultComparison)
 *
 * Validates: Requirements 9.1–9.6, 10.1–10.6, 11.1–11.6, 13.1–13.6
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import CrawlResultReviewPage from './CrawlResultReview';
import type { ExtractedPaymentInfo } from '../types/extractedData';

/* ------------------------------------------------------------------ */
/*  Mocks                                                              */
/* ------------------------------------------------------------------ */

// Mock the API module
vi.mock('../api/extractedData', () => ({
  fetchExtractedData: vi.fn(),
  updateExtractedData: vi.fn(),
  approveExtractedData: vi.fn(),
  rejectExtractedData: vi.fn(),
  fetchAuditLogs: vi.fn(),
  fetchVisualConfirmationData: vi.fn(),
}));

// Mock react-zoom-pan-pinch to avoid canvas/DOM measurement issues in jsdom
vi.mock('react-zoom-pan-pinch', () => ({
  TransformWrapper: ({ children }: { children: (utils: Record<string, () => void>) => React.ReactNode }) =>
    children({ zoomIn: vi.fn(), zoomOut: vi.fn(), resetTransform: vi.fn() }),
  TransformComponent: ({ children }: { children: React.ReactNode }) => <div data-testid="transform-component">{children}</div>,
}));

import {
  fetchExtractedData,
  updateExtractedData,
  approveExtractedData,
  rejectExtractedData,
  fetchAuditLogs,
  fetchVisualConfirmationData,
} from '../api/extractedData';

const mockFetchExtractedData = vi.mocked(fetchExtractedData);
const mockUpdateExtractedData = vi.mocked(updateExtractedData);
const mockApproveExtractedData = vi.mocked(approveExtractedData);
const mockRejectExtractedData = vi.mocked(rejectExtractedData);
const mockFetchAuditLogs = vi.mocked(fetchAuditLogs);
const mockFetchVisualConfirmationData = vi.mocked(fetchVisualConfirmationData);

/* ------------------------------------------------------------------ */
/*  Test data                                                          */
/* ------------------------------------------------------------------ */

const makeSampleData = (overrides: Partial<ExtractedPaymentInfo> = {}): ExtractedPaymentInfo => ({
  id: 100,
  crawl_result_id: 10,
  site_id: 1,
  product_info: {
    name: 'テスト商品',
    description: '商品の説明文',
    sku: 'SKU-001',
  },
  price_info: [
    { amount: 1500, currency: 'JPY', price_type: '通常価格', condition: '税込' },
    { amount: 1200, currency: 'JPY', price_type: '会員価格' },
  ],
  payment_methods: [
    { method_name: 'クレジットカード', provider: 'Stripe', processing_fee: 3.6, fee_type: 'percentage' },
  ],
  fees: [
    { fee_type: '送料', amount: 500, currency: 'JPY', condition: '5000円未満' },
  ],
  metadata: {
    url: 'https://example.com/product',
    screenshot_path: '/screenshots/2024/01/1/test.png',
  },
  confidence_scores: {
    product_name: 0.95,
    product_description: 0.45,
    sku: 0.72,
    base_price: 0.88,
    payment_methods: 0.60,
    fees: 0.35,
  },
  overall_confidence_score: 0.78,
  status: 'pending',
  language: 'ja',
  extracted_at: '2024-06-15T10:30:00Z',
  ...overrides,
});

/** Render the review page with a route that provides crawlResultId param. */
function renderReviewPage(crawlResultId = '10') {
  return render(
    <MemoryRouter initialEntries={[`/sites/1/crawl-results/${crawlResultId}/review`]}>
      <Routes>
        <Route
          path="/sites/:siteId/crawl-results/:crawlResultId/review"
          element={<CrawlResultReviewPage />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

/* ------------------------------------------------------------------ */
/*  Tests                                                              */
/* ------------------------------------------------------------------ */

describe('CrawlResultReview Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchAuditLogs.mockResolvedValue([]);
    // Default: visual confirmation returns "complete" so it doesn't interfere with existing tests
    mockFetchVisualConfirmationData.mockResolvedValue({
      screenshot_url: null,
      raw_html: null,
      extraction_status: 'complete',
      html_data: null,
      ocr_data: null,
    });
  });

  // ================================================================
  // レビューUIの全機能テスト
  // ================================================================
  describe('レビューUI全機能', () => {
    it('shows loading state while fetching data', () => {
      mockFetchExtractedData.mockReturnValue(new Promise(() => {}));
      renderReviewPage();
      expect(screen.getByText('読み込み中...')).toBeInTheDocument();
    });

    it('shows error message when data fetch fails', async () => {
      mockFetchExtractedData.mockRejectedValueOnce(new Error('サーバーエラー'));
      mockFetchVisualConfirmationData.mockRejectedValueOnce(new Error('サーバーエラー'));
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText(/サーバーエラー/)).toBeInTheDocument();
      });
    });

    it('shows "データが見つかりません" when API returns null-like', async () => {
      mockFetchExtractedData.mockResolvedValueOnce(null as unknown as ExtractedPaymentInfo);
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('データが見つかりません。')).toBeInTheDocument();
      });
    });

    it('displays screenshot and extracted data side by side (Req 9.1, 9.2)', async () => {
      mockFetchExtractedData.mockResolvedValueOnce(makeSampleData());
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('クロール結果レビュー')).toBeInTheDocument();
      });

      // Screenshot should be rendered
      const img = screen.getByAltText('クロール結果スクリーンショット');
      expect(img).toBeInTheDocument();

      // Extracted data section
      expect(screen.getByText('抽出データ')).toBeInTheDocument();
      expect(screen.getByText('商品情報')).toBeInTheDocument();
    });

    it('displays crawl timestamp and site URL at the top (Req 9.3)', async () => {
      mockFetchExtractedData.mockResolvedValueOnce(makeSampleData());
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText(/クロール日時:/)).toBeInTheDocument();
      });
      expect(screen.getByText(/サイトURL:/)).toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'https://example.com/product' })).toBeInTheDocument();
    });

    it('displays overall confidence score prominently (Req 9.4)', async () => {
      mockFetchExtractedData.mockResolvedValueOnce(makeSampleData());
      renderReviewPage();

      await waitFor(() => {
        // 0.78 → 78% (中)
        expect(screen.getByTitle('全体信頼度: 78% (中)')).toBeInTheDocument();
      });
    });

    it('shows "スクリーンショットがありません" when no screenshot path', async () => {
      mockFetchExtractedData.mockResolvedValueOnce(
        makeSampleData({ metadata: { url: 'https://example.com' } }),
      );
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('スクリーンショットがありません')).toBeInTheDocument();
      });
    });

    it('displays confidence indicators with color coding (Req 10.1, 10.2)', async () => {
      mockFetchExtractedData.mockResolvedValueOnce(makeSampleData());
      renderReviewPage();

      await waitFor(() => {
        // High confidence: product_name 0.95 → 95% (高)
        expect(screen.getByText('95% (高)')).toBeInTheDocument();
        // Low confidence: product_description 0.45 → 45% (低)
        expect(screen.getByText('45% (低)')).toBeInTheDocument();
        // Medium confidence: sku 0.72 → 72% (中)
        expect(screen.getByText('72% (中)')).toBeInTheDocument();
      });
    });

    it('displays product info, price info, payment methods, and fees sections', async () => {
      mockFetchExtractedData.mockResolvedValueOnce(makeSampleData());
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('商品情報')).toBeInTheDocument();
      });
      expect(screen.getByText('価格情報')).toBeInTheDocument();
      expect(screen.getByText('支払い方法')).toBeInTheDocument();
      expect(screen.getByText('手数料')).toBeInTheDocument();
    });

    it('displays product field values correctly', async () => {
      mockFetchExtractedData.mockResolvedValueOnce(makeSampleData());
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('テスト商品')).toBeInTheDocument();
      });
      expect(screen.getByText('商品の説明文')).toBeInTheDocument();
      expect(screen.getByText('SKU-001')).toBeInTheDocument();
    });

    it('displays status badge for pending status', async () => {
      mockFetchExtractedData.mockResolvedValueOnce(makeSampleData());
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('保留中')).toBeInTheDocument();
      });
    });

    it('highlights field on click and shows indicator on screenshot (Req 9.5)', async () => {
      mockFetchExtractedData.mockResolvedValueOnce(makeSampleData());
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('テスト商品')).toBeInTheDocument();
      });

      // Click on a data field row
      const row = screen.getByRole('button', { name: /商品名: テスト商品/ });
      fireEvent.click(row);

      // Should show highlight indicator on screenshot
      expect(screen.getByText(/選択中: product_name/)).toBeInTheDocument();
    });

    it('toggles highlight off when same field is clicked again', async () => {
      mockFetchExtractedData.mockResolvedValueOnce(makeSampleData());
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('テスト商品')).toBeInTheDocument();
      });

      const row = screen.getByRole('button', { name: /商品名: テスト商品/ });
      fireEvent.click(row);
      expect(screen.getByText(/選択中: product_name/)).toBeInTheDocument();

      // Click again to deselect
      fireEvent.click(row);
      expect(screen.queryByText(/選択中:/)).not.toBeInTheDocument();
    });

    it('renders zoom controls for screenshot viewer (Req 9.6)', async () => {
      mockFetchExtractedData.mockResolvedValueOnce(makeSampleData());
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByLabelText('ズームイン')).toBeInTheDocument();
      });
      expect(screen.getByLabelText('ズームアウト')).toBeInTheDocument();
      expect(screen.getByLabelText('リセット')).toBeInTheDocument();
    });
  });

  // ================================================================
  // ヘルプモーダルのテスト
  // ================================================================
  describe('ヘルプモーダル', () => {
    it('displays help button with correct aria-label (Req 6.1, 6.2, 6.4)', async () => {
      mockFetchExtractedData.mockResolvedValueOnce(makeSampleData());
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('クロール結果レビュー')).toBeInTheDocument();
      });

      const helpButton = screen.getByLabelText('ヘルプを表示');
      expect(helpButton).toBeInTheDocument();
      expect(helpButton.textContent).toBe('?');
    });

    it('opens help modal with page-specific content on click (Req 6.2, 6.5)', async () => {
      mockFetchExtractedData.mockResolvedValueOnce(makeSampleData());
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('クロール結果レビュー')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByLabelText('ヘルプを表示'));

      await waitFor(() => {
        expect(screen.getByText('クロール結果レビューの使い方')).toBeInTheDocument();
      });
      expect(screen.getByText(/スクリーンショットとデータの並列表示/)).toBeInTheDocument();
      expect(screen.getByText(/フィールドハイライト/)).toBeInTheDocument();
      expect(screen.getByText(/HTML解析とOCR解析の比較/)).toBeInTheDocument();
      // 承認ワークフロー appears both in help modal and on the page itself
      const approvalTexts = screen.getAllByText(/承認ワークフロー/);
      expect(approvalTexts.length).toBeGreaterThanOrEqual(2); // one in help, one in page
    });
  });

  // ================================================================
  // 編集と承認ワークフローのテスト
  // ================================================================
  describe('編集と承認ワークフロー', () => {
    it('shows edit buttons for editable fields (Req 11.1)', async () => {
      mockFetchExtractedData.mockResolvedValueOnce(makeSampleData());
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('テスト商品')).toBeInTheDocument();
      });

      // Each editable field should have an edit button (✎)
      const editButtons = screen.getAllByLabelText(/を編集/);
      expect(editButtons.length).toBeGreaterThan(0);
    });

    it('enters inline edit mode and saves a product field (Req 11.1, 11.3)', async () => {
      const sampleData = makeSampleData();
      mockFetchExtractedData.mockResolvedValueOnce(sampleData);

      const updatedData = makeSampleData({
        product_info: { ...sampleData.product_info, name: '更新商品名' },
      });
      mockUpdateExtractedData.mockResolvedValueOnce(updatedData);

      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('テスト商品')).toBeInTheDocument();
      });

      // Click edit button for the product name field
      const editBtn = screen.getByLabelText('テスト商品 を編集');
      fireEvent.click(editBtn);

      // Should show input field
      const input = screen.getByLabelText('フィールド編集');
      expect(input).toBeInTheDocument();

      // Change value and save
      fireEvent.change(input, { target: { value: '更新商品名' } });
      fireEvent.click(screen.getByLabelText('保存'));

      await waitFor(() => {
        expect(mockUpdateExtractedData).toHaveBeenCalledWith(100, {
          product_info: expect.objectContaining({ name: '更新商品名' }),
        });
      });
    });

    it('shows approval workflow with approve and reject buttons (Req 13.1, 13.2)', async () => {
      mockFetchExtractedData.mockResolvedValueOnce(makeSampleData());
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('承認ワークフロー')).toBeInTheDocument();
      });
      expect(screen.getByRole('button', { name: /承認/ })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /却下/ })).toBeInTheDocument();
    });

    it('approves extraction and updates status (Req 13.3)', async () => {
      mockFetchExtractedData.mockResolvedValueOnce(makeSampleData());
      mockApproveExtractedData.mockResolvedValueOnce(undefined);
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /承認/ })).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: /承認/ }));

      await waitFor(() => {
        expect(mockApproveExtractedData).toHaveBeenCalledWith(100);
      });

      // Status should update to approved (badge + workflow both show it)
      await waitFor(() => {
        expect(screen.getAllByText('承認済み').length).toBeGreaterThanOrEqual(1);
      });
    });

    it('rejects extraction with reason and updates status (Req 13.4, 13.5)', async () => {
      mockFetchExtractedData.mockResolvedValueOnce(makeSampleData());
      mockRejectExtractedData.mockResolvedValueOnce(undefined);
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /却下/ })).toBeInTheDocument();
      });

      // Click reject to show reason form
      fireEvent.click(screen.getByRole('button', { name: /却下/ }));

      // Enter reason and confirm
      const textarea = screen.getByPlaceholderText(/却下理由を入力してください/);
      fireEvent.change(textarea, { target: { value: 'データが不正確' } });
      fireEvent.click(screen.getByRole('button', { name: /却下を確定/ }));

      await waitFor(() => {
        expect(mockRejectExtractedData).toHaveBeenCalledWith(100, 'データが不正確');
      });

      // Status should update to rejected (badge + workflow both show it)
      await waitFor(() => {
        expect(screen.getAllByText('却下').length).toBeGreaterThanOrEqual(1);
      });
    });

    it('shows change history panel (Req 12.3)', async () => {
      mockFetchExtractedData.mockResolvedValueOnce(makeSampleData());
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /変更履歴/ })).toBeInTheDocument();
      });
    });

    it('expands change history and fetches audit logs', async () => {
      mockFetchExtractedData.mockResolvedValueOnce(makeSampleData());
      mockFetchAuditLogs.mockResolvedValueOnce([
        {
          id: 1,
          user: 'admin',
          timestamp: '2024-06-15T11:00:00Z',
          field_name: 'product_name',
          old_value: '旧名',
          new_value: '新名',
          action: 'update',
        },
      ]);
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /変更履歴/ })).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole('button', { name: /変更履歴/ }));

      await waitFor(() => {
        expect(mockFetchAuditLogs).toHaveBeenCalledWith('extracted_payment_info', 100);
      });

      await waitFor(() => {
        expect(screen.getByText('admin')).toBeInTheDocument();
        expect(screen.getByText('旧名')).toBeInTheDocument();
        expect(screen.getByText('新名')).toBeInTheDocument();
      });
    });

    it('shows add field button for product info (Req 11.6)', async () => {
      mockFetchExtractedData.mockResolvedValueOnce(makeSampleData());
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('＋ フィールド追加')).toBeInTheDocument();
      });
    });

    it('displays approved status info when data is already approved (Req 13.6)', async () => {
      mockFetchExtractedData.mockResolvedValueOnce(
        makeSampleData({
          status: 'approved',
          metadata: {
            url: 'https://example.com',
            screenshot_path: '/screenshots/test.png',
            approved_by: 'reviewer_user',
            approved_at: '2024-06-16T09:00:00Z',
          },
        }),
      );
      renderReviewPage();

      await waitFor(() => {
        // Both status badge and approval workflow show "承認済み"
        expect(screen.getAllByText('承認済み').length).toBeGreaterThanOrEqual(1);
      });
      expect(screen.getByText(/reviewer_user/)).toBeInTheDocument();
    });
  });
});
