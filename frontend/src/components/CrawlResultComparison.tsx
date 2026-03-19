import { useEffect, useState, useCallback, useMemo } from 'react';
import { getCrawlResults } from '../services/api';
import type { CrawlResult } from '../services/api';
import { fetchExtractedData } from '../api/extractedData';
import type { ExtractedPaymentInfo, PriceInfo, PaymentMethod, Fee } from '../types/extractedData';
import './CrawlResultComparison.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080';

interface CrawlResultComparisonProps {
  siteId: number;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

/** Format a crawl result for the dropdown label. */
function formatCrawlLabel(cr: CrawlResult): string {
  const date = new Date(cr.crawled_at).toLocaleString('ja-JP');
  return `${date}  (ID: ${cr.id}, ${cr.status_code})`;
}

/** Build a screenshot URL from a CrawlResult or ExtractedPaymentInfo. */
function buildScreenshotUrl(
  screenshotPath: string | null | undefined,
  metadataPath?: string | null,
): string | null {
  const path = screenshotPath ?? metadataPath;
  if (!path) return null;
  return `${API_BASE_URL}/${path.replace(/^\//, '')}`;
}

/** Flatten extracted data into a list of comparable field rows. */
interface FieldRow {
  section: string;
  label: string;
  key: string;
  value: string;
  numericValue?: number;
}

function flattenExtractedData(data: ExtractedPaymentInfo | null): FieldRow[] {
  if (!data) return [];
  const rows: FieldRow[] = [];

  // Product info
  const pi = data.product_info;
  if (pi) {
    if (pi.name) rows.push({ section: '商品情報', label: '商品名', key: 'product_name', value: pi.name });
    if (pi.description) rows.push({ section: '商品情報', label: '説明', key: 'product_description', value: pi.description });
    if (pi.sku) rows.push({ section: '商品情報', label: 'SKU', key: 'product_sku', value: pi.sku });
    if (pi.category) rows.push({ section: '商品情報', label: 'カテゴリ', key: 'product_category', value: pi.category });
    if (pi.brand) rows.push({ section: '商品情報', label: 'ブランド', key: 'product_brand', value: pi.brand });
  }

  // Price info
  if (data.price_info) {
    data.price_info.forEach((p: PriceInfo, i: number) => {
      const label = p.price_type ?? `価格 ${i + 1}`;
      const display = `${p.amount.toLocaleString()} ${p.currency}${p.condition ? ` (${p.condition})` : ''}`;
      rows.push({ section: '価格情報', label, key: `price_${i}`, value: display, numericValue: p.amount });
    });
  }

  // Payment methods
  if (data.payment_methods) {
    data.payment_methods.forEach((pm: PaymentMethod, i: number) => {
      const detail = pm.processing_fee
        ? ` 手数料: ${pm.processing_fee}${pm.fee_type === 'percentage' ? '%' : '円'}`
        : '';
      rows.push({ section: '支払い方法', label: pm.method_name, key: `pm_${i}`, value: `${pm.provider ?? '—'}${detail}` });
    });
  }

  // Fees
  if (data.fees) {
    data.fees.forEach((f: Fee, i: number) => {
      const display = `${f.amount.toLocaleString()} ${f.currency}${f.condition ? ` (${f.condition})` : ''}`;
      rows.push({ section: '手数料', label: f.fee_type, key: `fee_${i}`, value: display, numericValue: f.amount });
    });
  }

  // Overall confidence
  if (data.overall_confidence_score != null) {
    rows.push({
      section: 'メタ情報',
      label: '全体信頼度',
      key: 'overall_confidence',
      value: (data.overall_confidence_score * 100).toFixed(1) + '%',
      numericValue: data.overall_confidence_score,
    });
  }

  if (data.status) {
    const statusLabels: Record<string, string> = { pending: '保留中', approved: '承認済み', rejected: '却下', failed: '失敗' };
    rows.push({ section: 'メタ情報', label: 'ステータス', key: 'status', value: statusLabels[data.status] ?? data.status });
  }

  return rows;
}

/** Merge two field-row lists into a unified comparison list. */
interface ComparisonRow {
  section: string;
  label: string;
  key: string;
  leftValue: string;
  rightValue: string;
  leftNumeric?: number;
  rightNumeric?: number;
  changed: boolean;
  diff?: string;
  diffDirection?: 'positive' | 'negative' | 'zero';
}

function buildComparisonRows(leftRows: FieldRow[], rightRows: FieldRow[]): ComparisonRow[] {
  const rightMap = new Map<string, FieldRow>();
  rightRows.forEach((r) => rightMap.set(r.key, r));

  const seen = new Set<string>();
  const result: ComparisonRow[] = [];

  // Walk left rows first
  for (const left of leftRows) {
    seen.add(left.key);
    const right = rightMap.get(left.key);
    const rightValue = right?.value ?? '—';
    const changed = rightValue !== left.value;

    const row: ComparisonRow = {
      section: left.section,
      label: left.label,
      key: left.key,
      leftValue: left.value,
      rightValue,
      leftNumeric: left.numericValue,
      rightNumeric: right?.numericValue,
      changed,
    };

    // Numeric diff
    if (changed && left.numericValue != null && right?.numericValue != null) {
      const diff = right.numericValue - left.numericValue;
      const sign = diff > 0 ? '+' : '';
      row.diff = `${sign}${diff.toLocaleString()}`;
      row.diffDirection = diff > 0 ? 'positive' : diff < 0 ? 'negative' : 'zero';
    }

    result.push(row);
  }

  // Add right-only rows
  for (const right of rightRows) {
    if (!seen.has(right.key)) {
      result.push({
        section: right.section,
        label: right.label,
        key: right.key,
        leftValue: '—',
        rightValue: right.value,
        rightNumeric: right.numericValue,
        changed: true,
      });
    }
  }

  return result;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

const CrawlResultComparison: React.FC<CrawlResultComparisonProps> = ({ siteId }) => {
  const [crawlResults, setCrawlResults] = useState<CrawlResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Selected IDs
  const [leftId, setLeftId] = useState<number | ''>('');
  const [rightId, setRightId] = useState<number | ''>('');

  // Fetched extracted data
  const [leftData, setLeftData] = useState<ExtractedPaymentInfo | null>(null);
  const [rightData, setRightData] = useState<ExtractedPaymentInfo | null>(null);
  const [comparing, setComparing] = useState(false);
  const [compareError, setCompareError] = useState<string | null>(null);

  // Load crawl results for the site
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const results = await getCrawlResults(siteId);
        if (!cancelled) {
          // Sort newest first
          const sorted = [...results].sort(
            (a, b) => new Date(b.crawled_at).getTime() - new Date(a.crawled_at).getTime(),
          );
          setCrawlResults(sorted);
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'クロール結果の取得に失敗しました');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [siteId]);

  // Compare handler
  const handleCompare = useCallback(async () => {
    if (leftId === '' || rightId === '') return;
    setComparing(true);
    setCompareError(null);
    setLeftData(null);
    setRightData(null);
    try {
      const [left, right] = await Promise.all([
        fetchExtractedData(leftId),
        fetchExtractedData(rightId),
      ]);
      setLeftData(left);
      setRightData(right);
    } catch (err: unknown) {
      setCompareError(err instanceof Error ? err.message : '比較データの取得に失敗しました');
    } finally {
      setComparing(false);
    }
  }, [leftId, rightId]);

  // Derived comparison rows
  const leftRows = useMemo(() => flattenExtractedData(leftData), [leftData]);
  const rightRows = useMemo(() => flattenExtractedData(rightData), [rightData]);
  const comparisonRows = useMemo(() => buildComparisonRows(leftRows, rightRows), [leftRows, rightRows]);

  // Group rows by section
  const sections = useMemo(() => {
    const map = new Map<string, ComparisonRow[]>();
    for (const row of comparisonRows) {
      const list = map.get(row.section) ?? [];
      list.push(row);
      map.set(row.section, list);
    }
    return map;
  }, [comparisonRows]);

  // Screenshot URLs
  const leftCrawl = crawlResults.find((cr) => cr.id === leftId);
  const rightCrawl = crawlResults.find((cr) => cr.id === rightId);
  const leftScreenshot = buildScreenshotUrl(
    leftCrawl?.screenshot_path,
    leftData?.metadata?.screenshot_path as string | undefined,
  );
  const rightScreenshot = buildScreenshotUrl(
    rightCrawl?.screenshot_path,
    rightData?.metadata?.screenshot_path as string | undefined,
  );

  /* ---- Render ---- */

  if (loading) {
    return <div className="comparison__loading" role="status">クロール結果を読み込み中...</div>;
  }

  if (error) {
    return <div className="comparison__empty" role="alert">エラー: {error}</div>;
  }

  if (crawlResults.length < 2) {
    return (
      <div className="comparison__empty">
        比較するには2件以上のクロール結果が必要です。
      </div>
    );
  }

  return (
    <div className="comparison">
      {/* Header with selectors */}
      <div className="comparison__header">
        <h2>クロール結果比較</h2>
        <div className="comparison__selectors">
          <div className="comparison__selector-group">
            <label htmlFor="comparison-left">比較元（古い方）</label>
            <select
              id="comparison-left"
              value={leftId}
              onChange={(e) => setLeftId(e.target.value ? Number(e.target.value) : '')}
            >
              <option value="">選択してください</option>
              {crawlResults.map((cr) => (
                <option key={cr.id} value={cr.id}>
                  {formatCrawlLabel(cr)}
                </option>
              ))}
            </select>
          </div>

          <div className="comparison__selector-group">
            <label htmlFor="comparison-right">比較先（新しい方）</label>
            <select
              id="comparison-right"
              value={rightId}
              onChange={(e) => setRightId(e.target.value ? Number(e.target.value) : '')}
            >
              <option value="">選択してください</option>
              {crawlResults.map((cr) => (
                <option key={cr.id} value={cr.id}>
                  {formatCrawlLabel(cr)}
                </option>
              ))}
            </select>
          </div>

          <button
            type="button"
            className="comparison__compare-btn"
            disabled={leftId === '' || rightId === '' || leftId === rightId || comparing}
            onClick={handleCompare}
          >
            {comparing ? '比較中...' : '比較する'}
          </button>
        </div>
      </div>

      {compareError && (
        <div className="comparison__empty" role="alert">エラー: {compareError}</div>
      )}

      {/* Comparison results */}
      {leftData && rightData && (
        <>
          {/* Screenshots side by side */}
          <div className="comparison__screenshots">
            <div className="comparison__screenshot-panel">
              <h3>比較元: {leftCrawl ? new Date(leftCrawl.crawled_at).toLocaleString('ja-JP') : ''}</h3>
              {leftScreenshot ? (
                <img src={leftScreenshot} alt="比較元スクリーンショット" />
              ) : (
                <div className="comparison__no-screenshot">スクリーンショットなし</div>
              )}
            </div>
            <div className="comparison__screenshot-panel">
              <h3>比較先: {rightCrawl ? new Date(rightCrawl.crawled_at).toLocaleString('ja-JP') : ''}</h3>
              {rightScreenshot ? (
                <img src={rightScreenshot} alt="比較先スクリーンショット" />
              ) : (
                <div className="comparison__no-screenshot">スクリーンショットなし</div>
              )}
            </div>
          </div>

          {/* Data comparison tables by section */}
          {Array.from(sections.entries()).map(([sectionName, rows]) => (
            <div key={sectionName} className="comparison__data">
              <h3>{sectionName}</h3>
              <table className="comparison__table">
                <thead>
                  <tr>
                    <th>項目</th>
                    <th>比較元</th>
                    <th>比較先</th>
                    <th>差分</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr
                      key={row.key}
                      className={row.changed ? 'comparison__row--changed' : ''}
                    >
                      <td>{row.label}</td>
                      <td>{row.leftValue}</td>
                      <td>{row.rightValue}</td>
                      <td>
                        {row.diff && (
                          <span className={`comparison__diff comparison__diff--${row.diffDirection}`}>
                            {row.diff}
                          </span>
                        )}
                        {!row.diff && row.changed && (
                          <span className="comparison__diff comparison__diff--positive">変更あり</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}

          {comparisonRows.length === 0 && (
            <div className="comparison__empty">比較可能なデータがありません。</div>
          )}
        </>
      )}
    </div>
  );
};

export default CrawlResultComparison;
