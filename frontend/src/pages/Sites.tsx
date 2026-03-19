import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getSites, getCustomers, createSite, updateSite, deleteSite, triggerCrawl, getCrawlStatus, getLatestCrawlResult, type Site, type Customer, type CrawlResult } from '../services/api';
import { useAutoRefresh } from '../hooks/useAutoRefresh';

interface SiteFormData {
  customer_id: number;
  name: string;
  url: string;
  monitoring_enabled: boolean;
}

const Sites = () => {
  const [sites, setSites] = useState<Site[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [customerFilter, setCustomerFilter] = useState<string>('all');
  
  // Crawl state
  const [crawlingStates, setCrawlingStates] = useState<Record<number, boolean>>({});
  const [crawlErrors, setCrawlErrors] = useState<Record<number, string>>({});
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [toastType, setToastType] = useState<'success' | 'error' | 'warning'>('success');
  
  // Modal state
  const [showModal, setShowModal] = useState(false);
  const [modalMode, setModalMode] = useState<'create' | 'edit'>('create');
  const [editingSite, setEditingSite] = useState<Site | null>(null);
  const [formData, setFormData] = useState<SiteFormData>({
    customer_id: 0,
    name: '',
    url: '',
    monitoring_enabled: true,
  });
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Crawl result modal state
  const [showCrawlResultModal, setShowCrawlResultModal] = useState(false);
  const [crawlResultLoading, setCrawlResultLoading] = useState(false);
  const [crawlResultError, setCrawlResultError] = useState<string | null>(null);
  const [selectedCrawlResult, setSelectedCrawlResult] = useState<CrawlResult | null>(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [sitesData, customersData] = await Promise.all([
        getSites(),
        getCustomers(true), // active customers only
      ]);
      setSites(sitesData);
      setCustomers(customersData);
      setError(null);
    } catch (err) {
      setError('データの取得に失敗しました');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // Auto-refresh every 30 seconds
  useAutoRefresh(fetchData, 30000);

  const filteredSites = sites.filter(site => {
    const matchesSearch = site.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         site.url.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'all' || site.compliance_status === statusFilter;
    const matchesCustomer = customerFilter === 'all' || site.customer_id.toString() === customerFilter;
    return matchesSearch && matchesStatus && matchesCustomer;
  });

  const getCustomerName = (customerId: number) => {
    const customer = customers.find(c => c.id === customerId);
    return customer ? customer.name : `顧客ID: ${customerId}`;
  };

  const getStatusBadge = (status: string) => {
    const statusMap: Record<string, { label: string; className: string }> = {
      compliant: { label: '準拠', className: 'status-compliant' },
      violation: { label: '違反', className: 'status-violation' },
      pending: { label: '保留中', className: 'status-pending' },
      error: { label: 'エラー', className: 'status-error' },
    };
    const statusInfo = statusMap[status] || { label: status, className: '' };
    return <span className={`status-badge ${statusInfo.className}`}>{statusInfo.label}</span>;
  };

  // Modal handlers
  const openCreateModal = () => {
    setModalMode('create');
    setEditingSite(null);
    setFormData({
      customer_id: customers.length > 0 ? customers[0].id : 0,
      name: '',
      url: '',
      monitoring_enabled: true,
    });
    setFormError(null);
    setShowModal(true);
  };

  const openEditModal = (site: Site) => {
    setModalMode('edit');
    setEditingSite(site);
    setFormData({
      customer_id: site.customer_id,
      name: site.name,
      url: site.url,
      monitoring_enabled: site.is_active,
    });
    setFormError(null);
    setShowModal(true);
  };

  const closeModal = () => {
    setShowModal(false);
    setEditingSite(null);
    setFormData({
      customer_id: customers.length > 0 ? customers[0].id : 0,
      name: '',
      url: '',
      monitoring_enabled: true,
    });
    setFormError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setSubmitting(true);

    try {
      // Validation
      if (formData.customer_id === 0) {
        setFormError('顧客を選択してください');
        setSubmitting(false);
        return;
      }
      if (!formData.name.trim()) {
        setFormError('サイト名を入力してください');
        setSubmitting(false);
        return;
      }
      if (!formData.url.trim()) {
        setFormError('URLを入力してください');
        setSubmitting(false);
        return;
      }
      
      // URL validation
      try {
        new URL(formData.url);
      } catch {
        setFormError('有効なURLを入力してください');
        setSubmitting(false);
        return;
      }

      if (modalMode === 'create') {
        await createSite(formData);
      } else if (editingSite) {
        await updateSite(editingSite.id, formData);
      }

      await fetchData();
      closeModal();
    } catch (err: any) {
      setFormError(err.response?.data?.detail || 'エラーが発生しました');
      console.error(err);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (site: Site) => {
    if (!confirm(`「${site.name}」を削除してもよろしいですか？`)) {
      return;
    }

    try {
      await deleteSite(site.id);
      await fetchData();
    } catch (err: any) {
      alert(err.response?.data?.detail || '削除に失敗しました');
      console.error(err);
    }
  };

  // Toast notification handler
  const showToast = (message: string, type: 'success' | 'error' | 'warning' = 'success') => {
    setToastMessage(message);
    setToastType(type);
    setTimeout(() => {
      setToastMessage(null);
    }, 5000);
  };

  // Crawl handlers
  const handleCrawl = async (site: Site) => {
    // Check if already crawling
    if (crawlingStates[site.id]) {
      showToast('クロールが実行中です', 'warning');
      return;
    }

    // Start crawling
    setCrawlingStates(prev => ({ ...prev, [site.id]: true }));
    setCrawlErrors(prev => {
      const newErrors = { ...prev };
      delete newErrors[site.id];
      return newErrors;
    });

    try {
      const { job_id } = await triggerCrawl(site.id);
      
      // Poll for status
      const pollInterval = setInterval(async () => {
        try {
          const statusResponse = await getCrawlStatus(job_id);
          
          if (statusResponse.status === 'completed') {
            clearInterval(pollInterval);
            setCrawlingStates(prev => ({ ...prev, [site.id]: false }));
            showToast('クロールが完了しました', 'success');
            await fetchData(); // Refresh site list
          } else if (statusResponse.status === 'failed') {
            clearInterval(pollInterval);
            setCrawlingStates(prev => ({ ...prev, [site.id]: false }));
            setCrawlErrors(prev => ({ ...prev, [site.id]: 'クロールに失敗しました' }));
            showToast('クロールに失敗しました', 'error');
          }
        } catch (err) {
          clearInterval(pollInterval);
          setCrawlingStates(prev => ({ ...prev, [site.id]: false }));
          setCrawlErrors(prev => ({ ...prev, [site.id]: 'ステータス取得に失敗しました' }));
          showToast('クロールステータスの取得に失敗しました', 'error');
        }
      }, 2000); // Poll every 2 seconds

      // Timeout after 5 minutes
      setTimeout(() => {
        clearInterval(pollInterval);
        if (crawlingStates[site.id]) {
          setCrawlingStates(prev => ({ ...prev, [site.id]: false }));
          showToast('クロールがタイムアウトしました', 'error');
        }
      }, 300000);
    } catch (err: any) {
      setCrawlingStates(prev => ({ ...prev, [site.id]: false }));
      
      if (err.response?.status === 409) {
        showToast('クロールが実行中です', 'warning');
      } else {
        const errorMessage = err.response?.data?.detail || 'クロールの開始に失敗しました';
        setCrawlErrors(prev => ({ ...prev, [site.id]: errorMessage }));
        showToast(errorMessage, 'error');
      }
      console.error(err);
    }
  };

  // Crawl result modal handlers
  const handleViewCrawlResult = async (site: Site) => {
    if (!site.last_crawled_at) {
      showToast('クロール結果がありません', 'warning');
      return;
    }

    setShowCrawlResultModal(true);
    setCrawlResultLoading(true);
    setCrawlResultError(null);
    setSelectedCrawlResult(null);

    try {
      const result = await getLatestCrawlResult(site.id);
      setSelectedCrawlResult(result);
    } catch (err: any) {
      setCrawlResultError(err.response?.data?.detail || 'クロール結果の取得に失敗しました');
      console.error(err);
    } finally {
      setCrawlResultLoading(false);
    }
  };

  const closeCrawlResultModal = () => {
    setShowCrawlResultModal(false);
    setSelectedCrawlResult(null);
    setCrawlResultError(null);
  };

  if (loading) {
    return <div className="loading">読み込み中...</div>;
  }

  if (error) {
    return <div className="error">{error}</div>;
  }

  return (
    <div className="sites">
      <div className="page-header">
        <h1>監視対象サイト一覧</h1>
        <button className="btn btn-primary" onClick={openCreateModal}>
          + 新規サイト登録
        </button>
      </div>
      
      <div className="filters">
        <input
          type="text"
          placeholder="サイト名またはURLで検索..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="search-input"
        />
        
        <select
          value={customerFilter}
          onChange={(e) => setCustomerFilter(e.target.value)}
          className="status-filter"
        >
          <option value="all">すべての顧客</option>
          {customers.map(customer => (
            <option key={customer.id} value={customer.id}>{customer.name}</option>
          ))}
        </select>
        
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="status-filter"
        >
          <option value="all">すべてのステータス</option>
          <option value="compliant">準拠</option>
          <option value="violation">違反</option>
          <option value="pending">保留中</option>
          <option value="error">エラー</option>
        </select>
      </div>

      <div className="sites-table">
        <table>
          <thead>
            <tr>
              <th>顧客名</th>
              <th>サイト名</th>
              <th>URL</th>
              <th>ステータス</th>
              <th>最終クロール</th>
              <th>監視</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {filteredSites.map(site => (
              <tr key={site.id}>
                <td>{getCustomerName(site.customer_id)}</td>
                <td>{site.name}</td>
                <td><a href={site.url} target="_blank" rel="noopener noreferrer">{site.url}</a></td>
                <td>{getStatusBadge(site.compliance_status)}</td>
                <td>
                  {site.last_crawled_at ? (
                    <button 
                      className="link-button" 
                      onClick={() => handleViewCrawlResult(site)}
                      title="クロール結果を表示"
                    >
                      {new Date(site.last_crawled_at).toLocaleString('ja-JP')}
                    </button>
                  ) : (
                    '未実施'
                  )}
                </td>
                <td>
                  <span className={site.is_active ? 'badge-active' : 'badge-inactive'}>
                    {site.is_active ? '有効' : '無効'}
                  </span>
                </td>
                <td>
                  <div className="action-buttons">
                    <button 
                      className="btn btn-sm btn-primary" 
                      onClick={() => handleCrawl(site)}
                      disabled={crawlingStates[site.id]}
                      title="今すぐクロール"
                    >
                      {crawlingStates[site.id] ? (
                        <>
                          <span className="spinner-small"></span>
                          クロール中...
                        </>
                      ) : (
                        '今すぐクロール'
                      )}
                    </button>
                    <button 
                      className="btn btn-sm btn-secondary" 
                      onClick={() => openEditModal(site)}
                      title="編集"
                    >
                      編集
                    </button>
                    <button 
                      className="btn btn-sm btn-danger" 
                      onClick={() => handleDelete(site)}
                      title="削除"
                    >
                      削除
                    </button>
                  </div>
                  {crawlErrors[site.id] && (
                    <div className="error-text-small">{crawlErrors[site.id]}</div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        
        {filteredSites.length === 0 && (
          <div className="no-data">該当するサイトがありません</div>
        )}
      </div>

      {/* Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{modalMode === 'create' ? '新規サイト登録' : 'サイト編集'}</h2>
              <button className="modal-close" onClick={closeModal}>×</button>
            </div>
            
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label htmlFor="customer_id">顧客 *</label>
                <select
                  id="customer_id"
                  value={formData.customer_id}
                  onChange={(e) => setFormData({ ...formData, customer_id: Number(e.target.value) })}
                  required
                >
                  <option value={0}>顧客を選択</option>
                  {customers.map(customer => (
                    <option key={customer.id} value={customer.id}>
                      {customer.name} {customer.company_name ? `(${customer.company_name})` : ''}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="name">サイト名 *</label>
                <input
                  type="text"
                  id="name"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="例: Example Payment Site"
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="url">URL *</label>
                <input
                  type="url"
                  id="url"
                  value={formData.url}
                  onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                  placeholder="例: https://example.com"
                  required
                />
              </div>

              <div className="form-group">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={formData.monitoring_enabled}
                    onChange={(e) => setFormData({ ...formData, monitoring_enabled: e.target.checked })}
                  />
                  <span>監視を有効にする</span>
                </label>
              </div>

              {formError && (
                <div className="form-error">{formError}</div>
              )}

              <div className="modal-footer">
                <button 
                  type="button" 
                  className="btn btn-secondary" 
                  onClick={closeModal}
                  disabled={submitting}
                >
                  キャンセル
                </button>
                <button 
                  type="submit" 
                  className="btn btn-primary"
                  disabled={submitting}
                >
                  {submitting ? '処理中...' : (modalMode === 'create' ? '登録' : '更新')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Toast Notification */}
      {toastMessage && (
        <div className={`toast toast-${toastType}`}>
          <div className="toast-content">
            <span>{toastMessage}</span>
            <button className="toast-close" onClick={() => setToastMessage(null)}>×</button>
          </div>
        </div>
      )}

      {/* Crawl Result Modal */}
      {showCrawlResultModal && (
        <div className="modal-overlay" onClick={closeCrawlResultModal}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>クロール結果詳細</h2>
              <button className="modal-close" onClick={closeCrawlResultModal}>×</button>
            </div>
            
            <div className="modal-body">
              {crawlResultLoading && (
                <div className="loading">読み込み中...</div>
              )}
              
              {crawlResultError && (
                <div className="error">{crawlResultError}</div>
              )}
              
              {selectedCrawlResult && (
                <div className="crawl-result-details">
                  <div className="detail-row">
                    <span className="detail-label">取得日時:</span>
                    <span className="detail-value">
                      {new Date(selectedCrawlResult.crawled_at).toLocaleString('ja-JP')}
                    </span>
                  </div>
                  
                  <div className="detail-row">
                    <span className="detail-label">URL:</span>
                    <span className="detail-value">
                      <a href={selectedCrawlResult.url} target="_blank" rel="noopener noreferrer">
                        {selectedCrawlResult.url}
                      </a>
                    </span>
                  </div>
                  
                  <div className="detail-row">
                    <span className="detail-label">ステータス:</span>
                    <span className="detail-value">
                      {selectedCrawlResult.status_code === 200 ? (
                        <span className="status-badge status-compliant">完了</span>
                      ) : (
                        <span className="status-badge status-error">
                          失敗 (HTTP {selectedCrawlResult.status_code})
                        </span>
                      )}
                    </span>
                  </div>
                  
                  {selectedCrawlResult.screenshot_path && (
                    <div className="detail-row">
                      <span className="detail-label">スクリーンショット:</span>
                      <div className="detail-value">
                        <img 
                          src={selectedCrawlResult.screenshot_path} 
                          alt="クロール時のスクリーンショット"
                          className="crawl-screenshot"
                          style={{ maxWidth: '100%', marginTop: '10px' }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
            
            <div className="modal-footer">
              {selectedCrawlResult && (
                <>
                  <Link
                    to={`/sites/${selectedCrawlResult.site_id}/crawl-results/${selectedCrawlResult.id}/review`}
                    className="btn btn-primary"
                  >
                    レビュー
                  </Link>
                  <Link
                    to={`/sites/${selectedCrawlResult.site_id}/crawl-results/compare`}
                    className="btn btn-secondary"
                  >
                    比較
                  </Link>
                </>
              )}
              <button 
                type="button" 
                className="btn btn-secondary" 
                onClick={closeCrawlResultModal}
              >
                閉じる
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Sites;
