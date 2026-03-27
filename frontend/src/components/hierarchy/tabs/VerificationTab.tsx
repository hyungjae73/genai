import { useState, useEffect, useCallback, useRef } from 'react';
import {
  triggerVerification,
  getVerificationResults,
  getVerificationStatus,
} from '../../../services/api';
import type { VerificationResult } from '../../../services/api';
import { Button } from '../../ui/Button/Button';
import { Badge } from '../../ui/Badge/Badge';
import { Table, type TableColumn } from '../../ui/Table/Table';
import { Card } from '../../ui/Card/Card';
import './VerificationTab.css';

export interface VerificationTabProps {
  siteId: number;
}

interface ComparisonRow {
  field: string;
  htmlValue: string;
  ocrValue: string;
  ocrConfidence: number;
  hasOcrData: boolean;
  statusIcon: string;
  [key: string]: unknown;
}

const severityToBadgeVariant = (severity: string): 'danger' | 'warning' | 'neutral' => {
  switch (severity) {
    case 'high': return 'danger';
    case 'medium': return 'warning';
    default: return 'neutral';
  }
};

const statusToBadgeVariant = (status: string): 'success' | 'warning' | 'danger' | 'info' => {
  switch (status) {
    case 'completed': return 'success';
    case 'partial_failure': return 'warning';
    case 'failed': return 'danger';
    default: return 'info';
  }
};

const renderValue = (value: any): string => {
  if (value === null || value === undefined) return 'N/A';
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value);
};

