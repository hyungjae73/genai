/**
 * Unit tests for ChangeHistoryPanel component.
 *
 * Tests cover:
 * - Collapsed/expanded toggle behavior
 * - Loading state display
 * - Empty history message
 * - Audit log entries display (user, timestamp, field, old/new values)
 * - Field filter functionality
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ChangeHistoryPanel from './ChangeHistoryPanel';
import type { AuditLogEntry } from '../types/extractedData';

/* ---- Mock the API module ---- */
vi.mock('../api/extractedData', () => ({
  fetchAuditLogs: vi.fn(),
}));

import { fetchAuditLogs } from '../api/extractedData';

const mockFetchAuditLogs = vi.mocked(fetchAuditLogs);

const sampleLogs: AuditLogEntry[] = [
  {
    id: 1,
    user: 'admin',
    timestamp: '2024-06-01T10:00:00Z',
    field_name: 'product_name',
    old_value: '旧商品名',
    new_value: '新商品名',
    action: 'update',
  },
  {
    id: 2,
    user: 'reviewer1',
    timestamp: '2024-06-02T14:30:00Z',
    field_name: 'base_price',
    old_value: '1000',
    new_value: '1200',
    action: 'update',
  },
  {
    id: 3,
    user: 'admin',
    timestamp: '2024-06-03T09:15:00Z',
    field_name: 'product_name',
    old_value: '新商品名',
    new_value: '最新商品名',
    action: 'update',
  },
];

