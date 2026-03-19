/**
 * Unit tests for PriceHistoryChart component.
 *
 * Covers:
 * - グラフレンダリングのテスト (chart rendering, axes, legend, markers)
 * - 日付範囲フィルタリングのテスト (date range selection and API calls)
 * - 複数商品比較のテスト (multi-product comparison on same chart)
 *
 * Validates: Requirements 15.1, 15.2, 15.3, 15.4, 15.5, 15.6
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import PriceHistoryChart from './PriceHistoryChart';
import type { PriceHistoryList } from '../types/extractedData';

// Mock the API module
vi.mock('../api/extractedData', () => ({
  fetchPriceHistory: vi.fn(),
}));

// Mock Recharts – use importOriginal to keep all real exports, only override ResponsiveContainer
vi.mock('recharts', async (importOriginal) => {
  const actual = await importOriginal<typeof import('recharts')>();
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div data-testid="responsive-container" style={{ width: 800, height: 400 }}>
        {children}
      </div>
    ),
  };
});

import { fetchPriceHistory } from '../api/extractedData';
const mockFetch = vi.mocked(fetchPriceHistory);

/** Helper to build a PriceHistoryList response */
const buildHistory = (
  items: Array<{
    productId: string;
    price: number;
    recordedAt: string;
    changePercent?: number | null;
    previousPrice?: number | null;
  }>,
): PriceHistoryList => ({
  items: items.map((item, idx) => ({
    id: idx + 1,
    site_id: 1,
    product_identifier: item.productId,
    price: item.price,
    currency: 'JPY',
    price_type: 'base_price',
    previous_price: item.previousPrice ?? null,
    price_change_amount: null,
    price_change_percentage: item.changePercent ?? null,
    recorded_at: item.recordedAt,
  })),
  total: items.length,
});

