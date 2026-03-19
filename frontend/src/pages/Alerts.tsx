import { useEffect, useState } from 'react';
import { getAlerts, type Alert } from '../services/api';
import { useAutoRefresh } from '../hooks/useAutoRefresh';

const Alerts = () => {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [severityFilter, setSeverityFilter] = useState<string>('all');

  const fetchAlerts = async () => {
    try {
      setLoading(true);
      const data = await getAlerts();
      setAlerts(data);
      setError(null);
    } catch (err) {
      setError('アラート一覧の取得に失敗しました');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
  }, []);

  // Auto-refresh every 30 seconds
  useAutoRefresh(fetchAlerts, 30000);

  const filteredAlerts = alerts.filter(alert => {
    return severityFilter === 'all' || alert.severity === severityFilter;
  });

  const getSeverityBadge = (severity: string) => {
    const severityMap: Record<string, { label: string; className: string }> = {
      low: { label: '低', className: 'severity-low' },
      medium: { label: '中', className: 'severity-medium' },
      high: { label: '高', className: 'severity-high' },
      critical: { label: '緊急', className: 'severity-critical' },
    };
    const severityInfo = severityMap[severity] || { label: severity, className: '' };
    return <span className={`severity-badge ${severityInfo.className}`}>{severityInfo.label}</span>;
  };

  if (loading) {
    return <div className="loading">読み込み中...</div>;
  }

  if (error) {
    return <div className="error">{error}</div>;
  }

  return (
    <div className="alerts">
      <h1>アラート一覧</h1>
      
      <div className="filters">
        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
          className="severity-filter"
        >
          <option value="all">すべての重要度</option>
          <option value="critical">緊急</option>
          <option value="high">高</option>
          <option value="medium">中</option>
          <option value="low">低</option>
        </select>
      </div>

      <div className="alerts-list">
        {filteredAlerts.map(alert => (
          <div key={alert.id} className={`alert-card ${alert.is_resolved ? 'resolved' : ''}`}>
            <div className="alert-header">
              {getSeverityBadge(alert.severity)}
              <span className="alert-time">{new Date(alert.created_at).toLocaleString()}</span>
            </div>
            <div className="alert-body">
              <h3>{alert.site_name}</h3>
              <p className="alert-type">{alert.violation_type}</p>
              <p className="alert-message">{alert.message}</p>
            </div>
            {alert.is_resolved && (
              <div className="alert-footer">
                <span className="resolved-badge">解決済み</span>
              </div>
            )}
          </div>
        ))}
        
        {filteredAlerts.length === 0 && (
          <div className="no-data">該当するアラートがありません</div>
        )}
      </div>
    </div>
  );
};

export default Alerts;
