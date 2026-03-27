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
        <h1>偽サイト検知 <HelpButton title="偽サイト検知の使い方">
          <div className="help-content">
            <h3>ユーザーストーリー</h3>
            <p>偽サイトの検知状況を一覧で確認し、対応状況を追跡したい</p>

            <h3>偽ドメイン・正規ドメイン・類似度スコアの見方</h3>
            <ul>
              <li><strong>偽ドメイン</strong>: 検知された偽サイトのドメイン名です</li>
              <li><strong>正規ドメイン</strong>: 偽サイトが模倣している正規サイトのドメイン名です</li>
              <li><strong>類似度スコア</strong>: 0〜1の数値で、1に近いほど類似度が高いことを示します</li>
            </ul>

            <h3>ドメイン類似度とコンテンツ類似度の違い</h3>
            <ul>
              <li><strong>ドメイン類似度</strong>: ドメイン名の文字列がどれだけ似ているかを示します</li>
              <li><strong>コンテンツ類似度</strong>: ページの内容がどれだけ似ているかを示します</li>
            </ul>

            <h3>ステータス</h3>
            <ul>
              <li><strong>未解決</strong>: まだ対応が完了していないアラートです</li>
              <li><strong>解決済み</strong>: 対応が完了したアラートです</li>
            </ul>

            <h3>データの自動更新</h3>
            <p>データは30秒ごとに自動更新されます。手動でのリロードは不要です。</p>
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
