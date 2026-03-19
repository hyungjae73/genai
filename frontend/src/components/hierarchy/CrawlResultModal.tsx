import { useEffect, useState } from 'react';
import { getCrawlStatus } from '../../services/api';
import './CrawlResultModal.css';

interface Violation {
  type: string;
  severity: string;
  field: string;
  message: string;
}

interface CrawlResultData {
  site_id: number;
  url: string;
  status: string;
  violations: Violation[];
  alerts_sent: boolean;
  error: string | null;
}

interface CrawlResultModalProps {
  jobId: string;
  onClose: () => void;
}

const CrawlResultModal = ({ jobId, onClose }: CrawlResultModalProps) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [resultData, setResultData] = useState<CrawlResultData | null>(null);

  useEffect(() => {
    const fetchResult = async () => {
      try {
        const statusResponse = await getCrawlStatus(jobId);
        
        if (statusResponse.status === 'completed' && statusResponse.result) {
          setResultData(statusResponse.result as CrawlResultData);
        } else if (statusResponse.status === 'failed') {
          setError('クロールに失敗しました');
        } else {
          setError('クロール結果がまだ利用できません');
        }
      } catch (err) {
        setError('結果の取得に失敗しました');
      } finally {
        setLoading(false);
      }
    };

    fetchResult();
  }, [jobId]);

  const getSeverityClass = (severity: string) => {
    const severityMap: Record<string, string> = {
      low: 'severity-low',
      medium: 'severity-medium',
      high: 'severity-high',
      critical: 'severity-critical'
    };
    return severityMap[severity] || 'severity-low';
  };

  const getSeverityLabel = (severity: string) => {
    const labels: Record<string, string> = {
      low: '低',
      medium: '中',
      high: '高',
      critical: '重大'
    };
    return labels[severity] || severity;
  };

  const getStatusLabel = (status: string) => {
    const labels: Record<string, string> = {
      success: '成功',
      crawl_failed: 'クロール失敗',
      error: 'エラー'
    };
    return labels[status] || status;
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>クロール結果</h2>
          <button className="close-button" onClick={onClose}>
            ×
          </button>
        </div>

        <div className="modal-body">
          {loading && (
            <div className="loading-state">
              <span className="spinner">⟳</span>
              <p>結果を読み込み中...</p>
            </div>
          )}

          {error && (
            <div className="error-state">
              <p>{error}</p>
            </div>
          )}

          {!loading && !error && resultData && (
            <div className="result-content">
              <div className="result-summary">
                <div className="summary-item">
                  <span className="label">URL:</span>
                  <span className="value">{resultData.url}</span>
                </div>
                <div className="summary-item">
                  <span className="label">ステータス:</span>
                  <span className={`status-badge status-${resultData.status}`}>
                    {getStatusLabel(resultData.status)}
                  </span>
                </div>
                {resultData.error && (
                  <div className="summary-item error-message">
                    <span className="label">エラー:</span>
                    <span className="value">{resultData.error}</span>
                  </div>
                )}
              </div>

              {resultData.violations && resultData.violations.length > 0 ? (
                <div className="violations-section">
                  <h3>検出された違反 ({resultData.violations.length}件)</h3>
                  <div className="violations-list">
                    {resultData.violations.map((violation, index) => (
                      <div key={index} className="violation-item">
                        <div className="violation-header">
                          <span className={`severity-badge ${getSeverityClass(violation.severity)}`}>
                            {getSeverityLabel(violation.severity)}
                          </span>
                          <span className="violation-type">{violation.type}</span>
                        </div>
                        <div className="violation-details">
                          <div className="detail-row">
                            <span className="detail-label">フィールド:</span>
                            <span className="detail-value">{violation.field}</span>
                          </div>
                          <div className="detail-row">
                            <span className="detail-label">メッセージ:</span>
                            <span className="detail-value">{violation.message}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                  {resultData.alerts_sent && (
                    <div className="alerts-info">
                      <span className="info-icon">ℹ</span>
                      アラートが送信されました
                    </div>
                  )}
                </div>
              ) : (
                <div className="no-violations">
                  <span className="success-icon">✓</span>
                  <p>違反は検出されませんでした</p>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="close-footer-button" onClick={onClose}>
            閉じる
          </button>
        </div>
      </div>
    </div>
  );
};

export default CrawlResultModal;
