import { useEffect, useState } from 'react';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import type { ChartOptions } from 'chart.js';
import { getStatistics, getMonitoringHistory, type Statistics, type MonitoringHistory } from '../services/api';
import { useAutoRefresh } from '../hooks/useAutoRefresh';
import { Card } from '../components/ui/Card/Card';
import { HelpButton } from '../components/ui/HelpButton/HelpButton';
import './Dashboard.css';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

const Dashboard = () => {
  const [statistics, setStatistics] = useState<Statistics | null>(null);
  const [history, setHistory] = useState<MonitoringHistory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [stats, hist] = await Promise.all([
        getStatistics(),
        getMonitoringHistory(),
      ]);
      setStatistics(stats);
      setHistory(hist);
      setError(null);
    } catch (err) {
      setError('データの取得に失敗しました');
      console.error('Dashboard fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // Auto-refresh every 30 seconds
  useAutoRefresh(fetchData, 30000);

  if (loading) {
    return <div className="loading">読み込み中...</div>;
  }

  if (error) {
    return <div className="error">{error}</div>;
  }

  if (!statistics) {
    return <div className="error">データがありません</div>;
  }

  // Prepare chart data
  const chartData = {
    labels: history.slice(-10).map(h => new Date(h.crawled_at).toLocaleDateString()),
    datasets: [
      {
        label: '違反数',
        data: history.slice(-10).map(h => h.violations_count),
        borderColor: 'rgb(255, 99, 132)',
        backgroundColor: 'rgba(255, 99, 132, 0.5)',
      },
    ],
  };

  const chartOptions: ChartOptions<'line'> = {
    responsive: true,
    plugins: {
      legend: {
        position: 'top',
      },
      title: {
        display: true,
        text: '違反数の推移',
      },
    },
  };

  return (
    <div className="dashboard">
      <div className="page-header">
        <h1>統計ダッシュボード <HelpButton title="統計ダッシュボードの使い方">
          <div className="help-content">
            <h3>ユーザーストーリー</h3>
            <p>監視状況の全体像を把握したい</p>

            <h3>統計カード</h3>
            <ul>
              <li><strong>監視サイト数</strong>: 現在監視中のサイト総数とアクティブなサイト数を表示します</li>
              <li><strong>違反数</strong>: 検出された違反の総数と重大な違反数を表示します</li>
              <li><strong>成功率</strong>: クロールの成功率をパーセンテージで表示します</li>
              <li><strong>偽サイト検知数</strong>: 検知された偽サイトの総数と未解決件数を表示します</li>
            </ul>

            <h3>違反数推移グラフ</h3>
            <p>直近のクロール結果から違反数の推移を折れ線グラフで表示します。トレンドの把握にご活用ください。</p>

            <h3>データの自動更新</h3>
            <p>ダッシュボードのデータは30秒ごとに自動更新されます。手動でのリロードは不要です。</p>
          </div>
        </HelpButton></h1>
      </div>

      <div className="stats-grid">
        <Card hoverable>
          <h3 className="stat-card-title">監視サイト数</h3>
          <p className="stat-value">{statistics.total_sites}</p>
          <p className="stat-label">アクティブ: {statistics.active_sites}</p>
        </Card>

        <Card hoverable>
          <h3 className="stat-card-title">違反数</h3>
          <p className="stat-value">{statistics.total_violations}</p>
          <p className="stat-label">重大: {statistics.high_severity_violations}</p>
        </Card>

        <Card hoverable>
          <h3 className="stat-card-title">成功率</h3>
          <p className="stat-value">{statistics.success_rate.toFixed(1)}%</p>
        </Card>

        <Card hoverable>
          <h3 className="stat-card-title">最終クロール</h3>
          <p className="stat-value">
            {statistics.last_crawl
              ? new Date(statistics.last_crawl).toLocaleString('ja-JP')
              : '未実施'}
          </p>
        </Card>

        <Card hoverable>
          <h3 className="stat-card-title">偽サイト検知</h3>
          <p className="stat-value">{statistics.fake_site_alerts ?? 0}</p>
          <p className="stat-label">未解決: {statistics.unresolved_fake_site_alerts ?? 0}</p>
        </Card>
      </div>

      {history.length > 0 && (
        <div className="chart-container">
          <Line options={chartOptions} data={chartData} />
        </div>
      )}
    </div>
  );
}

export default Dashboard;
