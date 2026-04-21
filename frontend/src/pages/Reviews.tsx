import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card } from '../components/ui/Card/Card';
import { Badge } from '../components/ui/Badge/Badge';
import { Select } from '../components/ui/Select/Select';
import { Button } from '../components/ui/Button/Button';
import { HelpButton } from '../components/ui/HelpButton/HelpButton';
import { fetchReviews, type ReviewListParams } from '../services/api';
import type { ReviewItem, ReviewStatus, ReviewPriority, ReviewType } from '../types/review';
import './Reviews.css';

const STATUS_OPTIONS = [
  { value: '', label: 'すべてのステータス' },
  { value: 'pending', label: '未審査' },
  { value: 'in_review', label: '審査中' },
  { value: 'escalated', label: 'エスカレーション' },
  { value: 'approved', label: '承認済み' },
  { value: 'rejected', label: '却下済み' },
];

const PRIORITY_OPTIONS = [
  { value: '', label: 'すべての優先度' },
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
];

const TYPE_OPTIONS = [
  { value: '', label: 'すべての種別' },
  { value: 'violation', label: '契約違反' },
  { value: 'dark_pattern', label: 'ダークパターン' },
  { value: 'fake_site', label: '偽サイト' },
];

const PAGE_SIZE = 20;

function statusBadgeVariant(status: ReviewStatus): 'warning' | 'info' | 'danger' | 'success' | 'neutral' {
  switch (status) {
    case 'pending': return 'warning';
    case 'in_review': return 'info';
    case 'escalated': return 'danger';
    case 'approved': return 'success';
    case 'rejected': return 'neutral';
  }
}

function priorityBadgeVariant(priority: ReviewPriority): 'danger' | 'warning' | 'info' | 'neutral' {
  switch (priority) {
    case 'critical': return 'danger';
    case 'high': return 'warning';
    case 'medium': return 'info';
    case 'low': return 'neutral';
  }
}

function reviewTypeLabel(type: ReviewType): string {
  switch (type) {
    case 'violation': return '契約違反';
    case 'dark_pattern': return 'ダークパターン';
    case 'fake_site': return '偽サイト';
  }
}

function statusLabel(status: ReviewStatus): string {
  switch (status) {
    case 'pending': return '未審査';
    case 'in_review': return '審査中';
    case 'escalated': return 'エスカレーション';
    case 'approved': return '承認済み';
    case 'rejected': return '却下済み';
  }
}

