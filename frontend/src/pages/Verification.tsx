import { useEffect, useState } from 'react';
import {
  getSites,
  triggerVerification,
  getVerificationResults,
  getVerificationStatus,
  type Site,
  type VerificationResult,
} from '../services/api';

interface VerificationState {
  selectedSiteId: number | null;
  isLoading: boolean;
  currentResult: VerificationResult | null;
  historicalResults: VerificationResult[];
  error: string | null;
  isRunning: boolean;
  jobId: number | null;
}

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
      // Trigger verification
      const response = await triggerVerification({
        site_id: state.selectedSiteId,
      });

      setState(prev => ({ ...prev, jobId: response.job_id }));

      // Poll for completion
      const pollInterval = setInterval(async () => {
        try {
          const status = await getVerificationStatus(response.job_id);
          
          if (status.status === 'completed' || status.status === 'failed') {
            clearInterval(pollInterval);
            
            // Fetch results
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

      // Timeout after 60 seconds
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

    const rows = [];
    rows.push(['Field Name', 'HTML Value', 'OCR Value', 'Contract Value', 'Status']);

    // Add data rows
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

  const getStatusColor = (field: string): string => {
    if (!state.currentResult) return '';
    
    const discrepancy = state.currentResult.discrepancies.find(d => d.field_name === field);
    const htmlViolation = state.currentResult.html_violations.find(v => v.field_name === field);
    const ocrViolation = state.currentResult.ocr_violations.find(v => v.field_name === field);
    
    if (htmlViolation || ocrViolation) return 'status-violation';
    if (discrepancy) return 'status-discrepancy';
    return 'status-match';
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

  return (
    <div className="verification">
      <div className="page-header">
        <h1>検証・比較システム</h1>
      </div>

      <div className="verification-controls">
        <div className="control-group">
          <label htmlFor="site-select">監視対象サイト:</label>
          <select
            id="site-select"
            value={state.selectedSiteId || ''}
            onChange={(e) => setState(prev => ({ ...prev, selectedSiteId: Number(e.target.value) }))}
            disabled={state.isLoading}
          >
            <option value="">サイトを選択</option>
            {sites.map(site => (
              <option key={site.id} value={site.id}>
                {site.name}
              </option>
            ))}
          </select>
        </div>

        <button
          className="btn btn-primary"
          onClick={handleRunVerification}
          disabled={!state.selectedSiteId || state.isLoading}
        >
          {state.isLoading ? '検証中...' : '検証実行'}
        </button>

        {state.currentResult && (
          <button
            className="btn btn-secondary"
            onClick={handleExportCSV}
            disabled={state.isLoading}
          >
            CSV出力
          </button>
        )}
      </div>

      {state.error && (
        <div className="error-message">{state.error}</div>
      )}

      {state.isLoading && (
        <div className="loading-indicator">
          <div className="spinner"></div>
          <p>検証を実行中です。しばらくお待ちください...</p>
        </div>
      )}

      {state.currentResult && !state.isLoading && (
        <div className="verification-results">
          <div className="result-header">
            <h2>検証結果</h2>
            <div className="result-meta">
              <span>実行日時: {new Date(state.currentResult.created_at).toLocaleString('ja-JP')}</span>
              <span>OCR信頼度: {(state.currentResult.ocr_confidence * 100).toFixed(1)}%</span>
              <span className={`status-badge status-${state.currentResult.status}`}>
                {state.currentResult.status}
              </span>
            </div>
          </div>

          <div className="comparison-table">
            <table>
              <thead>
                <tr>
                  <th>フィールド名</th>
                  <th>HTML値</th>
                  <th>OCR値</th>
                  <th>ステータス</th>
                </tr>
              </thead>
              <tbody>
                {Object.keys(state.currentResult.html_data).map(field => (
                  <tr key={field} className={getStatusColor(field)}>
                    <td>{field}</td>
                    <td>
                      <pre>{renderValue(state.currentResult!.html_data[field])}</pre>
                    </td>
                    <td>
                      <pre>{renderValue(state.currentResult!.ocr_data[field])}</pre>
                      {state.currentResult!.ocr_data[field] && (
                        <span className="confidence-badge">
                          信頼度: {(state.currentResult!.ocr_confidence * 100).toFixed(0)}%
                        </span>
                      )}
                    </td>
                    <td className="status-cell">
                      {getStatusIcon(field)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {state.currentResult.discrepancies.length > 0 && (
            <div className="discrepancies-section">
              <h3>検出された差異</h3>
              <div className="discrepancies-list">
                {state.currentResult.discrepancies.map((disc, idx) => (
                  <div key={idx} className={`discrepancy-item severity-${disc.severity}`}>
                    <div className="discrepancy-header">
                      <span className="field-name">{disc.field_name}</span>
                      <span className={`severity-badge severity-${disc.severity}`}>
                        {disc.severity}
                      </span>
                    </div>
                    <div className="discrepancy-details">
                      <div>
                        <strong>HTML:</strong> {renderValue(disc.html_value)}
                      </div>
                      <div>
                        <strong>OCR:</strong> {renderValue(disc.ocr_value)}
                      </div>
                      <div>
                        <strong>差異タイプ:</strong> {disc.difference_type}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {(state.currentResult.html_violations.length > 0 || state.currentResult.ocr_violations.length > 0) && (
            <div className="violations-section">
              <h3>検出された違反</h3>
              
              {state.currentResult.html_violations.length > 0 && (
                <div className="violations-group">
                  <h4>HTML違反</h4>
                  {state.currentResult.html_violations.map((violation, idx) => (
                    <div key={idx} className={`violation-item severity-${violation.severity}`}>
                      <div className="violation-header">
                        <span className="field-name">{violation.field_name}</span>
                        <span className={`severity-badge severity-${violation.severity}`}>
                          {violation.severity}
                        </span>
                      </div>
                      <div className="violation-message">{violation.message}</div>
                      <div className="violation-details">
                        <div><strong>期待値:</strong> {renderValue(violation.expected_value)}</div>
                        <div><strong>実際の値:</strong> {renderValue(violation.actual_value)}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {state.currentResult.ocr_violations.length > 0 && (
                <div className="violations-group">
                  <h4>OCR違反</h4>
                  {state.currentResult.ocr_violations.map((violation, idx) => (
                    <div key={idx} className={`violation-item severity-${violation.severity}`}>
                      <div className="violation-header">
                        <span className="field-name">{violation.field_name}</span>
                        <span className={`severity-badge severity-${violation.severity}`}>
                          {violation.severity}
                        </span>
                      </div>
                      <div className="violation-message">{violation.message}</div>
                      <div className="violation-details">
                        <div><strong>期待値:</strong> {renderValue(violation.expected_value)}</div>
                        <div><strong>実際の値:</strong> {renderValue(violation.actual_value)}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {state.historicalResults.length > 1 && (
        <div className="historical-results">
          <h3>過去の検証結果</h3>
          <div className="historical-list">
            {state.historicalResults.map(result => (
              <div
                key={result.id}
                className={`historical-item ${result.id === state.currentResult?.id ? 'active' : ''}`}
                onClick={() => handleSelectHistoricalResult(result)}
              >
                <div className="historical-date">
                  {new Date(result.created_at).toLocaleString('ja-JP')}
                </div>
                <div className="historical-summary">
                  <span>差異: {result.discrepancies.length}</span>
                  <span>違反: {result.html_violations.length + result.ocr_violations.length}</span>
                  <span className={`status-badge status-${result.status}`}>
                    {result.status}
                  </span>
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