describe('PriceHistoryChart', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ================================================================
  // グラフレンダリングのテスト
  // ================================================================
  describe('グラフレンダリング', () => {
    it('shows empty message when no product identifiers provided', () => {
      render(<PriceHistoryChart siteId={1} productIdentifiers={[]} />);
      expect(screen.getByText('商品を選択してください')).toBeInTheDocument();
    });

    it('does not call API when no product identifiers provided', () => {
      render(<PriceHistoryChart siteId={1} productIdentifiers={[]} />);
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('shows loading state while fetching data', () => {
      mockFetch.mockReturnValue(new Promise(() => {}));

      render(
        <PriceHistoryChart siteId={1} productIdentifiers={['product-a']} />,
      );

      expect(screen.getByText('読み込み中...')).toBeInTheDocument();
    });

    it('renders chart heading and container after data loads', async () => {
      mockFetch.mockResolvedValueOnce(
        buildHistory([
          { productId: 'product-a', price: 1000, recordedAt: '2024-01-01T00:00:00Z' },
        ]),
      );

      render(
        <PriceHistoryChart siteId={1} productIdentifiers={['product-a']} />,
      );

      await waitFor(() => {
        expect(screen.queryByText('読み込み中...')).not.toBeInTheDocument();
      });

      expect(screen.getByText('価格履歴グラフ')).toBeInTheDocument();
      expect(screen.getByTestId('responsive-container')).toBeInTheDocument();
    });

    it('renders chart with multiple data points for a single product', async () => {
      mockFetch.mockResolvedValueOnce(
        buildHistory([
          { productId: 'product-a', price: 1000, recordedAt: '2024-01-01T00:00:00Z' },
          { productId: 'product-a', price: 1100, recordedAt: '2024-02-01T00:00:00Z' },
          { productId: 'product-a', price: 900, recordedAt: '2024-03-01T00:00:00Z' },
        ]),
      );

      render(
        <PriceHistoryChart siteId={1} productIdentifiers={['product-a']} />,
      );

      await waitFor(() => {
        expect(screen.getByTestId('responsive-container')).toBeInTheDocument();
      });

      expect(screen.queryByText('データがありません')).not.toBeInTheDocument();
    });

    it('shows no-data message when API returns empty items', async () => {
      mockFetch.mockResolvedValueOnce({ items: [], total: 0 });

      render(
        <PriceHistoryChart siteId={1} productIdentifiers={['product-a']} />,
      );

      await waitFor(() => {
        expect(screen.getByText('データがありません')).toBeInTheDocument();
      });
    });

    it('shows error message when API fails', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      render(
        <PriceHistoryChart siteId={1} productIdentifiers={['product-a']} />,
      );

      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });
    });

    it('shows generic error message for non-Error exceptions', async () => {
      mockFetch.mockRejectedValueOnce('unknown failure');

      render(
        <PriceHistoryChart siteId={1} productIdentifiers={['product-a']} />,
      );

      await waitFor(() => {
        expect(screen.getByText('データ取得に失敗しました')).toBeInTheDocument();
      });
    });

    it('renders date range form with start and end inputs', async () => {
      mockFetch.mockResolvedValueOnce({ items: [], total: 0 });

      render(
        <PriceHistoryChart siteId={1} productIdentifiers={['product-a']} />,
      );

      await waitFor(() => {
        expect(screen.queryByText('読み込み中...')).not.toBeInTheDocument();
      });

      expect(screen.getByLabelText('開始日:')).toBeInTheDocument();
      expect(screen.getByLabelText('終了日:')).toBeInTheDocument();
      expect(screen.getByText('表示')).toBeInTheDocument();
    });
  });

  // ================================================================
  // 日付範囲フィルタリングのテスト
  // ================================================================
  describe('日付範囲フィルタリング', () => {
    it('calls API without date params on initial load', async () => {
      mockFetch.mockResolvedValueOnce({ items: [], total: 0 });

      render(
        <PriceHistoryChart siteId={1} productIdentifiers={['product-a']} />,
      );

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(1, 'product-a', undefined, undefined);
      });
    });

    it('passes date range to API when dates are set and form submitted', async () => {
      mockFetch.mockResolvedValue({ items: [], total: 0 });

      render(
        <PriceHistoryChart siteId={1} productIdentifiers={['product-a']} />,
      );

      await waitFor(() => {
        expect(screen.queryByText('読み込み中...')).not.toBeInTheDocument();
      });

      fireEvent.change(screen.getByLabelText('開始日:'), {
        target: { value: '2024-01-01' },
      });
      fireEvent.change(screen.getByLabelText('終了日:'), {
        target: { value: '2024-06-30' },
      });

      fireEvent.click(screen.getByText('表示'));

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          1,
          'product-a',
          '2024-01-01',
          '2024-06-30',
        );
      });
    });

    it('passes only start date when end date is empty', async () => {
      mockFetch.mockResolvedValue({ items: [], total: 0 });

      render(
        <PriceHistoryChart siteId={1} productIdentifiers={['product-a']} />,
      );

      await waitFor(() => {
        expect(screen.queryByText('読み込み中...')).not.toBeInTheDocument();
      });

      fireEvent.change(screen.getByLabelText('開始日:'), {
        target: { value: '2024-03-01' },
      });

      fireEvent.click(screen.getByText('表示'));

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          1,
          'product-a',
          '2024-03-01',
          undefined,
        );
      });
    });

    it('passes only end date when start date is empty', async () => {
      mockFetch.mockResolvedValue({ items: [], total: 0 });

      render(
        <PriceHistoryChart siteId={1} productIdentifiers={['product-a']} />,
      );

      await waitFor(() => {
        expect(screen.queryByText('読み込み中...')).not.toBeInTheDocument();
      });

      fireEvent.change(screen.getByLabelText('終了日:'), {
        target: { value: '2024-12-31' },
      });

      fireEvent.click(screen.getByText('表示'));

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          1,
          'product-a',
          undefined,
          '2024-12-31',
        );
      });
    });

    it('re-fetches data with updated date range on form resubmit', async () => {
      mockFetch.mockResolvedValue({ items: [], total: 0 });

      render(
        <PriceHistoryChart siteId={1} productIdentifiers={['product-a']} />,
      );

      await waitFor(() => {
        expect(screen.queryByText('読み込み中...')).not.toBeInTheDocument();
      });

      // First submission
      fireEvent.change(screen.getByLabelText('開始日:'), {
        target: { value: '2024-01-01' },
      });
      fireEvent.click(screen.getByText('表示'));

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(1, 'product-a', '2024-01-01', undefined);
      });

      // Second submission with different range
      fireEvent.change(screen.getByLabelText('開始日:'), {
        target: { value: '2024-06-01' },
      });
      fireEvent.change(screen.getByLabelText('終了日:'), {
        target: { value: '2024-12-31' },
      });
      fireEvent.click(screen.getByText('表示'));

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          1,
          'product-a',
          '2024-06-01',
          '2024-12-31',
        );
      });
    });
  });

  // ================================================================
  // 複数商品比較のテスト
  // ================================================================
  describe('複数商品比較', () => {
    it('fetches data for each product identifier', async () => {
      mockFetch
        .mockResolvedValueOnce(
          buildHistory([
            { productId: 'product-a', price: 1000, recordedAt: '2024-01-01T00:00:00Z' },
          ]),
        )
        .mockResolvedValueOnce(
          buildHistory([
            { productId: 'product-b', price: 2000, recordedAt: '2024-01-01T00:00:00Z' },
          ]),
        );

      render(
        <PriceHistoryChart
          siteId={1}
          productIdentifiers={['product-a', 'product-b']}
        />,
      );

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledTimes(2);
      });

      expect(mockFetch).toHaveBeenCalledWith(1, 'product-a', undefined, undefined);
      expect(mockFetch).toHaveBeenCalledWith(1, 'product-b', undefined, undefined);
    });

    it('fetches data for three products simultaneously', async () => {
      mockFetch
        .mockResolvedValueOnce(
          buildHistory([
            { productId: 'p1', price: 100, recordedAt: '2024-01-01T00:00:00Z' },
          ]),
        )
        .mockResolvedValueOnce(
          buildHistory([
            { productId: 'p2', price: 200, recordedAt: '2024-01-01T00:00:00Z' },
          ]),
        )
        .mockResolvedValueOnce(
          buildHistory([
            { productId: 'p3', price: 300, recordedAt: '2024-01-01T00:00:00Z' },
          ]),
        );

      render(
        <PriceHistoryChart
          siteId={1}
          productIdentifiers={['p1', 'p2', 'p3']}
        />,
      );

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledTimes(3);
      });

      expect(mockFetch).toHaveBeenCalledWith(1, 'p1', undefined, undefined);
      expect(mockFetch).toHaveBeenCalledWith(1, 'p2', undefined, undefined);
      expect(mockFetch).toHaveBeenCalledWith(1, 'p3', undefined, undefined);
    });

    it('renders chart when multiple products have overlapping timestamps', async () => {
      mockFetch
        .mockResolvedValueOnce(
          buildHistory([
            { productId: 'product-a', price: 1000, recordedAt: '2024-01-01T00:00:00Z' },
            { productId: 'product-a', price: 1100, recordedAt: '2024-02-01T00:00:00Z' },
          ]),
        )
        .mockResolvedValueOnce(
          buildHistory([
            { productId: 'product-b', price: 2000, recordedAt: '2024-01-01T00:00:00Z' },
            { productId: 'product-b', price: 1800, recordedAt: '2024-02-01T00:00:00Z' },
          ]),
        );

      render(
        <PriceHistoryChart
          siteId={1}
          productIdentifiers={['product-a', 'product-b']}
        />,
      );

      await waitFor(() => {
        expect(screen.getByTestId('responsive-container')).toBeInTheDocument();
      });

      expect(screen.queryByText('データがありません')).not.toBeInTheDocument();
    });

    it('renders chart when products have non-overlapping timestamps', async () => {
      mockFetch
        .mockResolvedValueOnce(
          buildHistory([
            { productId: 'product-a', price: 1000, recordedAt: '2024-01-01T00:00:00Z' },
          ]),
        )
        .mockResolvedValueOnce(
          buildHistory([
            { productId: 'product-b', price: 2000, recordedAt: '2024-03-01T00:00:00Z' },
          ]),
        );

      render(
        <PriceHistoryChart
          siteId={1}
          productIdentifiers={['product-a', 'product-b']}
        />,
      );

      await waitFor(() => {
        expect(screen.getByTestId('responsive-container')).toBeInTheDocument();
      });
    });

    it('applies date range filter to all products in comparison', async () => {
      mockFetch.mockResolvedValue({ items: [], total: 0 });

      render(
        <PriceHistoryChart
          siteId={1}
          productIdentifiers={['product-a', 'product-b']}
        />,
      );

      // Wait for initial load
      await waitFor(() => {
        expect(screen.queryByText('読み込み中...')).not.toBeInTheDocument();
      });

      // Set date range and submit
      fireEvent.change(screen.getByLabelText('開始日:'), {
        target: { value: '2024-01-01' },
      });
      fireEvent.change(screen.getByLabelText('終了日:'), {
        target: { value: '2024-06-30' },
      });
      fireEvent.click(screen.getByText('表示'));

      // Both products should eventually be fetched with the date range
      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(1, 'product-a', '2024-01-01', '2024-06-30');
        expect(mockFetch).toHaveBeenCalledWith(1, 'product-b', '2024-01-01', '2024-06-30');
      });
    });

    it('handles partial API failure gracefully (one product fails)', async () => {
      mockFetch
        .mockResolvedValueOnce(
          buildHistory([
            { productId: 'product-a', price: 1000, recordedAt: '2024-01-01T00:00:00Z' },
          ]),
        )
        .mockRejectedValueOnce(new Error('Failed to fetch product-b'));

      render(
        <PriceHistoryChart
          siteId={1}
          productIdentifiers={['product-a', 'product-b']}
        />,
      );

      await waitFor(() => {
        expect(screen.getByText('Failed to fetch product-b')).toBeInTheDocument();
      });
    });
  });
});
