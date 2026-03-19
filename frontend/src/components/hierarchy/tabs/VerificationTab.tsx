import { useState, useEffect } from 'react';
import { getVerificationResults } from '../../../services/api';
import type { VerificationResult } from '../../../services/api';

export interface VerificationTabProps {
  siteId: number;
}

const VerificationTab = ({ siteId }: VerificationTabProps) => {
  const [verificationResults, setVerificationResults] = useState<VerificationResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);

        const response = await getVerificationResults(siteId);
        setVerificationResults(response.results);
      } catch (err) {
        setError(err instanceof Error ? err.message : '検証結果の取得に失敗しました');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [siteId]);

  const getStatusLabel = (status: string): string => {
    const statusMap: Record<string, string> = {
      completed: '完了',
      pending: '処理中',
      failed: '失敗',
      error: 'エラー',
    };
    return statusMap[status] || status;
  };

  const getStatusClass = (status: string): string => {
    const statusClassMap: Record<string, string> = {
      completed: 'status-completed',
      pending: 'status-pending',
      failed: 'status-failed',
      error: 'status-error',
    };
    return statusClassMap[status] || 'status-unknown';
  };

  if (loading) {
    return (
      <div className="tab-loading">
        <span className="spinner">⟳</span>
        <span>読み込み中...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="tab-error">
        <p>エラー: {error}</p>
      </div>
    );
  }

  if (verificationResults.length === 0) {
    return (
      <div className="tab-empty">
        <p>検証結果がありません</p>
      </div>
    );
  }

  return (
    <div className="verification-tab">
      {verificationResults.map((result) => {
        const discrepancyCount = result.discrepancies?.length || 0;
        const violationCount = 
          (result.html_violations?.length || 0) + 
          (result.ocr_violations?.length || 0);

        return (
          <div key={result.id} className="verification-item">
            <div className="verification-header">
              <span className={`status-badge ${getStatusClass(result.status)}`}>
                {getStatusLabel(result.status)}
              </span>
              <span className="verification-date">
                {new Date(result.created_at).toLocaleString('ja-JP')}
              </span>
            </div>

            <div className="verification-summary">
              <div className="summary-item">
                <span className="summary-label">差異件数:</span>
                <span className="summary-value">{discrepancyCount}</span>
              </div>
              <div className="summary-item">
                <span className="summary-label">違反件数:</span>
                <span className="summary-value">{violationCount}</span>
              </div>
              {result.ocr_confidence !== undefined && (
                <div className="summary-item">
                  <span className="summary-label">OCR信頼度:</span>
                  <span className="summary-value">
                    {(result.ocr_confidence * 100).toFixed(0)}%
                  </span>
                </div>
              )}
            </div>

            {result.error_message && (
              <div className="verification-error">
                <p>エラーメッセージ: {result.error_message}</p>
              </div>
            )}

            {/* Discrepancies */}
            {discrepancyCount > 0 && (
              <div className="verification-section">
                <h4>差異詳細</h4>
                <div className="discrepancies-list">
                  {result.discrepancies.map((discrepancy, index) => (
                    <div key={index} className="discrepancy-item">
                      <div className="discrepancy-field">
                        <strong>{discrepancy.field_name}</strong>
                        <span className={`severity-badge severity-${discrepancy.severity}`}>
                          {discrepancy.severity}
                        </span>
                      </div>
                      <div className="discrepancy-values">
                        <div className="value-item">
                          <span className="value-label">HTML値:</span>
                          <span className="value-content">
                            {JSON.stringify(discrepancy.html_value)}
                          </span>
                        </div>
                        <div className="value-item">
                          <span className="value-label">OCR値:</span>
                          <span className="value-content">
                            {JSON.stringify(discrepancy.ocr_value)}
                          </span>
                        </div>
                      </div>
                      <div className="discrepancy-type">
                        差異タイプ: {discrepancy.difference_type}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Violations */}
            {violationCount > 0 && (
              <div className="verification-section">
                <h4>違反詳細</h4>
                <div className="violations-list">
                  {[...(result.html_violations || []), ...(result.ocr_violations || [])].map(
                    (violation, index) => (
                      <div key={index} className="violation-item">
                        <div className="violation-header">
                          <strong>{violation.field_name}</strong>
                          <span className={`severity-badge severity-${violation.severity}`}>
                            {violation.severity}
                          </span>
                          <span className="data-source-badge">
                            {violation.data_source}
                          </span>
                        </div>
                        <div className="violation-message">{violation.message}</div>
                        <div className="violation-values">
                          <div className="value-item">
                            <span className="value-label">期待値:</span>
                            <span className="value-content">
                              {JSON.stringify(violation.expected_value)}
                            </span>
                          </div>
                          <div className="value-item">
                            <span className="value-label">実際値:</span>
                            <span className="value-content">
                              {JSON.stringify(violation.actual_value)}
                            </span>
                          </div>
                        </div>
                        <div className="violation-type">
                          違反タイプ: {violation.violation_type}
                        </div>
                      </div>
                    )
                  )}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default VerificationTab;