describe('ChangeHistoryPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchAuditLogs.mockResolvedValue(sampleLogs);
  });

  /* ---------------------------------------------------------------- */
  /*  Collapsed state (default)                                        */
  /* ---------------------------------------------------------------- */
  it('renders collapsed by default with header button', () => {
    render(<ChangeHistoryPanel entityId={1} />);
    const toggle = screen.getByRole('button', { name: /変更履歴/ });
    expect(toggle).toBeInTheDocument();
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
  });

  it('does not fetch audit logs when collapsed', () => {
    render(<ChangeHistoryPanel entityId={1} />);
    expect(mockFetchAuditLogs).not.toHaveBeenCalled();
  });

  /* ---------------------------------------------------------------- */
  /*  Expanding and loading                                            */
  /* ---------------------------------------------------------------- */
  it('fetches audit logs when expanded', async () => {
    render(<ChangeHistoryPanel entityId={42} entityType="extracted_payment_info" />);
    fireEvent.click(screen.getByRole('button', { name: /変更履歴/ }));

    await waitFor(() => {
      expect(mockFetchAuditLogs).toHaveBeenCalledWith('extracted_payment_info', 42);
    });
  });

  it('shows loading text while fetching', async () => {
    // Make the fetch hang so we can observe loading state
    mockFetchAuditLogs.mockReturnValue(new Promise(() => {}));
    render(<ChangeHistoryPanel entityId={1} />);
    fireEvent.click(screen.getByRole('button', { name: /変更履歴/ }));

    expect(screen.getByText('読み込み中...')).toBeInTheDocument();
  });

  /* ---------------------------------------------------------------- */
  /*  Empty history                                                    */
  /* ---------------------------------------------------------------- */
  it('shows empty message when no logs exist', async () => {
    mockFetchAuditLogs.mockResolvedValue([]);
    render(<ChangeHistoryPanel entityId={1} />);
    fireEvent.click(screen.getByRole('button', { name: /変更履歴/ }));

    await waitFor(() => {
      expect(screen.getByText('変更履歴はありません')).toBeInTheDocument();
    });
  });

  /* ---------------------------------------------------------------- */
  /*  Displaying log entries                                           */
  /* ---------------------------------------------------------------- */
  it('displays user identifiers for each log entry', async () => {
    render(<ChangeHistoryPanel entityId={1} />);
    fireEvent.click(screen.getByRole('button', { name: /変更履歴/ }));

    await waitFor(() => {
      // admin appears in 2 rows (log 1 and log 3)
      expect(screen.getAllByText('admin')).toHaveLength(2);
      expect(screen.getByText('reviewer1')).toBeInTheDocument();
    });
  });

  it('displays field names for each log entry', async () => {
    render(<ChangeHistoryPanel entityId={1} />);
    fireEvent.click(screen.getByRole('button', { name: /変更履歴/ }));

    await waitFor(() => {
      // product_name appears in 2 table rows + 1 filter button = 3
      expect(screen.getAllByText('product_name')).toHaveLength(3);
      // base_price appears in 1 table row + 1 filter button = 2
      expect(screen.getAllByText('base_price')).toHaveLength(2);
    });
  });

  it('displays old and new values', async () => {
    render(<ChangeHistoryPanel entityId={1} />);
    fireEvent.click(screen.getByRole('button', { name: /変更履歴/ }));

    await waitFor(() => {
      expect(screen.getByText('旧商品名')).toBeInTheDocument();
      // 新商品名 appears as new_value in row 1 and old_value in row 3
      expect(screen.getAllByText('新商品名')).toHaveLength(2);
      expect(screen.getByText('1000')).toBeInTheDocument();
      expect(screen.getByText('1200')).toBeInTheDocument();
    });
  });

  it('displays dash for null old/new values', async () => {
    mockFetchAuditLogs.mockResolvedValue([
      {
        id: 10,
        user: 'user1',
        timestamp: '2024-06-01T10:00:00Z',
        field_name: 'sku',
        old_value: null,
        new_value: 'SKU-001',
        action: 'create',
      },
    ]);
    render(<ChangeHistoryPanel entityId={1} />);
    fireEvent.click(screen.getByRole('button', { name: /変更履歴/ }));

    await waitFor(() => {
      expect(screen.getByText('—')).toBeInTheDocument();
      expect(screen.getByText('SKU-001')).toBeInTheDocument();
    });
  });

  it('renders a table with correct headers', async () => {
    render(<ChangeHistoryPanel entityId={1} />);
    fireEvent.click(screen.getByRole('button', { name: /変更履歴/ }));

    await waitFor(() => {
      expect(screen.getByText('日時')).toBeInTheDocument();
      expect(screen.getByText('ユーザー')).toBeInTheDocument();
      expect(screen.getByText('フィールド')).toBeInTheDocument();
      expect(screen.getByText('旧値')).toBeInTheDocument();
      expect(screen.getByText('新値')).toBeInTheDocument();
    });
  });

  /* ---------------------------------------------------------------- */
  /*  Field filter                                                     */
  /* ---------------------------------------------------------------- */
  it('shows field filter buttons when multiple fields exist', async () => {
    render(<ChangeHistoryPanel entityId={1} />);
    fireEvent.click(screen.getByRole('button', { name: /変更履歴/ }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'すべて' })).toBeInTheDocument();
      // field filter buttons for product_name and base_price
      const filterButtons = screen.getAllByRole('button');
      const fieldButtons = filterButtons.filter(
        (b) => b.textContent === 'product_name' || b.textContent === 'base_price',
      );
      expect(fieldButtons.length).toBeGreaterThanOrEqual(2);
    });
  });

  it('filters logs by selected field', async () => {
    render(<ChangeHistoryPanel entityId={1} />);
    fireEvent.click(screen.getByRole('button', { name: /変更履歴/ }));

    await waitFor(() => {
      expect(screen.getByText('1000')).toBeInTheDocument();
    });

    // Click the base_price filter button
    const filterButtons = screen.getAllByRole('button').filter(
      (b) => b.textContent === 'base_price',
    );
    fireEvent.click(filterButtons[0]);

    // Should show base_price entry but not product_name entries
    expect(screen.getByText('1000')).toBeInTheDocument();
    expect(screen.getByText('1200')).toBeInTheDocument();
    expect(screen.queryByText('旧商品名')).not.toBeInTheDocument();
  });

  it('shows all logs when "すべて" filter is clicked', async () => {
    render(<ChangeHistoryPanel entityId={1} />);
    fireEvent.click(screen.getByRole('button', { name: /変更履歴/ }));

    await waitFor(() => {
      expect(screen.getByText('1000')).toBeInTheDocument();
    });

    // Filter to base_price first
    const basePriceBtn = screen.getAllByRole('button').filter(
      (b) => b.textContent === 'base_price',
    );
    fireEvent.click(basePriceBtn[0]);
    expect(screen.queryByText('旧商品名')).not.toBeInTheDocument();

    // Click "すべて" to reset
    fireEvent.click(screen.getByRole('button', { name: 'すべて' }));
    expect(screen.getByText('旧商品名')).toBeInTheDocument();
    expect(screen.getByText('1000')).toBeInTheDocument();
  });

  /* ---------------------------------------------------------------- */
  /*  Collapse toggle                                                  */
  /* ---------------------------------------------------------------- */
  it('collapses content when header is clicked again', async () => {
    render(<ChangeHistoryPanel entityId={1} />);
    const toggle = screen.getByRole('button', { name: /変更履歴/ });

    // Expand
    fireEvent.click(toggle);
    await waitFor(() => {
      expect(screen.getAllByText('admin').length).toBeGreaterThanOrEqual(1);
    });

    // Collapse
    fireEvent.click(toggle);
    expect(screen.queryByText('admin')).not.toBeInTheDocument();
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
  });

  /* ---------------------------------------------------------------- */
  /*  fieldFilter prop                                                 */
  /* ---------------------------------------------------------------- */
  it('applies initial fieldFilter prop', async () => {
    render(<ChangeHistoryPanel entityId={1} fieldFilter="base_price" />);
    fireEvent.click(screen.getByRole('button', { name: /変更履歴/ }));

    await waitFor(() => {
      expect(screen.getByText('1000')).toBeInTheDocument();
    });

    // product_name entries should be filtered out
    expect(screen.queryByText('旧商品名')).not.toBeInTheDocument();
  });
});
