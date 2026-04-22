import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card } from '../components/ui/Card/Card';
import { Badge } from '../components/ui/Badge/Badge';
import { Button } from '../components/ui/Button/Button';
import { useAuth } from '../contexts/AuthContext';
import { useReviewDetail, useAssignReviewer, useDecidePrimary, useDecideSecondary } from '../hooks/queries/useReviews';
import type { ReviewDecisionType } from '../types/review';
import './ReviewDetail.css';

const DECISION_OPTIONS_PRIMARY: { value: ReviewDecisionType; label: string }[] = [
  { value: 'approved', label: '承認' },
  { value: 'rejected', label: '却下' },
  { value: 'escalated', label: 'エスカレーション' },
];

const DECISION_OPTIONS_SECONDARY: { value: ReviewDecisionType; label: string }[] = [
  { value: 'approved', label: '最終承認' },
  { value: 'rejected', label: '最終却下' },
];

const ReviewDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const reviewId = Number(id);

  const { data: detail, isLoading: loading, error: queryError } = useReviewDetail(reviewId);
  const error = queryError ? '審査案件の取得に失敗しました' : null;

  const assignReviewerMutation = useAssignReviewer();
  const decidePrimaryMutation = useDecidePrimary();
  const decideSecondaryMutation = useDecideSecondary();

  // 判定フォーム
  const [decision, setDecision] = useState<ReviewDecisionType>('approved');
  const [comment, setComment] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const handleAssign = async () => {
    if (!user) return;
    setSubmitting(true);
    setFormError(null);
    try {
      await assignReviewerMutation.mutateAsync({ reviewId, body: { reviewer_id: user.id } });
    } catch {
      setFormError('担当者割り当てに失敗しました');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDecide = async (stage: 'primary' | 'secondary') => {
    if (!comment.trim()) {
      setFormError('コメントを入力してください');
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      if (stage === 'primary') {
        await decidePrimaryMutation.mutateAsync({ reviewId, body: { decision, comment } });
      } else {
        await decideSecondaryMutation.mutateAsync({ reviewId, body: { decision, comment } });
      }
      setComment('');
    } catch {
      setFormError('判定の送信に失敗しました');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <div className="review-detail-loading" aria-live="polite">読み込み中...</div>;
  if (error) return <div className="review-detail-error" role="alert">{error}</div>;
  if (!detail) return null;

  const { review_item, alert, violation, dark_pattern, fake_site, site, decisions } = detail;
  const status = review_item.status;
  const isAdmin = user?.role === 'admin';

  return (
    <div className="review-detail-page">
      <div className="review-detail-header">
        <Button variant="ghost" size="sm" onClick={() => navigate('/reviews')}>← 一覧に戻る</Button>
        <h1 className="review-detail-title">審査案件 #{review_item.id}</h1>
        <Badge variant={status === 'approved' ? 'success' : status === 'rejected' ? 'neutral' : status === 'escalated' ? 'danger' : status === 'in_review' ? 'info' : 'warning'}>
          {status}
        </Badge>
      </div>

      {/* 基本情報 */}
      <Card>
        <h2 className="review-detail-section-title">基本情報</h2>
        <dl className="review-detail-dl">
          <dt>種別</dt><dd>{review_item.review_type}</dd>
          <dt>優先度</dt><dd><Badge variant={review_item.priority === 'critical' ? 'danger' : review_item.priority === 'high' ? 'warning' : 'info'}>{review_item.priority.toUpperCase()}</Badge></dd>
          <dt>担当者</dt><dd>{review_item.assigned_to ?? '未割り当て'}</dd>
          <dt>作成日時</dt><dd>{new Date(review_item.created_at).toLocaleString('ja-JP')}</dd>
        </dl>
      </Card>

      {/* サイト情報 */}
      {site && (
        <Card>
          <h2 className="review-detail-section-title">サイト情報</h2>
          <dl className="review-detail-dl">
            <dt>サイト名</dt><dd>{site.name}</dd>
            <dt>URL</dt><dd><a href={site.url} target="_blank" rel="noopener noreferrer">{site.url}</a></dd>
          </dl>
        </Card>
      )}

      {/* Alert 詳細 */}
      {alert && (
        <Card>
          <h2 className="review-detail-section-title">アラート詳細</h2>
          <dl className="review-detail-dl">
            <dt>種別</dt><dd>{alert.alert_type}</dd>
            <dt>重大度</dt><dd>{alert.severity}</dd>
            <dt>メッセージ</dt><dd>{alert.message}</dd>
            <dt>検出日時</dt><dd>{new Date(alert.created_at).toLocaleString('ja-JP')}</dd>
          </dl>
        </Card>
      )}

      {/* 違反詳細 */}
      {violation && (
        <Card>
          <h2 className="review-detail-section-title">違反詳細</h2>
          <dl className="review-detail-dl">
            <dt>違反種別</dt><dd>{violation.violation_type}</dd>
            <dt>期待値</dt><dd><pre className="review-detail-pre">{JSON.stringify(violation.expected_value, null, 2)}</pre></dd>
            <dt>実際値</dt><dd><pre className="review-detail-pre">{JSON.stringify(violation.actual_value, null, 2)}</pre></dd>
          </dl>
        </Card>
      )}

      {/* ダークパターン詳細 */}
      {dark_pattern && (
        <Card>
          <h2 className="review-detail-section-title">ダークパターン検出結果</h2>
          <dl className="review-detail-dl">
            <dt>スコア</dt><dd>{dark_pattern.dark_pattern_score?.toFixed(3) ?? '-'}</dd>
            <dt>検出種別</dt><dd>{dark_pattern.dark_pattern_types ? JSON.stringify(dark_pattern.dark_pattern_types) : '-'}</dd>
          </dl>
        </Card>
      )}

      {/* 偽サイト詳細 */}
      {fake_site && (
        <Card>
          <h2 className="review-detail-section-title">偽サイト情報</h2>
          <dl className="review-detail-dl">
            <dt>偽ドメイン</dt><dd>{fake_site.fake_domain ?? '-'}</dd>
            <dt>ドメイン類似度</dt><dd>{fake_site.domain_similarity_score?.toFixed(3) ?? '-'}</dd>
            <dt>コンテンツ類似度</dt><dd>{fake_site.content_similarity_score?.toFixed(3) ?? '-'}</dd>
          </dl>
        </Card>
      )}

      {/* 判定履歴 */}
      {decisions.length > 0 && (
        <Card>
          <h2 className="review-detail-section-title">判定履歴</h2>
          <ul className="review-detail-decisions">
            {decisions.map((d) => (
              <li key={d.id} className="review-detail-decision-item">
                <div className="review-detail-decision-meta">
                  <Badge variant={d.decision === 'approved' ? 'success' : d.decision === 'rejected' ? 'neutral' : 'warning'}>
                    {d.decision}
                  </Badge>
                  <span className="review-detail-decision-stage">{d.review_stage === 'primary' ? '一次審査' : '二次審査'}</span>
                  <span className="review-detail-decision-date">{new Date(d.decided_at).toLocaleString('ja-JP')}</span>
                </div>
                <p className="review-detail-decision-comment">{d.comment}</p>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {/* アクションフォーム */}
      <Card>
        <h2 className="review-detail-section-title">審査アクション</h2>

        {formError && <div className="review-detail-form-error" role="alert">{formError}</div>}

        {/* 担当者割り当て (pending 状態) */}
        {status === 'pending' && (
          <div className="review-detail-action">
            <p>この案件を自分に割り当てて審査を開始します。</p>
            <Button variant="primary" size="md" onClick={handleAssign} disabled={submitting}>
              {submitting ? '処理中...' : '担当者として割り当て'}
            </Button>
          </div>
        )}

        {/* 一次審査判定 (in_review 状態) */}
        {status === 'in_review' && (
          <div className="review-detail-action">
            <div className="review-detail-form-row">
              <label htmlFor="primary-decision" className="review-detail-label">判定</label>
              <select
                id="primary-decision"
                className="review-detail-select"
                value={decision}
                onChange={(e) => setDecision(e.target.value as ReviewDecisionType)}
              >
                {DECISION_OPTIONS_PRIMARY.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
            <div className="review-detail-form-row">
              <label htmlFor="primary-comment" className="review-detail-label">コメント <span aria-hidden="true">*</span></label>
              <textarea
                id="primary-comment"
                className="review-detail-textarea"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                rows={3}
                placeholder="判定理由を入力してください"
                required
              />
            </div>
            <Button variant="primary" size="md" onClick={() => handleDecide('primary')} disabled={submitting}>
              {submitting ? '処理中...' : '一次審査判定を送信'}
            </Button>
          </div>
        )}

        {/* 二次審査判定 (escalated 状態、admin のみ) */}
        {status === 'escalated' && isAdmin && (
          <div className="review-detail-action">
            <div className="review-detail-form-row">
              <label htmlFor="secondary-decision" className="review-detail-label">最終判定</label>
              <select
                id="secondary-decision"
                className="review-detail-select"
                value={decision}
                onChange={(e) => setDecision(e.target.value as ReviewDecisionType)}
              >
                {DECISION_OPTIONS_SECONDARY.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
            <div className="review-detail-form-row">
              <label htmlFor="secondary-comment" className="review-detail-label">コメント <span aria-hidden="true">*</span></label>
              <textarea
                id="secondary-comment"
                className="review-detail-textarea"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                rows={3}
                placeholder="最終判定理由を入力してください"
                required
              />
            </div>
            <Button variant="primary" size="md" onClick={() => handleDecide('secondary')} disabled={submitting}>
              {submitting ? '処理中...' : '最終判定を送信'}
            </Button>
          </div>
        )}

        {(status === 'approved' || status === 'rejected') && (
          <p className="review-detail-final">この案件は最終判定済みです。</p>
        )}
      </Card>
    </div>
  );
};

export default ReviewDetailPage;
