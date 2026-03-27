/**
 * Unit tests for CrawlResultComparison component.
 *
 * Covers:
 * - 比較表示のテスト (comparison display, selectors, screenshots side-by-side)
 * - 差分計算のテスト (numeric diff calculation, non-numeric change detection)
 * - フィールドハイライトのテスト (changed field highlighting, unchanged fields)
 *
 * Validates: Requirements 17.1, 17.2, 17.3, 17.4, 17.5
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import CrawlResultComparison from './CrawlResultComparison';
import type { CrawlResult } from '../services/api';
import type { ExtractedPaymentInfo } from '../types/extractedData';

// Mock API modules
vi.mock('../services/api', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn() },
  getCrawlResults: vi.fn(),
}));

vi.mock('../api/extractedData', () => ({
  fetchExtractedData: vi.fn(),
}));

import { getCrawlResults } from '../services/api';
import { fetchExtractedData } from '../api/extractedData';

const mockGetCrawlResults = vi.mocked(getCrawlResults);
const mockFetchExtractedData = vi.mocked(fetchExtractedData);

/* ------------------------------------------------------------------ */
/*  Test helpers                                                       */
/* ------------------------------------------------------------------ */

const makeCrawlResult = (id: number, crawledAt: string, extra: Partial<CrawlResult> = {}): CrawlResult => ({
  id,
  site_id: 1,
  url: 'https://example.com',
  status_code: 200,
  screenshot_path: `/screenshots/${id}.png`,
  crawled_at: crawledAt,
  ...extra,
});

const makeExtractedData = (
  id: number,
  crawlResultId: number,
  overrides: Partial<ExtractedPaymentInfo> = {},
): ExtractedPaymentInfo => ({
  id,
  crawl_result_id: crawlResultId,
  site_id: 1,
  source: 'html',
  product_info: { name: '商品A', sku: 'SKU-001' },
  price_info: [{ amount: 1000, currency: 'JPY', price_type: '通常価格' }],
  payment_methods: null,
  fees: null,
  metadata: null,
  confidence_scores: null,
  overall_confidence_score: 0.85,
  status: 'pending',
  language: 'ja',
  extracted_at: '2024-01-01T00:00:00Z',
  ...overrides,
});

/** Render the component with two crawl results loaded and trigger comparison. */
async function renderAndCompare(
  leftData: ExtractedPaymentInfo,
  rightData: ExtractedPaymentInfo,
  crawlResults?: CrawlResult[],
) {
  const results = crawlResults ?? [
    makeCrawlResult(1, '2024-01-01T00:00:00Z'),
    makeCrawlResult(2, '2024-02-01T00:00:00Z'),
  ];
  mockGetCrawlResults.mockResolvedValueOnce(results);
  mockFetchExtractedData
    .mockResolvedValueOnce(leftData)
    .mockResolvedValueOnce(rightData);

  render(<CrawlResultComparison siteId={1} />);

  await waitFor(() => {
    expect(screen.getByText('比較する')).toBeInTheDocument();
  });

  fireEvent.change(screen.getByLabelText('比較元（古い方）'), { target: { value: String(results[0].id) } });
  fireEvent.change(screen.getByLabelText('比較先（新しい方）'), { target: { value: String(results[1].id) } });
  fireEvent.click(screen.getByText('比較する'));

  // Wait for comparison data to load
  await waitFor(() => {
    expect(mockFetchExtractedData).toHaveBeenCalledTimes(2);
  });
}

/* ------------------------------------------------------------------ */
/*  Tests                                                              */
/* ------------------------------------------------------------------ */

