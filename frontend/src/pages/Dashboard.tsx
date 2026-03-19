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
      <h1>統計ダッシュボード</h1>
      
      <div className="stats-grid">
        <div className="stat-card">
          <h3>監視サイト数</h3>
          <p className="stat-value">{statistics.total_sites}</p>
          <p className="stat-label">アクティブ: {statistics.active_sites}</p>
        </div>
        
        <div className="stat-card">
          <h3>違反数</h3>
          <p className="stat-value">{statistics.total_violations}</p>
          <p className="stat-label">重大: {statistics.high_severity_violations}</p>
        </div>
        
        <div className="stat-card">
          <h3>成功率</h3>
          <p className="stat-value">{statistics.success_rate.toFixed(1)}%</p>
        </div>
        
        <div className="stat-card">
          <h3>最終クロール</h3>
          <p className="stat-value">
            {statistics.last_crawl 
              ? new Date(statistics.last_crawl).toLocaleString('ja-JP')
              : '未実施'}
          </p>
        </div>
      </div>

      {history.length > 0 && (
        <div className="chart-container">
          <Line options={chartOptions} data={chartData} />
        </div>
      )}
    </div>
  );
};

export default Dashboard;
