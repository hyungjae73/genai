import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { triggerCrawl, getCrawlStatus, getLatestCrawlResult } from '../services/api';
import type { Site, CrawlResult } from '../services/api';
import { useSites, useCreateSite, useUpdateSite, useDeleteSite, siteKeys } from '../hooks/queries/useSites';
import { useCustomers } from '../hooks/queries/useCustomers';
import { Badge } from '../components/ui/Badge/Badge';
import { Button } from '../components/ui/Button/Button';
import { Table, type TableColumn } from '../components/ui/Table/Table';
import { Input } from '../components/ui/Input/Input';
import { Select } from '../components/ui/Select/Select';
import { Modal } from '../components/ui/Modal/Modal';
import { HelpButton } from '../components/ui/HelpButton/HelpButton';
import './Sites.css';

type SiteRecord = Site & Record<string, unknown>;

interface SiteFormData {
  customer_id: number;
  name: string;
  url: string;
  monitoring_enabled: boolean;
}

interface Toast {
  message: string;
  type: 'success' | 'error' | 'warning';
}

const complianceStatusMap: Record<string, { label: string; variant: 'success' | 'danger' | 'warning' | 'neutral'; description: string }> = {
  compliant: { label: '準拠', variant: 'success', description: '契約条件に準拠しています' },
  violation: { label: '違反', variant: 'danger', description: '契約条件の違反が検出されました' },
  pending: { label: '保留', variant: 'warning', description: 'クロール未実行または検証待ちです' },
  error: { label: 'エラー', variant: 'neutral', description: 'クロールまたは検証でエラーが発生しました' },
};

const statusFilterOptions = [
  { value: 'all', label: 'すべてのステータス' },
  { value: 'compliant', label: '準拠' },
  { value: 'violation', label: '違反' },
  { value: 'pending', label: '保留' },
  { value: 'error', label: 'エラー' },
];

