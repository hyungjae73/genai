import React from 'react';
import { Card } from '../components/ui/Card/Card';
import { Badge } from '../components/ui/Badge/Badge';
import { useReviewStats } from '../hooks/queries/useReviews';
import './ReviewDashboard.css';

const STATUS_LABELS: Record<string, string> = {
  pending: '未審査',
  in_review: '審査中',
  escalated: 'エスカレーション',
  approved: '承認済み',
  rejected: '却下済み',
};

const PRIORITY_LABELS: Record<string, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
};

const TYPE_LABELS: Record<string, string> = {
  violation: '契約違反',
  dark_pattern: 'ダークパターン',
  fake_site: '偽サイト',
};

const ReviewDashboard: React.FC = () => {
  const { data: stats, isLoading: loading, error: queryError } = useReviewStats();
  const error = queryError ? '統計情報の取得に失敗しました' : null;

  if (loading) return <div className="review-dashboard-loading" aria-live="polite">読み込み中...</div>;
  if (error) return <div className="review-dashboard-error" role="alert">{error}</div>;
  if (!stats) return null;

  return (
    <div className="review-dashboard-page">
      <h1 className="review-dashboard-title">審査ダッシュボード</h1>

      {/* ステータス別件数 */}
      <section aria-labelledby="status-section-title">
        <h2 id="status-section-title" className="review-dashboard-section-title">ステータス別件数</h2>
        <div className="review-dashboard-cards">
          {Object.entries(STATUS_LABELS).map(([key, label]) => (
            <Card key={key}>
              <div className="review-dashboard-stat-card">
                <span className="review-dashboard-stat-label">{label}</span>
                <span className="review-dashboard-stat-value">{stats.by_status[key as keyof typeof stats.by_status] ?? 0}</span>
              </div>
            </Card>
          ))}
        </div>
      </section>

      {/* 優先度別 未審査件数 */}
      <section aria-labelledby="priority-section-title">
        <h2 id="priority-section-title" className="review-dashboard-section-title">優先度別 未審査件数</h2>
        <div className="review-dashboard-cards">
          {Object.entries(PRIORITY_LABELS).map(([key, label]) => (
            <Card key={key}>
              <div className="review-dashboard-stat-card">
                <Badge variant={key === 'critical' ? 'danger' : key === 'high' ? 'warning' : key === 'medium' ? 'info' : 'neutral'}>
                  {label}
                </Badge>
                <span className="review-dashboard-stat-value">{stats.by_priority[key as keyof typeof stats.by_priority] ?? 0}</span>
              </div>
            </Card>
          ))}
        </div>
      </section>

      {/* 種別別 未審査件数 */}
      <section aria-labelledby="type-section-title">
        <h2 id="type-section-title" className="review-dashboard-section-title">種別別 未審査件数</h2>
        <div className="review-dashboard-cards">
          {Object.entries(TYPE_LABELS).map(([key, label]) => (
            <Card key={key}>
              <div className="review-dashboard-stat-card">
                <span className="review-dashboard-stat-label">{label}</span>
                <span className="review-dashboard-stat-value">{stats.by_review_type[key as keyof typeof stats.by_review_type] ?? 0}</span>
              </div>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
};

export default ReviewDashboard;
