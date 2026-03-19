import { useState, useEffect } from 'react';
import { getSiteAlerts } from '../../../services/api';
import type { Alert } from '../../../services/api';

export interface AlertTabProps {
  siteId: number;
  customerName: string;
}

type SeverityLevel = 'low' | 'medium' | 'high' | 'critical';
type FilterStatus = 'all' | 'resolved' | 'unresolved';

/**
 * Gets the CSS class for a severity badge.
 * Pure function for testing purposes.
 */
export const getSeverityBadgeClass = (severity: SeverityLevel): string => {
  const classMap: Record<SeverityLevel, string> = {
    low: 'severity-badge severity-low',
    medium: 'severity-badge severity-medium',
    high: 'severity-badge severity-high',
    critical: 'severity-badge severity-critical',
  };
  return classMap[severity];
};

/**
 * Gets the Japanese label for a severity level.
 * Pure function for testing purposes.
 */
export const getSeverityLabel = (severity: SeverityLevel): string => {
  const labelMap: Record<SeverityLevel, string> = {
    low: '低',
    medium: '中',
    high: '高',
    critical: '緊急',
  };
  return labelMap[severity];
};

/**
 * Filters alerts by resolution status.
 * Pure function for testing purposes.
 */
export const filterAlertsByStatus = (alerts: Alert[], filterStatus: FilterStatus): Alert[] => {
  if (filterStatus === 'all') {
    return alerts;
  }
  const isResolved = filterStatus === 'resolved';
  return alerts.filter(alert => alert.is_resolved === isResolved);
};

const AlertTab = ({ siteId, customerName }: AlertTabProps) => {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<FilterStatus>('all');

  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        setLoading(true);
        setError(null);
        
        const alertsData = await getSiteAlerts(siteId);
        setAlerts(alertsData);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'アラートの取得に失敗しました');
      } finally {
        setLoading(false);
      }
    };

    fetchAlerts();
  }, [siteId]);

  const filteredAlerts = filterAlertsByStatus(alerts, filterStatus);

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

  if (alerts.length === 0) {
    return (
      <div className="tab-empty">
        <p>アラートがありません</p>
      </div>
    );
  }

  return (
    <div className="alert-tab">
      <div className="alert-filters">
        <label>ステータス:</label>
        <select 
          value={filterStatus} 
          onChange={(e) => setFilterStatus(e.target.value as FilterStatus)}
          className="filter-select"
        >
          <option value="all">すべて</option>
          <option value="unresolved">未解決</option>
          <option value="resolved">解決済み</option>
        </select>
      </div>

      {filteredAlerts.length === 0 ? (
        <div className="tab-empty">
          <p>該当するアラートがありません</p>
        </div>
      ) : (
        <div className="alert-list">
          {filteredAlerts.map((alert) => (
            <div key={alert.id} className="alert-item">
              <div className="alert-header">
                <span className={getSeverityBadgeClass(alert.severity)}>
                  {getSeverityLabel(alert.severity)}
                </span>
                <span className={`status-badge ${alert.is_resolved ? 'resolved' : 'unresolved'}`}>
                  {alert.is_resolved ? '解決済み' : '未解決'}
                </span>
                <span className="alert-date">
                  {new Date(alert.created_at).toLocaleString('ja-JP')}
                </span>
              </div>

              <div className="alert-details">
                <div className="alert-info">
                  <div className="info-row">
                    <span className="info-label">顧客名:</span>
                    <span className="info-value">{customerName}</span>
                  </div>
                  <div className="info-row">
                    <span className="info-label">商品ページ:</span>
                    <span className="info-value">{alert.site_name}</span>
                  </div>
                  <div className="info-row">
                    <span className="info-label">違反タイプ:</span>
                    <span className="info-value">{alert.violation_type}</span>
                  </div>
                </div>

                <div className="alert-message">
                  <p>{alert.message}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default AlertTab;