describe('CrawlResultComparison', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ================================================================
  // 比較表示のテスト (Comparison display)
  // ================================================================
  describe('比較表示', () => {
    it('shows loading state initially', () => {
      mockGetCrawlResults.mockReturnValue(new Promise(() => {}));
      render(<CrawlResultComparison siteId={1} />);
      expect(screen.getByText('クロール結果を読み込み中...')).toBeInTheDocument();
    });

    it('shows message when fewer than 2 crawl results exist', async () => {
      mockGetCrawlResults.mockResolvedValueOnce([makeCrawlResult(1, '2024-01-01T00:00:00Z')]);
      render(<CrawlResultComparison siteId={1} />);
      await waitFor(() => {
        expect(screen.getByText('比較するには2件以上のクロール結果が必要です。')).toBeInTheDocument();
      });
    });

    it('shows error when crawl results fetch fails', async () => {
      mockGetCrawlResults.mockRejectedValueOnce(new Error('Network error'));
      render(<CrawlResultComparison siteId={1} />);
      await waitFor(() => {
        expect(screen.getByText(/Network error/)).toBeInTheDocument();
      });
    });

    it('renders selectors when crawl results are available', async () => {
      mockGetCrawlResults.mockResolvedValueOnce([
        makeCrawlResult(1, '2024-01-01T00:00:00Z'),
        makeCrawlResult(2, '2024-02-01T00:00:00Z'),
      ]);
      render(<CrawlResultComparison siteId={1} />);
      await waitFor(() => {
        expect(screen.getByText('クロール結果比較')).toBeInTheDocument();
      });
      expect(screen.getByLabelText('比較元（古い方）')).toBeInTheDocument();
      expect(screen.getByLabelText('比較先（新しい方）')).toBeInTheDocument();
      expect(screen.getByText('比較する')).toBeDisabled();
    });

    it('enables compare button when two different results are selected', async () => {
      mockGetCrawlResults.mockResolvedValueOnce([
        makeCrawlResult(1, '2024-01-01T00:00:00Z'),
        makeCrawlResult(2, '2024-02-01T00:00:00Z'),
      ]);
      render(<CrawlResultComparison siteId={1} />);
      await waitFor(() => {
        expect(screen.getByText('比較する')).toBeInTheDocument();
      });

      fireEvent.change(screen.getByLabelText('比較元（古い方）'), { target: { value: '1' } });
      fireEvent.change(screen.getByLabelText('比較先（新しい方）'), { target: { value: '2' } });

      expect(screen.getByText('比較する')).not.toBeDisabled();
    });

    it('keeps compare button disabled when same result is selected for both', async () => {
      mockGetCrawlResults.mockResolvedValueOnce([
        makeCrawlResult(1, '2024-01-01T00:00:00Z'),
        makeCrawlResult(2, '2024-02-01T00:00:00Z'),
      ]);
      render(<CrawlResultComparison siteId={1} />);
      await waitFor(() => {
        expect(screen.getByText('比較する')).toBeInTheDocument();
      });

      fireEvent.change(screen.getByLabelText('比較元（古い方）'), { target: { value: '1' } });
      fireEvent.change(screen.getByLabelText('比較先（新しい方）'), { target: { value: '1' } });

      expect(screen.getByText('比較する')).toBeDisabled();
    });

    it('displays both screenshots side by side after comparison', async () => {
      const leftData = makeExtractedData(10, 1);
      const rightData = makeExtractedData(20, 2);

      await renderAndCompare(leftData, rightData);

      await waitFor(() => {
        expect(screen.getByAltText('比較元スクリーンショット')).toBeInTheDocument();
        expect(screen.getByAltText('比較先スクリーンショット')).toBeInTheDocument();
      });
    });

    it('shows "スクリーンショットなし" when screenshot_path is null', async () => {
      const results = [
        makeCrawlResult(1, '2024-01-01T00:00:00Z', { screenshot_path: null }),
        makeCrawlResult(2, '2024-02-01T00:00:00Z', { screenshot_path: null }),
      ];
      const leftData = makeExtractedData(10, 1);
      const rightData = makeExtractedData(20, 2);

      await renderAndCompare(leftData, rightData, results);

      await waitFor(() => {
        const noScreenshots = screen.getAllByText('スクリーンショットなし');
        expect(noScreenshots).toHaveLength(2);
      });
    });

    it('displays comparison data tables grouped by section', async () => {
      const leftData = makeExtractedData(10, 1, {
        product_info: { name: '商品A', sku: 'SKU-001' },
        price_info: [{ amount: 1000, currency: 'JPY', price_type: '通常価格' }],
        fees: [{ fee_type: '送料', amount: 500, currency: 'JPY' }],
      });
      const rightData = makeExtractedData(20, 2, {
        product_info: { name: '商品A', sku: 'SKU-001' },
        price_info: [{ amount: 1000, currency: 'JPY', price_type: '通常価格' }],
        fees: [{ fee_type: '送料', amount: 500, currency: 'JPY' }],
      });

      await renderAndCompare(leftData, rightData);

      await waitFor(() => {
        expect(screen.getByText('商品情報')).toBeInTheDocument();
        expect(screen.getByText('価格情報')).toBeInTheDocument();
        expect(screen.getByText('手数料')).toBeInTheDocument();
      });
    });

    it('shows error when comparison data fetch fails', async () => {
      mockGetCrawlResults.mockResolvedValueOnce([
        makeCrawlResult(1, '2024-01-01T00:00:00Z'),
        makeCrawlResult(2, '2024-02-01T00:00:00Z'),
      ]);
      // Both fetches reject — Promise.allSettled treats them as { status: 'rejected' }
      // so both left and right become null, triggering the "no data" message.
      mockFetchExtractedData
        .mockRejectedValueOnce(new Error('比較データの取得に失敗'))
        .mockRejectedValueOnce(new Error('比較データの取得に失敗'));

      render(<CrawlResultComparison siteId={1} />);
      await waitFor(() => {
        expect(screen.getByText('比較する')).toBeInTheDocument();
      });

      fireEvent.change(screen.getByLabelText('比較元（古い方）'), { target: { value: '1' } });
      fireEvent.change(screen.getByLabelText('比較先（新しい方）'), { target: { value: '2' } });
      fireEvent.click(screen.getByText('比較する'));

      await waitFor(() => {
        expect(screen.getByText(/抽出データがありません/)).toBeInTheDocument();
      });
    });

    it('allows selecting any two crawl results from history (Req 17.5)', async () => {
      mockGetCrawlResults.mockResolvedValueOnce([
        makeCrawlResult(1, '2024-01-01T00:00:00Z'),
        makeCrawlResult(2, '2024-02-01T00:00:00Z'),
        makeCrawlResult(3, '2024-03-01T00:00:00Z'),
      ]);

      render(<CrawlResultComparison siteId={1} />);
      await waitFor(() => {
        expect(screen.getByText('比較する')).toBeInTheDocument();
      });

      // Both selectors should have all 3 options
      const leftSelect = screen.getByLabelText('比較元（古い方）') as HTMLSelectElement;
      const rightSelect = screen.getByLabelText('比較先（新しい方）') as HTMLSelectElement;

      // Each select has 1 placeholder + 3 crawl result options
      expect(leftSelect.options).toHaveLength(4);
      expect(rightSelect.options).toHaveLength(4);
    });
  });

  // ================================================================
  // 差分計算のテスト (Diff calculation)
  // ================================================================
  describe('差分計算', () => {
    it('calculates positive numeric diff for price increase', async () => {
      const leftData = makeExtractedData(10, 1, {
        price_info: [{ amount: 1000, currency: 'JPY', price_type: '通常価格' }],
      });
      const rightData = makeExtractedData(20, 2, {
        price_info: [{ amount: 1200, currency: 'JPY', price_type: '通常価格' }],
      });

      await renderAndCompare(leftData, rightData);

      await waitFor(() => {
        expect(screen.getByText('+200')).toBeInTheDocument();
      });
    });

    it('calculates negative numeric diff for price decrease', async () => {
      const leftData = makeExtractedData(10, 1, {
        price_info: [{ amount: 1500, currency: 'JPY', price_type: '通常価格' }],
      });
      const rightData = makeExtractedData(20, 2, {
        price_info: [{ amount: 1000, currency: 'JPY', price_type: '通常価格' }],
      });

      await renderAndCompare(leftData, rightData);

      await waitFor(() => {
        expect(screen.getByText('-500')).toBeInTheDocument();
      });
    });

    it('calculates diff for fee amount changes', async () => {
      const leftData = makeExtractedData(10, 1, {
        product_info: null,
        price_info: null,
        fees: [{ fee_type: '送料', amount: 500, currency: 'JPY' }],
      });
      const rightData = makeExtractedData(20, 2, {
        product_info: null,
        price_info: null,
        fees: [{ fee_type: '送料', amount: 800, currency: 'JPY' }],
      });

      await renderAndCompare(leftData, rightData);

      await waitFor(() => {
        expect(screen.getByText('+300')).toBeInTheDocument();
      });
    });

    it('shows "変更あり" for non-numeric field changes', async () => {
      const leftData = makeExtractedData(10, 1, {
        product_info: { name: '商品A', sku: 'SKU-001' },
        price_info: null,
      });
      const rightData = makeExtractedData(20, 2, {
        product_info: { name: '商品B', sku: 'SKU-001' },
        price_info: null,
      });

      await renderAndCompare(leftData, rightData);

      await waitFor(() => {
        expect(screen.getByText('商品A')).toBeInTheDocument();
        expect(screen.getByText('商品B')).toBeInTheDocument();
        expect(screen.getByText('変更あり')).toBeInTheDocument();
      });
    });

    it('shows no diff for unchanged fields', async () => {
      const leftData = makeExtractedData(10, 1, {
        product_info: { name: '商品A' },
        price_info: [{ amount: 1000, currency: 'JPY', price_type: '通常価格' }],
      });
      const rightData = makeExtractedData(20, 2, {
        product_info: { name: '商品A' },
        price_info: [{ amount: 1000, currency: 'JPY', price_type: '通常価格' }],
      });

      await renderAndCompare(leftData, rightData);

      await waitFor(() => {
        expect(screen.getByText('商品情報')).toBeInTheDocument();
      });

      // No diff indicators should appear
      expect(screen.queryByText('変更あり')).not.toBeInTheDocument();
      expect(screen.queryByText(/^\+/)).not.toBeInTheDocument();
      expect(screen.queryByText(/^-\d/)).not.toBeInTheDocument();
    });

    it('calculates diff for overall confidence score changes', async () => {
      const leftData = makeExtractedData(10, 1, {
        product_info: null,
        price_info: null,
        overall_confidence_score: 0.7,
      });
      const rightData = makeExtractedData(20, 2, {
        product_info: null,
        price_info: null,
        overall_confidence_score: 0.9,
      });

      await renderAndCompare(leftData, rightData);

      await waitFor(() => {
        expect(screen.getByText('メタ情報')).toBeInTheDocument();
        // Left: 70.0%, Right: 90.0% — these are different so a diff should appear
        expect(screen.getByText('70.0%')).toBeInTheDocument();
        expect(screen.getByText('90.0%')).toBeInTheDocument();
      });
    });

    it('handles fields present only in right (new fields)', async () => {
      const leftData = makeExtractedData(10, 1, {
        product_info: { name: '商品A' },
        price_info: null,
        payment_methods: null,
      });
      const rightData = makeExtractedData(20, 2, {
        product_info: { name: '商品A' },
        price_info: null,
        payment_methods: [{ method_name: 'クレジットカード', provider: 'Stripe' }],
      });

      await renderAndCompare(leftData, rightData);

      await waitFor(() => {
        // Payment method only in right should show "—" for left value
        expect(screen.getByText('クレジットカード')).toBeInTheDocument();
      });
    });

    it('handles fields present only in left (removed fields)', async () => {
      const leftData = makeExtractedData(10, 1, {
        product_info: { name: '商品A' },
        price_info: null,
        payment_methods: [{ method_name: '銀行振込', provider: null }],
      });
      const rightData = makeExtractedData(20, 2, {
        product_info: { name: '商品A' },
        price_info: null,
        payment_methods: null,
      });

      await renderAndCompare(leftData, rightData);

      await waitFor(() => {
        expect(screen.getByText('銀行振込')).toBeInTheDocument();
      });
    });
  });

  // ================================================================
  // フィールドハイライトのテスト (Field highlighting)
  // ================================================================
  describe('フィールドハイライト', () => {
    it('applies changed CSS class to rows with different values', async () => {
      const leftData = makeExtractedData(10, 1, {
        product_info: { name: '商品A' },
        price_info: [{ amount: 1000, currency: 'JPY', price_type: '通常価格' }],
      });
      const rightData = makeExtractedData(20, 2, {
        product_info: { name: '商品B' },
        price_info: [{ amount: 1200, currency: 'JPY', price_type: '通常価格' }],
      });

      await renderAndCompare(leftData, rightData);

      await waitFor(() => {
        expect(screen.getByText('商品A')).toBeInTheDocument();
      });

      // Find rows with the changed class
      const changedRows = document.querySelectorAll('.comparison__row--changed');
      expect(changedRows.length).toBeGreaterThan(0);
    });

    it('does not apply changed CSS class to rows with identical values', async () => {
      const leftData = makeExtractedData(10, 1, {
        product_info: { name: '商品A', sku: 'SKU-001' },
        price_info: null,
      });
      const rightData = makeExtractedData(20, 2, {
        product_info: { name: '商品A', sku: 'SKU-002' },
        price_info: null,
      });

      await renderAndCompare(leftData, rightData);

      await waitFor(() => {
        // '商品A' appears in both left and right columns, so use getAllByText
        expect(screen.getAllByText('商品A').length).toBeGreaterThanOrEqual(2);
      });

      // The product name row should NOT have the changed class (same value)
      // The SKU row SHOULD have the changed class (different value)
      const rows = document.querySelectorAll('tbody tr');
      let nameRowHasChanged = false;
      let skuRowHasChanged = false;

      rows.forEach((row) => {
        const cells = row.querySelectorAll('td');
        if (cells[0]?.textContent === '商品名') {
          nameRowHasChanged = row.classList.contains('comparison__row--changed');
        }
        if (cells[0]?.textContent === 'SKU') {
          skuRowHasChanged = row.classList.contains('comparison__row--changed');
        }
      });

      expect(nameRowHasChanged).toBe(false);
      expect(skuRowHasChanged).toBe(true);
    });

    it('applies positive diff styling for price increases', async () => {
      const leftData = makeExtractedData(10, 1, {
        product_info: null,
        price_info: [{ amount: 1000, currency: 'JPY', price_type: '通常価格' }],
      });
      const rightData = makeExtractedData(20, 2, {
        product_info: null,
        price_info: [{ amount: 1500, currency: 'JPY', price_type: '通常価格' }],
      });

      await renderAndCompare(leftData, rightData);

      await waitFor(() => {
        const diffEl = screen.getByText('+500');
        expect(diffEl).toBeInTheDocument();
        expect(diffEl.classList.contains('comparison__diff--positive')).toBe(true);
      });
    });

    it('applies negative diff styling for price decreases', async () => {
      const leftData = makeExtractedData(10, 1, {
        product_info: null,
        price_info: [{ amount: 2000, currency: 'JPY', price_type: '通常価格' }],
      });
      const rightData = makeExtractedData(20, 2, {
        product_info: null,
        price_info: [{ amount: 1500, currency: 'JPY', price_type: '通常価格' }],
      });

      await renderAndCompare(leftData, rightData);

      await waitFor(() => {
        const diffEl = screen.getByText('-500');
        expect(diffEl).toBeInTheDocument();
        expect(diffEl.classList.contains('comparison__diff--negative')).toBe(true);
      });
    });

    it('highlights status change between two results', async () => {
      const leftData = makeExtractedData(10, 1, {
        product_info: null,
        price_info: null,
        status: 'pending',
      });
      const rightData = makeExtractedData(20, 2, {
        product_info: null,
        price_info: null,
        status: 'approved',
      });

      await renderAndCompare(leftData, rightData);

      await waitFor(() => {
        expect(screen.getByText('保留中')).toBeInTheDocument();
        expect(screen.getByText('承認済み')).toBeInTheDocument();
      });

      // The status row should be highlighted as changed
      const rows = document.querySelectorAll('tbody tr');
      let statusRowChanged = false;
      rows.forEach((row) => {
        const cells = row.querySelectorAll('td');
        if (cells[0]?.textContent === 'ステータス') {
          statusRowChanged = row.classList.contains('comparison__row--changed');
        }
      });
      expect(statusRowChanged).toBe(true);
    });

    it('shows "変更あり" with positive diff class for non-numeric changes', async () => {
      const leftData = makeExtractedData(10, 1, {
        product_info: { name: '旧商品名' },
        price_info: null,
      });
      const rightData = makeExtractedData(20, 2, {
        product_info: { name: '新商品名' },
        price_info: null,
      });

      await renderAndCompare(leftData, rightData);

      await waitFor(() => {
        const changeIndicator = screen.getByText('変更あり');
        expect(changeIndicator).toBeInTheDocument();
        expect(changeIndicator.classList.contains('comparison__diff--positive')).toBe(true);
      });
    });
  });
});