const Reviews: React.FC = () => {
  const navigate = useNavigate();
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [filterStatus, setFilterStatus] = useState('');
  const [filterPriority, setFilterPriority] = useState('');
  const [filterType, setFilterType] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: ReviewListParams = {
        limit: PAGE_SIZE,
        offset,
      };
      if (filterStatus) params.status = filterStatus;
      if (filterPriority) params.priority = filterPriority;
      if (filterType) params.review_type = filterType;

      const data = await fetchReviews(params);
      setItems(data.items);
      setTotal(data.total);
    } catch {
      setError('審査キューの取得に失敗しました');
    } finally {
      setLoading(false);
    }
  }, [offset, filterStatus, filterPriority, filterType]);

  useEffect(() => {
    load();
  }, [load]);

  const handleFilterChange = () => {
    setOffset(0);
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  return (
    <div className="reviews-page">
      <div className="page-header">
        <h1>審査キュー <HelpButton title="審査キューの使い方">
          <div className="help-content">
            <h3>ユーザーストーリー</h3>
            <p>審査担当者として、自動検出でNGとなった案件を審査キューから取得し、判定を行います。管理者は二次審査（エスカレーション案件の最終判定）を担当します。</p>

            <h3>審査キューに投入される案件</h3>
            <p>以下の条件で案件が自動的に審査キューに投入されます:</p>
            <ul>
              <li><strong>契約違反（violation）</strong> — アラート severity が critical / high / medium の場合に自動投入。価格・決済方法・手数料・サブスク条件の不一致を検出した案件です。</li>
              <li><strong>ダークパターン（dark_pattern）</strong> — ダークパターン総合スコアが 0.7 以上の場合に自動投入。CSS欺瞞・LLM分類・UI/UXトラップ・ユーザージャーニー検出の結果です。</li>
              <li><strong>偽サイト（fake_site）</strong> — 偽サイト検出時に priority: critical で自動投入。ドメイン類似度80%以上かつコンテンツ類似度70%以上で確定した案件です。</li>
              <li><strong>OCR失敗</strong> — スマート・リトライ後もOCR信頼度が0%の場合、review_type: violation / priority: medium で自動投入。目視確認が必要な案件です。</li>
            </ul>

            <h3>一覧テーブルの列</h3>
            <table className="help-table">
              <thead><tr><th>列名</th><th>説明</th></tr></thead>
              <tbody>
                <tr><td>ID</td><td>審査案件の一意識別子（#1, #2, ...）</td></tr>
                <tr><td>種別</td><td>契約違反 / ダークパターン / 偽サイト</td></tr>
                <tr><td>ステータス</td><td>未審査 / 審査中 / エスカレーション / 承認済み / 却下済み</td></tr>
                <tr><td>優先度</td><td>CRITICAL / HIGH / MEDIUM / LOW（バッジ色で区別）</td></tr>
                <tr><td>担当者</td><td>割り当て済みの審査者名。未割り当ての場合は「未割り当て」</td></tr>
                <tr><td>作成日時</td><td>案件が審査キューに投入された日時</td></tr>
              </tbody>
            </table>

            <h3>ステータスの意味</h3>
            <table className="help-table">
              <thead><tr><th>ステータス</th><th>バッジ色</th><th>説明</th></tr></thead>
              <tbody>
                <tr><td>未審査</td><td>黄色</td><td>審査待ち。担当者未割り当て</td></tr>
                <tr><td>審査中</td><td>青色</td><td>担当者が割り当てられ、審査進行中</td></tr>
                <tr><td>エスカレーション</td><td>赤色</td><td>一次審査で判断困難と判定。admin による二次審査待ち</td></tr>
                <tr><td>承認済み</td><td>緑色</td><td>問題なしと判定。関連アラートは解決済みに更新</td></tr>
                <tr><td>却下済み</td><td>灰色</td><td>違反確定。顧客への違反確定通知が送信される</td></tr>
              </tbody>
            </table>

            <h3>優先度の意味</h3>
            <table className="help-table">
              <thead><tr><th>優先度</th><th>バッジ色</th><th>投入条件の例</th></tr></thead>
              <tbody>
                <tr><td>CRITICAL</td><td>赤色</td><td>偽サイト検出、severity: critical のアラート</td></tr>
                <tr><td>HIGH</td><td>黄色</td><td>severity: high のアラート</td></tr>
                <tr><td>MEDIUM</td><td>青色</td><td>severity: medium のアラート、OCR失敗案件</td></tr>
                <tr><td>LOW</td><td>灰色</td><td>severity: low のアラート</td></tr>
              </tbody>
            </table>

            <h3>フィルタリング</h3>
            <ul>
              <li><strong>ステータス</strong> — 未審査 / 審査中 / エスカレーション / 承認済み / 却下済み で絞り込み</li>
              <li><strong>優先度</strong> — Critical / High / Medium / Low で絞り込み</li>
              <li><strong>種別</strong> — 契約違反 / ダークパターン / 偽サイト で絞り込み</li>
            </ul>
            <p>デフォルトのソート順は優先度降順（Critical → Low）、同一優先度内は作成日時昇順（古い案件優先）です。</p>

            <h3>審査ワークフロー</h3>
            <ol>
              <li><strong>案件を選択</strong> — 行をクリックして詳細画面へ遷移</li>
              <li><strong>担当者割り当て</strong> — 「担当者として割り当て」ボタンで自分に割り当て（pending → in_review）</li>
              <li><strong>一次審査判定</strong> — 承認（問題なし）/ 却下（違反確定）/ エスカレーション（二次審査へ）を選択し、コメント必須で送信</li>
              <li><strong>二次審査（admin のみ）</strong> — エスカレーション案件に対して最終承認 / 最終却下を判定</li>
            </ol>

            <h3>状態遷移ルール</h3>
            <ul>
              <li>pending → in_review（担当者割り当て時のみ）</li>
              <li>in_review → approved / rejected / escalated（一次審査判定）</li>
              <li>escalated → approved / rejected（二次審査判定、admin のみ）</li>
              <li>approved / rejected は最終状態（変更不可）</li>
            </ul>

            <h3>ロール別の操作権限</h3>
            <table className="help-table">
              <thead><tr><th>操作</th><th>reviewer</th><th>admin</th><th>viewer</th></tr></thead>
              <tbody>
                <tr><td>一覧閲覧</td><td>○</td><td>○</td><td>×</td></tr>
                <tr><td>詳細閲覧</td><td>○</td><td>○</td><td>×</td></tr>
                <tr><td>担当者割り当て</td><td>○</td><td>○</td><td>×</td></tr>
                <tr><td>一次審査判定</td><td>○</td><td>○</td><td>×</td></tr>
                <tr><td>二次審査判定</td><td>×</td><td>○</td><td>×</td></tr>
                <tr><td>統計閲覧</td><td>○</td><td>○</td><td>○</td></tr>
              </tbody>
            </table>

            <div className="help-tip">同一アラートに対する審査案件の重複投入は自動的に防止されます。判定時のコメントは必須です（1文字以上）。</div>
          </div>
        </HelpButton></h1>
        <span className="reviews-count">{total} 件</span>
      </div>

      <Card>
        <div className="reviews-filters">
          <Select
            label="ステータス"
            value={filterStatus}
            onChange={(v) => { setFilterStatus(v); handleFilterChange(); }}
            options={STATUS_OPTIONS}
            placeholder="ステータス"
          />
          <Select
            label="優先度"
            value={filterPriority}
            onChange={(v) => { setFilterPriority(v); handleFilterChange(); }}
            options={PRIORITY_OPTIONS}
            placeholder="優先度"
          />
          <Select
            label="種別"
            value={filterType}
            onChange={(v) => { setFilterType(v); handleFilterChange(); }}
            options={TYPE_OPTIONS}
            placeholder="種別"
          />
        </div>

        {error && <div className="reviews-error" role="alert">{error}</div>}

        {loading ? (
          <div className="reviews-loading" aria-live="polite">読み込み中...</div>
        ) : (
          <div className="reviews-table-wrapper">
            <table className="reviews-table" aria-label="審査キュー一覧">
              <thead>
                <tr>
                  <th scope="col">ID</th>
                  <th scope="col">種別</th>
                  <th scope="col">ステータス</th>
                  <th scope="col">優先度</th>
                  <th scope="col">担当者</th>
                  <th scope="col">作成日時</th>
                </tr>
              </thead>
              <tbody>
                {items.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="reviews-empty">案件がありません</td>
                  </tr>
                ) : (
                  items.map((item) => (
                    <tr
                      key={item.id}
                      className="reviews-row"
                      onClick={() => navigate(`/reviews/${item.id}`)}
                      tabIndex={0}
                      onKeyDown={(e) => e.key === 'Enter' && navigate(`/reviews/${item.id}`)}
                      aria-label={`審査案件 ${item.id} の詳細を表示`}
                    >
                      <td>#{item.id}</td>
                      <td>{reviewTypeLabel(item.review_type)}</td>
                      <td>
                        <Badge variant={statusBadgeVariant(item.status)}>
                          {statusLabel(item.status)}
                        </Badge>
                      </td>
                      <td>
                        <Badge variant={priorityBadgeVariant(item.priority)}>
                          {item.priority.toUpperCase()}
                        </Badge>
                      </td>
                      <td>{item.assigned_to ?? '未割り当て'}</td>
                      <td>{new Date(item.created_at).toLocaleString('ja-JP')}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {totalPages > 1 && (
          <div className="reviews-pagination" role="navigation" aria-label="ページネーション">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              disabled={currentPage === 1}
            >
              前へ
            </Button>
            <span className="reviews-page-info">{currentPage} / {totalPages}</span>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setOffset(offset + PAGE_SIZE)}
              disabled={currentPage === totalPages}
            >
              次へ
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
};

export default Reviews;