const Sites = () => {
  const queryClient = useQueryClient();
  const { data: sites = [], isLoading: sitesLoading, error: sitesError } = useSites();
  const { data: customers = [], isLoading: customersLoading } = useCustomers();
  const createSiteMutation = useCreateSite();
  const updateSiteMutation = useUpdateSite();
  const deleteSiteMutation = useDeleteSite();

  const loading = sitesLoading || customersLoading;
  const error = sitesError ? 'サイト一覧の取得に失敗しました' : null;

  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [customerFilter, setCustomerFilter] = useState('all');

  // Crawl state
  const [crawlingIds, setCrawlingIds] = useState<Set<number>>(new Set());
  const [toast, setToast] = useState<Toast | null>(null);

  // Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [modalLoading, setModalLoading] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);
  const [crawlResult, setCrawlResult] = useState<CrawlResult | null>(null);

  // Site CRUD modal state
  const [siteModalOpen, setSiteModalOpen] = useState(false);
  const [siteModalMode, setSiteModalMode] = useState<'create' | 'edit'>('create');
  const [editingSite, setEditingSite] = useState<Site | null>(null);
  const [formData, setFormData] = useState<SiteFormData>({
    customer_id: 0,
    name: '',
    url: '',
    monitoring_enabled: true,
  });
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Auto-dismiss toast
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  const handleCrawl = async (siteId: number) => {
    setCrawlingIds(prev => new Set(prev).add(siteId));
    try {
      const { job_id } = await triggerCrawl(siteId);
      // Poll for status
      const pollStatus = async () => {
        const status = await getCrawlStatus(job_id);
        if (status.status === 'completed') {
          setToast({ message: 'クロールが完了しました', type: 'success' });
          setCrawlingIds(prev => { const next = new Set(prev); next.delete(siteId); return next; });
          queryClient.invalidateQueries({ queryKey: siteKeys.all });
        } else if (status.status === 'failed') {
          setToast({ message: 'クロールに失敗しました', type: 'error' });
          setCrawlingIds(prev => { const next = new Set(prev); next.delete(siteId); return next; });
        } else {
          setTimeout(pollStatus, 1000);
        }
      };
      await pollStatus();
    } catch (err: any) {
      if (err?.response?.status === 409) {
        setToast({ message: err.response.data?.detail || 'クロールが実行中です', type: 'warning' });
      } else {
        setToast({ message: 'クロールの開始に失敗しました', type: 'error' });
      }
      setCrawlingIds(prev => { const next = new Set(prev); next.delete(siteId); return next; });
    }
  };

  const handleViewCrawlResult = async (siteId: number) => {
    setModalOpen(true);
    setModalLoading(true);
    setModalError(null);
    setCrawlResult(null);
    try {
      const result = await getLatestCrawlResult(siteId);
      setCrawlResult(result);
    } catch (err: any) {
      setModalError(err?.response?.data?.detail || 'クロール結果の取得に失敗しました');
    } finally {
      setModalLoading(false);
    }
  };

  const customerMap = new Map(customers.map(c => [c.id, c.name]));

  // Site CRUD handlers
  const openCreateModal = () => {
    setSiteModalMode('create');
    setEditingSite(null);
    setFormData({
      customer_id: customers.length > 0 ? customers[0].id : 0,
      name: '',
      url: '',
      monitoring_enabled: true,
    });
    setFormError(null);
    setSiteModalOpen(true);
  };

  const openEditModal = (site: Site) => {
    setSiteModalMode('edit');
    setEditingSite(site);
    setFormData({
      customer_id: site.customer_id,
      name: site.name,
      url: site.url,
      monitoring_enabled: site.is_active,
    });
    setFormError(null);
    setSiteModalOpen(true);
  };

  const closeSiteModal = () => {
    setSiteModalOpen(false);
    setEditingSite(null);
    setFormError(null);
  };

  const handleSiteSubmit = async () => {
    setFormError(null);
    setSubmitting(true);
    try {
      if (formData.customer_id === 0) { setFormError('顧客を選択してください'); setSubmitting(false); return; }
      if (!formData.name.trim()) { setFormError('サイト名を入力してください'); setSubmitting(false); return; }
      if (!formData.url.trim()) { setFormError('URLを入力してください'); setSubmitting(false); return; }
      try { new URL(formData.url); } catch { setFormError('有効なURLを入力してください'); setSubmitting(false); return; }

      if (siteModalMode === 'create') {
        await createSiteMutation.mutateAsync(formData);
      } else if (editingSite) {
        await updateSiteMutation.mutateAsync({ id: editingSite.id, data: formData });
      }
      closeSiteModal();
    } catch (err: any) {
      setFormError(err.response?.data?.detail || 'エラーが発生しました');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteSite = async (site: Site) => {
    if (!confirm(`「${site.name}」を削除してもよろしいですか？`)) return;
    try {
      await deleteSiteMutation.mutateAsync(site.id);
    } catch (err: any) {
      alert(err.response?.data?.detail || '削除に失敗しました');
    }
  };

  const customerFilterOptions = [
    { value: 'all', label: 'すべての顧客' },
    ...customers.map(c => ({ value: String(c.id), label: c.name })),
  ];

  const filteredSites = sites.filter(site => {
    const matchesSearch =
      searchQuery === '' ||
      site.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      site.url.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'all' || site.compliance_status === statusFilter;
    const matchesCustomer = customerFilter === 'all' || site.customer_id === Number(customerFilter);
    return matchesSearch && matchesStatus && matchesCustomer;
  });

  const columns: TableColumn<SiteRecord>[] = [
    {
      key: 'name',
      header: 'サイト名',
      render: (site) => (
        <Link to="/sites" className="site-link">
          {site.name as string}
        </Link>
      ),
    },
    {
      key: 'url',
      header: 'URL',
      render: (site) => (
        <a href={site.url as string} target="_blank" rel="noopener noreferrer" className="site-url">
          {site.url as string}
        </a>
      ),
    },
    {
      key: 'customer_id',
      header: '顧客',
      render: (site) => <>{customerMap.get(site.customer_id as number) ?? '—'}</>,
    },
    {
      key: 'compliance_status',
      header: 'ステータス',
      render: (site) => {
        const status = site.compliance_status as string;
        const info = complianceStatusMap[status] || { label: status, variant: 'neutral' as const, description: '' };
        return <Badge variant={info.variant} size="sm" title={info.description}>{info.label}</Badge>;
      },
    },
    {
      key: 'is_active',
      header: '有効',
      render: (site) => (
        <Badge variant={site.is_active ? 'success' : 'neutral'} size="sm">
          {site.is_active ? '有効' : '無効'}
        </Badge>
      ),
    },
    {
      key: 'last_crawled_at',
      header: '最終クロール',
      render: (site) => {
        if (site.last_crawled_at) {
          return (
            <button
              className="crawl-date-button"
              onClick={() => handleViewCrawlResult(site.id as number)}
            >
              {new Date(site.last_crawled_at as string).toLocaleString('ja-JP')}
            </button>
          );
        }
        return <span className="no-crawl-text">未実施</span>;
      },
    },
    {
      key: 'actions',
      header: 'アクション',
      render: (site) => {
        const siteId = site.id as number;
        const isCrawling = crawlingIds.has(siteId);
        return (
          <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
            <Button
              variant="primary"
              size="sm"
              onClick={() => handleCrawl(siteId)}
              disabled={isCrawling}
              loading={isCrawling}
            >
              {isCrawling ? 'クロール中...' : '今すぐクロール'}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => openEditModal(site as Site)}
            >
              編集
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => handleDeleteSite(site as Site)}
            >
              削除
            </Button>
          </div>
        );
      },
    },
  ];

  if (loading) {
    return <div className="loading">読み込み中...</div>;
  }

  if (error) {
    return <div className="error">{error}</div>;
  }

  return (
    <div className="sites">
      <div className="page-header">
        <h1>監視対象サイト一覧 <HelpButton title="このページの使い方">
          <div className="help-content">
            <h3>できること</h3>
            <ul>
              <li>登録済みサイトの監視状態を一覧で確認</li>
              <li>サイト名・URLで検索、ステータスや顧客でフィルタリング</li>
              <li>新しい監視サイトの登録</li>
            </ul>

            <h3>クロールの実行</h3>
            <p>各サイトの「今すぐクロール」ボタンで最新データを取得します。完了すると結果が自動反映されます。</p>

            <h3>結果の確認</h3>
            <p>「最終クロール」列の日時をクリックすると、取得データの詳細（スクリーンショット・抽出データ・違反情報）を確認できます。</p>

            <div className="help-tip">ステータスの意味はステータスフィルター横の ? ボタンで確認できます。</div>
          </div>
        </HelpButton></h1>
        <Button variant="primary" size="md" onClick={openCreateModal}>
          + 新規サイト登録
        </Button>
      </div>

      <div className="filters">
        <Input
          label="検索"
          type="search"
          value={searchQuery}
          onChange={setSearchQuery}
          placeholder="サイト名またはURLで検索"
        />
        <div className="sites-filters__status-group">
          <Select
            label="ステータス"
            value={statusFilter}
            onChange={setStatusFilter}
            options={statusFilterOptions}
            aria-label="ステータスフィルター"
          />
          <HelpButton title="ステータスの意味">
            <div className="status-help">
              <div className="status-help__item">
                <div className="status-help__header">
                  <Badge variant="success" size="sm">準拠</Badge>
                  <span className="status-help__level">Compliant</span>
                </div>
                <p className="status-help__desc">
                  最新のクロール・検証で、契約条件との違反が検出されなかった状態です。
                  価格、決済方法、手数料、サブスクリプション条件の全てが契約通りに表示されています。
                </p>
              </div>
              <div className="status-help__item">
                <div className="status-help__header">
                  <Badge variant="danger" size="sm">違反</Badge>
                  <span className="status-help__level">Violation</span>
                </div>
                <p className="status-help__desc">
                  契約条件との不一致が検出された状態です。
                  価格の相違、許可外の決済方法の表示、手数料の不一致、
                  サブスクリプション条件の違反などが含まれます。
                </p>
              </div>
              <div className="status-help__item">
                <div className="status-help__header">
                  <Badge variant="warning" size="sm">保留</Badge>
                  <span className="status-help__level">Pending</span>
                </div>
                <p className="status-help__desc">
                  まだクロール・検証が実行されていない状態です。
                  サイト登録直後のデフォルトステータスで、
                  「今すぐクロール」ボタンで検証を開始できます。
                </p>
              </div>
              <div className="status-help__item">
                <div className="status-help__header">
                  <Badge variant="neutral" size="sm">エラー</Badge>
                  <span className="status-help__level">Error</span>
                </div>
                <p className="status-help__desc">
                  クロールまたは検証処理自体が失敗した状態です。
                  サイトへの接続不可、タイムアウト、サーバーエラーなどが原因として考えられます。
                  時間をおいて再度クロールを実行してください。
                </p>
              </div>
            </div>
          </HelpButton>
        </div>
        <Select
          label="顧客"
          value={customerFilter}
          onChange={setCustomerFilter}
          options={customerFilterOptions}
          aria-label="顧客フィルター"
          filterable
          placeholder="顧客名で絞り込み..."
        />
      </div>

      <Table<SiteRecord>
        columns={columns}
        data={filteredSites as SiteRecord[]}
        mobileLayout="card"
        emptyMessage="該当するサイトがありません"
        aria-label="監視サイト一覧"
      />

      {/* Toast notification */}
      {toast && (
        <div className={`toast toast-${toast.type}`} role="alert">
          {toast.message}
        </div>
      )}

      {/* Crawl result modal */}
      <Modal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        title="クロール結果詳細"
        footer={
          <Button variant="secondary" size="sm" onClick={() => setModalOpen(false)}>
            閉じる
          </Button>
        }
      >
        {modalLoading && <div className="loading">読み込み中...</div>}
        {modalError && <div className="error">{modalError}</div>}
        {crawlResult && (
          <div className="crawl-result-details">
            <div className="detail-row">
              <span className="detail-label">取得日時:</span>
              <span className="detail-value">{new Date(crawlResult.crawled_at).toLocaleString()}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">URL:</span>
              <span className="detail-value">{crawlResult.url}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">ステータス:</span>
              <span className="detail-value">
                {crawlResult.status_code >= 200 && crawlResult.status_code < 400
                  ? '完了'
                  : `失敗 (HTTP ${crawlResult.status_code})`}
              </span>
            </div>
            {crawlResult.screenshot_path && (
              <div className="detail-row">
                <span className="detail-label">スクリーンショット:</span>
                <img
                  src={`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080'}/${crawlResult.screenshot_path.replace(/^\//, '')}`}
                  alt="クロール時のスクリーンショット"
                  className="crawl-screenshot"
                />
              </div>
            )}
          </div>
        )}
      </Modal>

      {/* Site create/edit modal */}
      <Modal
        isOpen={siteModalOpen}
        onClose={closeSiteModal}
        title={siteModalMode === 'create' ? '新規サイト登録' : 'サイト編集'}
        size="md"
        footer={
          <>
            <Button variant="secondary" size="md" onClick={closeSiteModal} disabled={submitting}>
              キャンセル
            </Button>
            <Button variant="primary" size="md" onClick={handleSiteSubmit} disabled={submitting} loading={submitting}>
              {siteModalMode === 'create' ? '登録' : '更新'}
            </Button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
          <Select
            label="顧客 *"
            value={formData.customer_id ? String(formData.customer_id) : ''}
            onChange={(val) => setFormData({ ...formData, customer_id: Number(val) })}
            options={[
              { value: '', label: '顧客を選択' },
              ...customers.map(c => ({ value: String(c.id), label: c.name })),
            ]}
            aria-label="顧客選択"
          />
          <Input
            label="サイト名 *"
            value={formData.name}
            onChange={(val) => setFormData({ ...formData, name: val })}
            placeholder="例: Example Payment Site"
          />
          <Input
            label="URL *"
            value={formData.url}
            onChange={(val) => setFormData({ ...formData, url: val })}
            placeholder="例: https://example.com"
          />
          <label style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={formData.monitoring_enabled}
              onChange={(e) => setFormData({ ...formData, monitoring_enabled: e.target.checked })}
            />
            <span>監視を有効にする</span>
          </label>
          {formError && <div className="form-error" style={{ color: 'var(--color-danger-text)' }}>{formError}</div>}
        </div>
      </Modal>

    </div>
  );
};

export default Sites;
