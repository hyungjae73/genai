import { useState } from 'react';
import type { Alert } from '../services/api';
import { useAlerts } from '../hooks/queries/useAlerts';
import { Card } from '../components/ui/Card/Card';
import { Badge } from '../components/ui/Badge/Badge';
import { Select } from '../components/ui/Select/Select';
import { HelpButton } from '../components/ui/HelpButton/HelpButton';
import './Alerts.css';

const severityVariantMap: Record<string, { label: string; variant: 'danger' | 'warning' | 'info' | 'neutral' }> = {
  critical: { label: '緊急', variant: 'danger' },
  high: { label: '高', variant: 'danger' },
  medium: { label: '中', variant: 'warning' },
  low: { label: '低', variant: 'info' },
};

const severityFilterOptions = [
  { value: 'all', label: 'すべての重要度' },
  { value: 'critical', label: '緊急' },
  { value: 'high', label: '高' },
  { value: 'medium', label: '中' },
  { value: 'low', label: '低' },
];

const alertTypeFilterOptions = [
  { value: 'all', label: 'すべて' },
  { value: 'violation', label: '契約違反' },
  { value: 'fake_site', label: '偽サイト' },
];

const Alerts = () => {
  const { data: alerts = [], isLoading: loading, error: queryError } = useAlerts();
  const error = queryError ? 'アラート一覧の取得に失敗しました' : null;
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [alertTypeFilter, setAlertTypeFilter] = useState<string>('all');

  const filteredAlerts = alerts.filter(alert => {
    const matchesSeverity = severityFilter === 'all' || alert.severity === severityFilter;
    const matchesAlertType =
      alertTypeFilter === 'all' ||
      (alertTypeFilter === 'fake_site' && alert.alert_type === 'fake_site') ||
      (alertTypeFilter === 'violation' && alert.alert_type !== 'fake_site');
    return matchesSeverity && matchesAlertType;
  });

  const getSeverityBadge = (severity: string) => {
    const info = severityVariantMap[severity] || { label: severity, variant: 'neutral' as const };
    return (
      <Badge variant={info.variant} size="sm">
        <span className={`severity-badge severity-${severity}`}>{info.label}</span>
      </Badge>
    );
  };

  if (loading) {
    return <div className="loading">読み込み中...</div>;
  }

  if (error) {
    return <div className="error">{error}</div>;
  }

  return (
    <div className="alerts">
      <div className="page-header">
        <h1>アラート一覧 <HelpButton title="このページの使い方">
          <div className="help-content">
            <h3>できること</h3>
            <ul>
              <li>検出された違反・偽サイトアラートを重要度別に確認</li>
              <li>重要度（緊急/高/中/低）と種別（契約違反/偽サイト）でフィルタリング</li>
              <li>解決済みアラートの確認（半透明表示）</li>
            </ul>

            <h3>カードの見方</h3>
            <p>左ボーダー色が重要度を示します: 赤=緊急・高、黄=中、青=低。偽サイトアラートにはTakeDown対応バナーが表示されます。</p>

            <h3>重要度の目安</h3>
            <ul>
              <li><strong>緊急</strong> — 即時対応（偽サイト確定、価格ゼロ等）</li>
              <li><strong>高</strong> — 早急な確認（価格不一致、必須決済方法欠落等）</li>
              <li><strong>中</strong> — 次回確認時に対応（手数料不一致、解約ポリシーずれ等）</li>
              <li><strong>低</strong> — 必要に応じて確認（軽微な表示差異等）</li>
            </ul>
          </div>
        </HelpButton></h1>
      </div>

      <div className="alerts-filters">
        <Select
          label="重要度"
          value={severityFilter}
          onChange={setSeverityFilter}
          options={severityFilterOptions}
          aria-label="重要度フィルター"
        />
        <Select
          label="種別"
          value={alertTypeFilter}
          onChange={setAlertTypeFilter}
          options={alertTypeFilterOptions}
          aria-label="種別フィルター"
        />
      </div>

      <div className="alerts-list">
        {filteredAlerts.map(alert => (
          <Card
            key={alert.id}
            hoverable
            className={`alert-card ${alert.is_resolved ? 'resolved' : ''}`}
            borderLeft={
              alert.severity === 'critical' || alert.severity === 'high'
                ? 'danger'
                : alert.severity === 'medium'
                  ? 'warning'
                  : 'info'
            }
          >
            <div className="alert-header">
              <div className="alert-header__badges">
                {getSeverityBadge(alert.severity)}
                {alert.alert_type === 'fake_site' ? (
                  <Badge variant="danger" size="sm">
                    <span className="alert-type-badge fake-site">偽サイト</span>
                  </Badge>
                ) : (
                  <Badge variant="neutral" size="sm">
                    <span className="alert-type-badge violation">契約違反</span>
                  </Badge>
                )}
              </div>
              <span className="alert-time">{new Date(alert.created_at).toLocaleString()}</span>
            </div>
            {alert.alert_type === 'fake_site' && !alert.is_resolved && (
              <div className="takedown-banner">
                <p>TakeDown対応が必要</p>
                <p>偽ドメイン: {alert.fake_domain}</p>
                <p>ドメイン類似度: {alert.domain_similarity_score}</p>
                <p>コンテンツ類似度: {alert.content_similarity_score}</p>
              </div>
            )}
            <div className="alert-body">
              <h3>{alert.site_name}</h3>
              <p className="alert-type">{alert.violation_type}</p>
              <p className="alert-message">{alert.message}</p>
            </div>
            {alert.is_resolved && (
              <div className="alert-footer">
                <Badge variant="success" size="sm">解決済み</Badge>
              </div>
            )}
          </Card>
        ))}

        {filteredAlerts.length === 0 && (
          <div className="no-data">該当するアラートがありません</div>
        )}
      </div>
    </div>
  );
};

export default Alerts;
