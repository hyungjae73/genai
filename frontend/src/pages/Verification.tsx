import { useEffect, useState } from 'react';
import {
  getSites,
  triggerVerification,
  getVerificationResults,
  getVerificationStatus,
  type Site,
  type VerificationResult,
} from '../services/api';
import { Select } from '../components/ui/Select/Select';
import { Button } from '../components/ui/Button/Button';
import { Badge } from '../components/ui/Badge/Badge';
import { Table, type TableColumn } from '../components/ui/Table/Table';
import { Card } from '../components/ui/Card/Card';
import './Verification.css';

interface VerificationState {
  selectedSiteId: number | null;
  isLoading: boolean;
  currentResult: VerificationResult | null;
  historicalResults: VerificationResult[];
  error: string | null;
  isRunning: boolean;
  jobId: number | null;
}

interface ComparisonRow {
  field: string;
  htmlValue: string;
  ocrValue: string;
  ocrConfidence: number;
  hasOcrData: boolean;
  statusClass: string;
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
    case 'success': return 'success';
    case 'partial_failure': return 'warning';
    case 'failure': return 'danger';
    default: return 'info';
  }
};

const Verification = () => {
  const [sites, setSites] = useState<Site[]>([]);
  const [state, setState] = useState<VerificationState>({
    selectedSiteId: null,
    isLoading: false,
    currentResult: null,
    historicalResults: [],
    error: null,
    isRunning: false,
    jobId: null,
  });

  useEffect(() => {
    fetchSites();
  }, []);

  const fetchSites = async () => {
    try {
      const sitesData = await getSites();
      setSites(sitesData.filter(s => s.is_active));
    } catch (err) {
      console.error('Failed to fetch sites:', err);
    }
  };

  const handleRunVerification = async () => {
    if (!state.selectedSiteId) {
      setState(prev => ({ ...prev, error: 'サイトを選択してください' }));
      return;
    }

    setState(prev => ({ ...prev, isLoading: true, isRunning: true, error: null }));

    try {
      const response = await triggerVerification({
        site_id: state.selectedSiteId,
      });

      setState(prev => ({ ...prev, jobId: response.job_id }));

      const pollInterval = setInterval(async () => {
        try {
          const status = await getVerificationStatus(response.job_id);

          if (status.status === 'completed' || status.status === 'failed') {
            clearInterval(pollInterval);

            const results = await getVerificationResults(state.selectedSiteId!, 10, 0);

            setState(prev => ({
              ...prev,
              isLoading: false,
              isRunning: false,
              currentResult: results.results[0] || null,
              historicalResults: results.results,
              error: status.status === 'failed' ? status.result?.error_message || 'Verification failed' : null,
            }));
          }
        } catch (err) {
          clearInterval(pollInterval);
          setState(prev => ({
            ...prev,
            isLoading: false,
            isRunning: false,
            error: '検証ステータスの取得に失敗しました',
          }));
        }
      }, 2000);

      setTimeout(() => {
        clearInterval(pollInterval);
        if (state.isRunning) {
          setState(prev => ({
            ...prev,
            isLoading: false,
            isRunning: false,
            error: '検証がタイムアウトしました',
          }));
        }
      }, 60000);
    } catch (err: any) {
      setState(prev => ({
        ...prev,
        isLoading: false,
        isRunning: false,
        error: err.response?.data?.detail || '検証の開始に失敗しました',
      }));
    }
  };

  const handleSelectHistoricalResult = (result: VerificationResult) => {
    setState(prev => ({ ...prev, currentResult: result }));
  };

  const handleExportCSV = () => {
    if (!state.currentResult) return;

    const rows: string[][] = [];
    rows.push(['Field Name', 'HTML Value', 'OCR Value', 'Contract Value', 'Status']);

    const result = state.currentResult;
    const fields = new Set([
      ...Object.keys(result.html_data),
      ...Object.keys(result.ocr_data),
    ]);

    fields.forEach(field => {
      const htmlValue = JSON.stringify(result.html_data[field] || 'N/A');
      const ocrValue = JSON.stringify(result.ocr_data[field] || 'N/A');
      const discrepancy = result.discrepancies.find(d => d.field_name === field);
      const status = discrepancy ? 'Discrepancy' : 'Match';

      rows.push([field, htmlValue, ocrValue, '', status]);
    });

    const csvContent = rows.map(row => row.join(',')).join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `verification_${result.site_id}_${new Date().toISOString()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const getStatusClass = (field: string): string => {
    if (!state.currentResult) return '';

    const htmlViolation = state.currentResult.html_violations.find(v => v.field_name === field);
    const ocrViolation = state.currentResult.ocr_violations.find(v => v.field_name === field);
    const discrepancy = state.currentResult.discrepancies.find(d => d.field_name === field);

    if (htmlViolation || ocrViolation) return 'verification-row--violation';
    if (discrepancy) return 'verification-row--discrepancy';
    return 'verification-row--match';
  };

  const getStatusIcon = (field: string): string => {
    if (!state.currentResult) return '';

    const htmlViolation = state.currentResult.html_violations.find(v => v.field_name === field);
    const ocrViolation = state.currentResult.ocr_violations.find(v => v.field_name === field);

    if (htmlViolation && ocrViolation) return '⚠️ Both';
    if (htmlViolation) return '⚠️ HTML';
    if (ocrViolation) return '⚠️ OCR';
    return '✓';
  };

  const renderValue = (value: any): string => {
    if (value === null || value === undefined) return 'Not Found';
    if (typeof value === 'object') return JSON.stringify(value, null, 2);
    return String(value);
  };

  // Build comparison rows for the Table component
  const buildComparisonRows = (): ComparisonRow[] => {
    if (!state.currentResult) return [];

    const fields = Object.keys(state.currentResult.html_data);
    return fields.map(field => ({
      field,
      htmlValue: renderValue(state.currentResult!.html_data[field]),
      ocrValue: renderValue(state.currentResult!.ocr_data[field]),
      ocrConfidence: state.currentResult!.ocr_confidence,
      hasOcrData: !!state.currentResult!.ocr_data[field],
      statusClass: getStatusClass(field),
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
            <span className="verification-comparison confidence-indicator">
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

  // Build site options for the Select component
  const siteOptions = [
    { value: '', label: 'サイトを選択' },
    ...sites.map(site => ({ value: String(site.id), label: site.name })),
  ];

  return (
    <div className="verification">
      <div className="page-header">
        <h1>検証・比較システム</h1>
      </div>

      <Card padding="lg" className="verification-controls">
        <div className="control-group">
          <Select
            label="監視対象サイト"
            value={state.selectedSiteId ? String(state.selectedSiteId) : ''}
            onChange={(val) => setState(prev => ({ ...prev, selectedSiteId: val ? Number(val) : null }))}
            options={siteOptions}
            filterable
            aria-label="監視対象サイト"
          />
        </div>

        <Button
          variant="primary"
          size="md"
          onClick={handleRunVerification}
          disabled={!state.selectedSiteId || state.isLoading}
          loading={state.isLoading}
        >
          {state.isLoading ? '検証中...' : '検証実行'}
        </Button>

        {state.currentResult && (
          <Button
            variant="secondary"
            size="md"
            onClick={handleExportCSV}
            disabled={state.isLoading}
          >
            CSV出力
          </Button>
        )}
      </Card>

      {state.error && (
        <div className="verification-error">{state.error}</div>
      )}

      {state.isLoading && (
        <div className="verification-loading">
          <div className="verification-spinner" />
          <p>検証を実行中です。しばらくお待ちください...</p>
        </div>
      )}

      {state.currentResult && !state.isLoading && (
        <div className="verification-results">
          <div className="verification-result-header">
            <h2>検証結果</h2>
            <div className="verification-result-meta">
              <span>実行日時: {new Date(state.currentResult.created_at).toLocaleString('ja-JP')}</span>
              <span>OCR信頼度: {(state.currentResult.ocr_confidence * 100).toFixed(1)}%</span>
              <Badge variant={statusToBadgeVariant(state.currentResult.status)}>
                {state.currentResult.status}
              </Badge>
            </div>
          </div>

          <div className="verification-comparison">
            <Table<ComparisonRow>
              columns={comparisonColumns}
              data={buildComparisonRows()}
              mobileLayout="scroll"
              emptyMessage="比較データがありません"
              aria-label="検証比較テーブル"
            />
          </div>

          {state.currentResult.discrepancies.length > 0 && (
            <div className="verification-section">
              <h3>検出された差異</h3>
              <div className="verification-section-list">
                {state.currentResult.discrepancies.map((disc, idx) => (
                  <Card key={idx} borderLeft={severityToBadgeVariant(disc.severity) === 'neutral' ? undefined : severityToBadgeVariant(disc.severity) as 'danger' | 'warning'} padding="md">
                    <div className="verification-issue-header">
                      <span className="verification-field-name">{disc.field_name}</span>
                      <Badge variant={severityToBadgeVariant(disc.severity)} size="sm">
                        {disc.severity}
                      </Badge>
                    </div>
                    <div className="verification-issue-details">
                      <div><strong>HTML:</strong> {renderValue(disc.html_value)}</div>
                      <div><strong>OCR:</strong> {renderValue(disc.ocr_value)}</div>
                      <div><strong>差異タイプ:</strong> {disc.difference_type}</div>
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          )}

          {(state.currentResult.html_violations.length > 0 || state.currentResult.ocr_violations.length > 0) && (
            <div className="verification-section">
              <h3>検出された違反</h3>

              {state.currentResult.html_violations.length > 0 && (
                <div className="verification-section-list">
                  <h4>HTML違反</h4>
                  {state.currentResult.html_violations.map((violation, idx) => (
                    <Card key={idx} borderLeft={severityToBadgeVariant(violation.severity) === 'neutral' ? undefined : severityToBadgeVariant(violation.severity) as 'danger' | 'warning'} padding="md">
                      <div className="verification-issue-header">
                        <span className="verification-field-name">{violation.field_name}</span>
                        <Badge variant={severityToBadgeVariant(violation.severity)} size="sm">
                          {violation.severity}
                        </Badge>
                      </div>
                      <p className="verification-issue-message">{violation.message}</p>
                      <div className="verification-issue-details">
                        <div><strong>期待値:</strong> {renderValue(violation.expected_value)}</div>
                        <div><strong>実際の値:</strong> {renderValue(violation.actual_value)}</div>
                      </div>
                    </Card>
                  ))}
                </div>
              )}

              {state.currentResult.ocr_violations.length > 0 && (
                <div className="verification-section-list">
                  <h4>OCR違反</h4>
                  {state.currentResult.ocr_violations.map((violation, idx) => (
                    <Card key={idx} borderLeft={severityToBadgeVariant(violation.severity) === 'neutral' ? undefined : severityToBadgeVariant(violation.severity) as 'danger' | 'warning'} padding="md">
                      <div className="verification-issue-header">
                        <span className="verification-field-name">{violation.field_name}</span>
                        <Badge variant={severityToBadgeVariant(violation.severity)} size="sm">
                          {violation.severity}
                        </Badge>
                      </div>
                      <p className="verification-issue-message">{violation.message}</p>
                      <div className="verification-issue-details">
                        <div><strong>期待値:</strong> {renderValue(violation.expected_value)}</div>
                        <div><strong>実際の値:</strong> {renderValue(violation.actual_value)}</div>
                      </div>
                    </Card>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {state.historicalResults.length > 1 && (
        <div className="verification-section">
          <h3>過去の検証結果</h3>
          <div className="verification-section-list">
            {state.historicalResults.map(result => (
              <div
                key={result.id}
                className={`verification-history-item ${result.id === state.currentResult?.id ? 'verification-history-item--active' : ''}`}
                onClick={() => handleSelectHistoricalResult(result)}
              >
                <div className="verification-history-date">
                  {new Date(result.created_at).toLocaleString('ja-JP')}
                </div>
                <div className="verification-history-summary">
                  <span>差異: {result.discrepancies.length}</span>
                  <span>違反: {result.html_violations.length + result.ocr_violations.length}</span>
                  <Badge variant={statusToBadgeVariant(result.status)} size="sm">
                    {result.status}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default Verification;
