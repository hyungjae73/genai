import { useEffect, useState } from 'react';
import { getAlerts, type Alert } from '../services/api';
import { useAutoRefresh } from '../hooks/useAutoRefresh';
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
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [alertTypeFilter, setAlertTypeFilter] = useState<string>('all');

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
        <h1>アラート一覧 <HelpButton title="アラート一覧の使い方">
          <div className="help-content">
            <h3>ユーザーストーリー</h3>
            <p>検出された問題を重要度別に確認し、対応の優先順位を判断したい</p>

            <h3>重要度フィルター</h3>
            <p>重要度フィルター（緊急/高/中/低）で、対応が必要なアラートを絞り込めます。</p>

            <h3>種別フィルター</h3>
            <p>種別フィルター（契約違反/偽サイト）で、アラートの種類ごとに表示を切り替えられます。</p>

            <h3>カードのボーダー色</h3>
            <p>各アラートカードの左ボーダー色が重要度を示します。赤は緊急・高、黄色は中、青は低を表します。</p>

            <h3>TakeDown対応バナー</h3>
            <p>偽サイトアラートにはTakeDown対応バナーが表示されます。偽ドメインや類似度スコアを確認し、対応を進めてください。</p>

            <h3>解決済みアラート</h3>
            <p>解決済みアラートは半透明で表示されます。対応完了したアラートを視覚的に区別できます。</p>

            <h3>重要度の詳細</h3>
            <div className="severity-help">
              <div className="severity-help__item">
                <div className="severity-help__header">
                  <Badge variant="danger" size="sm">緊急</Badge>
                  <span className="severity-help__level">Critical</span>
                </div>
                <p className="severity-help__desc">
                  即時対応が必要な重大な問題です。偽サイトの検知確定や、価格がゼロになるなど、
                  顧客に直接的な被害が発生する可能性がある場合に発行されます。
                </p>
                <ul className="severity-help__examples">
                  <li>偽サイト検知（確定）</li>
                  <li>価格ゼロ検出（商品が無料表示になっている）</li>
                </ul>
              </div>

              <div className="severity-help__item">
                <div className="severity-help__header">
                  <Badge variant="danger" size="sm">高</Badge>
                  <span className="severity-help__level">High</span>
                </div>
                <p className="severity-help__desc">
                  契約条件との重要な不一致が検出された場合に発行されます。
                  早急な確認と対応が推奨されます。
                </p>
                <ul className="severity-help__examples">
                  <li>契約価格との不一致</li>
                  <li>必須決済方法の欠落</li>
                  <li>サブスクリプション条件の違反</li>
                  <li>大幅な価格変動の検出</li>
                </ul>
              </div>

              <div className="severity-help__item">
                <div className="severity-help__header">
                  <Badge variant="warning" size="sm">中</Badge>
                  <span className="severity-help__level">Medium</span>
                </div>
                <p className="severity-help__desc">
                  注意が必要ですが、即時対応は不要な問題です。
                  次回の定期確認時に対応を検討してください。
                </p>
                <ul className="severity-help__examples">
                  <li>許可外の決済方法が表示されている</li>
                  <li>手数料の不一致</li>
                  <li>契約期間の表示ずれ</li>
                  <li>解約ポリシーの不一致</li>
                </ul>
              </div>

              <div className="severity-help__item">
                <div className="severity-help__header">
                  <Badge variant="info" size="sm">低</Badge>
                  <span className="severity-help__level">Low</span>
                </div>
                <p className="severity-help__desc">
                  軽微な問題や情報提供レベルの通知です。
                  対応の優先度は低く、必要に応じて確認してください。
                </p>
                <ul className="severity-help__examples">
                  <li>軽微な表示の差異</li>
                  <li>情報提供レベルの変更通知</li>
                </ul>
              </div>
            </div>
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