const VerificationTab = ({ siteId }: VerificationTabProps) => {
  const [currentResult, setCurrentResult] = useState<VerificationResult | null>(null);
  const [historicalResults, setHistoricalResults] = useState<VerificationResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchResults = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await getVerificationResults(siteId, 10, 0);
      setHistoricalResults(response.results);
      if (response.results.length > 0) {
        setCurrentResult(response.results[0]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '検証結果の取得に失敗しました');
    } finally {
      setLoading(false);
    }
  }, [siteId]);

  useEffect(() => {
    fetchResults();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [fetchResults]);

  const handleRunVerification = async () => {
    setIsRunning(true);
    setError(null);

    try {
      const response = await triggerVerification({ site_id: siteId });

      pollRef.current = setInterval(async () => {
        try {
          const status = await getVerificationStatus(response.job_id);
          if (status.status === 'completed' || status.status === 'failed') {
            if (pollRef.current) clearInterval(pollRef.current);
            if (timeoutRef.current) clearTimeout(timeoutRef.current);
            setIsRunning(false);

            if (status.status === 'failed') {
              setError(status.result?.error_message || '検証に失敗しました');
            }
            await fetchResults();
          }
        } catch {
          if (pollRef.current) clearInterval(pollRef.current);
          if (timeoutRef.current) clearTimeout(timeoutRef.current);
          setIsRunning(false);
          setError('検証ステータスの取得に失敗しました');
        }
      }, 2000);

      timeoutRef.current = setTimeout(() => {
        if (pollRef.current) clearInterval(pollRef.current);
        setIsRunning(false);
        setError('検証がタイムアウトしました');
      }, 60000);
    } catch (err: any) {
      setIsRunning(false);
      setError(err.response?.data?.detail || '検証の開始に失敗しました');
    }
  };

  const handleSelectHistoricalResult = (result: VerificationResult) => {
    setCurrentResult(result);
  };

  const handleExportCSV = () => {
    if (!currentResult) return;

    const rows: string[][] = [];
    rows.push(['Field Name', 'HTML Value', 'OCR Value', 'Status']);

    const fields = new Set([
      ...Object.keys(currentResult.html_data || {}),
      ...Object.keys(currentResult.ocr_data || {}),
    ]);

    fields.forEach(field => {
      const htmlValue = renderValue(currentResult.html_data?.[field]);
      const ocrValue = renderValue(currentResult.ocr_data?.[field]);
      const discrepancy = currentResult.discrepancies?.find(d => d.field_name === field);
      const status = discrepancy ? 'Discrepancy' : 'Match';
      rows.push([field, htmlValue, ocrValue, status]);
    });

    const csvContent = rows.map(row =>
      row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(',')
    ).join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `verification_${currentResult.site_id}_${new Date().toISOString()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const getStatusIcon = (field: string): string => {
    if (!currentResult) return '';
    const htmlViolation = currentResult.html_violations?.find(v => v.field_name === field);
    const ocrViolation = currentResult.ocr_violations?.find(v => v.field_name === field);
    if (htmlViolation && ocrViolation) return '⚠️ Both';
    if (htmlViolation) return '⚠️ HTML';
    if (ocrViolation) return '⚠️ OCR';
    return '✓';
  };

  const buildComparisonRows = (): ComparisonRow[] => {
    if (!currentResult) return [];
    const fields = new Set([
      ...Object.keys(currentResult.html_data || {}),
      ...Object.keys(currentResult.ocr_data || {}),
    ]);
    return Array.from(fields).map(field => ({
      field,
      htmlValue: renderValue(currentResult.html_data?.[field]),
      ocrValue: renderValue(currentResult.ocr_data?.[field]),
      ocrConfidence: currentResult.ocr_confidence ?? 0,
      hasOcrData: !!currentResult.ocr_data?.[field],
      statusIcon: getStatusIcon(field),
    }));
  };

  const comparisonColumns: TableColumn<ComparisonRow>[] = [
    { key: 'field', header: 'フィールド名' },
    {
      key: 'htmlValue',
      header: 'HTML値',
      render: (row) => <pre>{row.htmlValue}</pre>,
    },
    {
      key: 'ocrValue',
      header: 'OCR値',
      render: (row) => (
        <>
          <pre>{row.ocrValue}</pre>
          {row.hasOcrData && (
            <span className="confidence-indicator">
              信頼度: {(row.ocrConfidence * 100).toFixed(0)}%
            </span>
          )}
        </>
      ),
    },
    {
      key: 'statusIcon',
      header: 'ステータス',
      render: (row) => (
        <span className="verification-status-cell">{row.statusIcon}</span>
      ),
    },
  ];

  if (loading && !isRunning) {
    return (
      <div className="tab-loading">
        <span className="spinner">⟳</span>
        <span>読み込み中...</span>
      </div>
    );
  }

  return (
    <div className="verification-tab">
      {/* Controls: Run verification + CSV export */}
      <div className="verification-tab-controls">
        <Button
          variant="primary"
          size="md"
          onClick={handleRunVerification}
          disabled={isRunning}
          loading={isRunning}
        >
          {isRunning ? '検証中...' : '検証実行'}
        </Button>

        {currentResult && (
          <Button
            variant="secondary"
            size="md"
            onClick={handleExportCSV}
            disabled={isRunning}
          >
            CSV出力
          </Button>
        )}
      </div>

      {error && (
        <div className="verification-tab-error">{error}</div>
      )}

      {isRunning && (
        <div className="verification-tab-loading">
          <div className="spinner" />
          <p>検証を実行中です...</p>
        </div>
      )}

      {/* Current result */}
      {currentResult && !isRunning && (
        <div className="verification-tab-results">
          <div className="verification-tab-result-header">
            <h3>検証結果</h3>
            <div className="verification-tab-result-meta">
              <span>{new Date(currentResult.created_at).toLocaleString('ja-JP')}</span>
              {currentResult.ocr_confidence !== undefined && (
                <span>OCR信頼度: {(currentResult.ocr_confidence * 100).toFixed(1)}%</span>
              )}
              <Badge variant={statusToBadgeVariant(currentResult.status)}>
                {currentResult.status}
              </Badge>
            </div>
          </div>

          {/* Comparison table */}
          <div className="verification-comparison">
            <Table<ComparisonRow>
              columns={comparisonColumns}
              data={buildComparisonRows()}
              mobileLayout="scroll"
              emptyMessage="比較データがありません"
              aria-label="検証比較テーブル"
            />
          </div>

          {/* Discrepancies with severity badges */}
          {currentResult.discrepancies && currentResult.discrepancies.length > 0 && (
            <div className="verification-tab-section">
              <h3>検出された差異</h3>
              <div className="verification-tab-section-list">
                {currentResult.discrepancies.map((disc, idx) => (
                  <Card
                    key={idx}
                    borderLeft={
                      severityToBadgeVariant(disc.severity) === 'neutral'
                        ? undefined
                        : (severityToBadgeVariant(disc.severity) as 'danger' | 'warning')
                    }
                    padding="md"
                  >
                    <div className="verification-tab-issue-header">
                      <span className="verification-tab-field-name">{disc.field_name}</span>
                      <Badge variant={severityToBadgeVariant(disc.severity)} size="sm">
                        {disc.severity}
                      </Badge>
                    </div>
                    <div className="verification-tab-issue-details">
                      <div><strong>HTML:</strong> {renderValue(disc.html_value)}</div>
                      <div><strong>OCR:</strong> {renderValue(disc.ocr_value)}</div>
                      <div><strong>差異タイプ:</strong> {disc.difference_type}</div>
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Historical results */}
      {historicalResults.length > 0 && !isRunning && (
        <div className="verification-tab-section">
          <h3>過去の検証結果</h3>
          <div className="verification-tab-section-list">
            {historicalResults.map(result => (
              <div
                key={result.id}
                className={`verification-tab-history-item ${
                  result.id === currentResult?.id ? 'verification-tab-history-item--active' : ''
                }`}
                onClick={() => handleSelectHistoricalResult(result)}
              >
                <div className="verification-tab-history-date">
                  {new Date(result.created_at).toLocaleString('ja-JP')}
                </div>
                <div className="verification-tab-history-summary">
                  <span>差異: {result.discrepancies?.length || 0}</span>
                  <span>
                    違反: {(result.html_violations?.length || 0) + (result.ocr_violations?.length || 0)}
                  </span>
                  <Badge variant={statusToBadgeVariant(result.status)} size="sm">
                    {result.status}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty state */}
      {!currentResult && !isRunning && !loading && historicalResults.length === 0 && (
        <div className="tab-empty">
          <p>検証結果がありません。「検証実行」ボタンで検証を開始してください。</p>
        </div>
      )}
    </div>
  );
};

export default VerificationTab;
