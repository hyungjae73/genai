/**
 * PriceHistoryChart - 価格履歴グラフコンポーネント
 *
 * Recharts LineChart を使用して価格の時系列変化を折れ線グラフで表示する。
 * - X軸: クロールタイムスタンプ (recorded_at)
 * - Y軸: 価格金額 (price)
 * - 日付範囲選択機能
 * - 複数商品の比較表示
 * - ツールチップで正確な価格とタイムスタンプを表示
 * - 重要な価格変動 (>20%) を赤いドットでマーカー表示
 *
 * Validates: Requirements 15.1, 15.2, 15.3, 15.4, 15.5, 15.6
 */

import React, { useEffect, useState, useCallback, useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceDot,
} from 'recharts';
import { fetchPriceHistory } from '../api/extractedData';
import type { PriceHistory } from '../types/extractedData';

export interface PriceHistoryChartProps {
  siteId: number;
  productIdentifiers: string[];
}

/** Colors for each product line */
const LINE_COLORS = [
  '#8884d8',
  '#82ca9d',
  '#ffc658',
  '#ff7300',
  '#0088fe',
  '#00c49f',
  '#ff8042',
  '#a4de6c',
];

/** Threshold for significant price change (20%) */
const SIGNIFICANT_CHANGE_THRESHOLD = 20;

interface MergedDataPoint {
  timestamp: string;
  [key: string]: string | number | null;
}

interface SignificantChange {
  timestamp: string;
  productId: string;
  price: number;
  changePercent: number;
}

const formatDate = (dateStr: string): string => {
  const d = new Date(dateStr);
  return `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')}`;
};

const formatDateTime = (dateStr: string): string => {
  const d = new Date(dateStr);
  return `${formatDate(dateStr)} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
};

/** Custom tooltip showing exact price and timestamp */
const PriceTooltip: React.FC<{
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
}> = ({ active, payload, label }) => {
  if (!active || !payload || !label) return null;
  return (
    <div
      style={{
        background: '#fff',
        border: '1px solid #ccc',
        borderRadius: 4,
        padding: '8px 12px',
        fontSize: 13,
      }}
    >
      <p style={{ margin: 0, fontWeight: 600 }}>{formatDateTime(label)}</p>
      {payload.map((entry) => (
        <p key={entry.name} style={{ margin: '4px 0 0', color: entry.color }}>
          {entry.name}: ¥{entry.value?.toLocaleString() ?? '—'}
        </p>
      ))}
    </div>
  );
};

const PriceHistoryChart: React.FC<PriceHistoryChartProps> = ({
  siteId,
  productIdentifiers,
}) => {
  const [historyMap, setHistoryMap] = useState<Record<string, PriceHistory[]>>(
    {},
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Date range state – default to empty (fetch all)
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  const loadData = useCallback(async () => {
    if (productIdentifiers.length === 0) return;
    setLoading(true);
    setError(null);
    try {
      const results: Record<string, PriceHistory[]> = {};
      await Promise.all(
        productIdentifiers.map(async (pid) => {
          const res = await fetchPriceHistory(
            siteId,
            pid,
            startDate || undefined,
            endDate || undefined,
          );
          results[pid] = res.items;
        }),
      );
      setHistoryMap(results);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'データ取得に失敗しました');
    } finally {
      setLoading(false);
    }
  }, [siteId, productIdentifiers, startDate, endDate]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Merge all product histories into a single timeline for the chart
  const { mergedData, significantChanges } = useMemo(() => {
    const timestampSet = new Set<string>();
    const changes: SignificantChange[] = [];

    for (const [pid, items] of Object.entries(historyMap)) {
      for (const item of items) {
        timestampSet.add(item.recorded_at);
        if (
          item.price_change_percentage !== null &&
          Math.abs(item.price_change_percentage) >= SIGNIFICANT_CHANGE_THRESHOLD
        ) {
          changes.push({
            timestamp: item.recorded_at,
            productId: pid,
            price: item.price,
            changePercent: item.price_change_percentage,
          });
        }
      }
    }

    const sortedTimestamps = Array.from(timestampSet).sort();
    const merged: MergedDataPoint[] = sortedTimestamps.map((ts) => {
      const point: MergedDataPoint = { timestamp: ts };
      for (const [pid, items] of Object.entries(historyMap)) {
        const match = items.find((i) => i.recorded_at === ts);
        point[pid] = match ? match.price : null;
      }
      return point;
    });

    return { mergedData: merged, significantChanges: changes };
  }, [historyMap]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    loadData();
  };

  if (productIdentifiers.length === 0) {
    return <p style={{ color: '#888' }}>商品を選択してください</p>;
  }

  return (
    <div style={{ width: '100%' }}>
      <h3 style={{ marginBottom: 8 }}>価格履歴グラフ</h3>

      {/* Date range picker */}
      <form
        onSubmit={handleSearch}
        style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 16 }}
      >
        <label>
          開始日:
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            style={{ marginLeft: 4 }}
          />
        </label>
        <label>
          終了日:
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            style={{ marginLeft: 4 }}
          />
        </label>
        <button type="submit">表示</button>
      </form>

      {loading && <p>読み込み中...</p>}
      {error && <p style={{ color: 'red' }}>{error}</p>}

      {!loading && !error && mergedData.length === 0 && (
        <p style={{ color: '#888' }}>データがありません</p>
      )}

      {!loading && mergedData.length > 0 && (
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={mergedData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="timestamp"
              tickFormatter={formatDate}
              tick={{ fontSize: 12 }}
            />
            <YAxis
              tickFormatter={(v: number) => `¥${v.toLocaleString()}`}
              tick={{ fontSize: 12 }}
            />
            <Tooltip content={<PriceTooltip />} />
            <Legend />

            {productIdentifiers.map((pid, idx) => (
              <Line
                key={pid}
                type="monotone"
                dataKey={pid}
                name={pid}
                stroke={LINE_COLORS[idx % LINE_COLORS.length]}
                strokeWidth={2}
                dot={{ r: 3 }}
                connectNulls
              />
            ))}

            {/* Significant price change markers (red dots) */}
            {significantChanges.map((sc, idx) => (
              <ReferenceDot
                key={`sig-${idx}`}
                x={sc.timestamp}
                y={sc.price}
                r={6}
                fill="red"
                stroke="darkred"
                strokeWidth={2}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
};

export default PriceHistoryChart;
