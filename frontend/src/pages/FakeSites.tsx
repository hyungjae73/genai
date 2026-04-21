import { useEffect, useState } from 'react';
import { getAlerts, type Alert } from '../services/api';
import { useAutoRefresh } from '../hooks/useAutoRefresh';
import { Badge } from '../components/ui/Badge/Badge';
import { Table, type TableColumn } from '../components/ui/Table/Table';
import { HelpButton } from '../components/ui/HelpButton/HelpButton';
import './FakeSites.css';

type AlertRecord = Alert & Record<string, unknown>;

const columns: TableColumn<AlertRecord>[] = [
  {
    key: 'alert_type',
    header: '種別',
    render: () => (
      <Badge variant="danger" size="sm">偽サイト</Badge>
    ),
  },
  {
    key: 'fake_domain',
    header: '偽ドメイン',
    render: (alert) => <>{alert.fake_domain ?? ''}</>,
  },
  {
    key: 'legitimate_domain',
    header: '正規ドメイン',
    render: (alert) => <>{alert.legitimate_domain ?? ''}</>,
  },
  {
    key: 'domain_similarity_score',
    header: 'ドメイン類似度',
    render: (alert) => <>{alert.domain_similarity_score !== undefined ? String(alert.domain_similarity_score) : ''}</>,
  },
  {
    key: 'content_similarity_score',
    header: 'コンテンツ類似度',
    render: (alert) => <>{alert.content_similarity_score !== undefined ? String(alert.content_similarity_score) : ''}</>,
  },
  {
    key: 'created_at',
    header: '検知日時',
    render: (alert) => <>{new Date(alert.created_at).toLocaleString()}</>,
  },
  {
    key: 'is_resolved',
    header: 'ステータス',
    render: (alert) => (
      <Badge variant={alert.is_resolved ? 'success' : 'warning'} size="sm">
        {alert.is_resolved ? '解決済み' : '未解決'}
      </Badge>
    ),
  },
];

const FakeSites = () => {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchFakeSiteAlerts = async () => {
    try {
      setLoading(true);
      const data = await getAlerts();
      setAlerts(data.filter(a => a.alert_type === 'fake_site'));
      setError(null);
    } catch (err) {
      setError('偽サイトアラートの取得に失敗しました');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFakeSiteAlerts();
  }, []);

  // Auto-refresh every 30 seconds
  useAutoRefresh(fetchFakeSiteAlerts, 30000);

  if (loading) {
    return <div className="loading">読み込み中...</div>;
  }

  if (error) {
    return <div className="error">{error}</div>;
  }

  return (
    <div className="fake-sites">
      <div className="page-header">
        <h1>偽サイト検知 <HelpButton title="このページの使い方">
          <div className="help-content">
            <h3>できること</h3>
            <ul>
              <li>検知された偽サイトの一覧確認</li>
              <li>偽ドメインと正規ドメインの類似度を比較</li>
              <li>対応状況（未解決/解決済み）の追跡</li>
            </ul>

            <h3>スコアの見方</h3>
            <ul>
              <li><strong>ドメイン類似度</strong> — ドメイン名の文字列の類似度（0〜1）</li>
              <li><strong>コンテンツ類似度</strong> — ページ内容の類似度（0〜1）</li>
            </ul>
            <p>1に近いほど類似度が高く、偽サイトの可能性が高いことを示します。</p>

            <div className="help-tip">データは30秒ごとに自動更新されます。</div>
          </div>
        </HelpButton></h1>
      </div>

      <Table<AlertRecord>
        columns={columns}
        data={alerts as AlertRecord[]}
        mobileLayout="card"
        emptyMessage="偽サイトアラートはありません"
        aria-label="偽サイト検知一覧"
      />
    </div>
  );
};

export default FakeSites;
