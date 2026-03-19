import { useEffect, useState } from 'react';
import { getSites, getContracts, getSiteContracts, createContract, deleteContract, type Site, type ContractCondition, type ContractConditionCreate } from '../services/api';

const Contracts = () => {
  const [sites, setSites] = useState<Site[]>([]);
  const [contracts, setContracts] = useState<ContractCondition[]>([]);
  const [selectedSite, setSelectedSite] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Modal state
  const [showModal, setShowModal] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  
  // Form state
  const [formData, setFormData] = useState<ContractConditionCreate>({
    site_id: 0,
    prices: { JPY: 0 },
    payment_methods: { allowed: [], required: [] },
    fees: { percentage: 0, fixed: 0 },
    subscription_terms: {
      has_commitment: false,
      commitment_months: 0,
      has_cancellation_policy: false,
    },
  });

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    if (selectedSite) {
      fetchSiteContracts(selectedSite);
    }
  }, [selectedSite]);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [sitesData, contractsData] = await Promise.all([
        getSites(),
        getContracts(),
      ]);
      setSites(sitesData);
      setContracts(contractsData);
      setError(null);
    } catch (err) {
      setError('データの取得に失敗しました');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const fetchSiteContracts = async (siteId: number) => {
    try {
      const siteContracts = await getSiteContracts(siteId, false);
      setContracts(siteContracts);
    } catch (err) {
      console.error('Failed to fetch site contracts:', err);
    }
  };

  const openCreateModal = (siteId?: number) => {
    setFormData({
      site_id: siteId || 0,
      prices: { JPY: 0 },
      payment_methods: { allowed: [], required: [] },
      fees: { percentage: 0, fixed: 0 },
      subscription_terms: {
        has_commitment: false,
        commitment_months: 0,
        has_cancellation_policy: false,
      },
    });
    setFormError(null);
    setShowModal(true);
  };

  const closeModal = () => {
    setShowModal(false);
    setFormError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setSubmitting(true);

    try {
      if (formData.site_id === 0) {
        setFormError('サイトを選択してください');
        setSubmitting(false);
        return;
      }

      await createContract(formData);
      await fetchData();
      if (selectedSite) {
        await fetchSiteContracts(selectedSite);
      }
      closeModal();
    } catch (err: any) {
      setFormError(err.response?.data?.detail || 'エラーが発生しました');
      console.error(err);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (contract: ContractCondition) => {
    if (!confirm(`契約条件 (バージョン ${contract.version}) を削除してもよろしいですか？`)) {
      return;
    }

    try {
      await deleteContract(contract.id);
      await fetchData();
      if (selectedSite) {
        await fetchSiteContracts(selectedSite);
      }
    } catch (err: any) {
      alert(err.response?.data?.detail || '削除に失敗しました');
      console.error(err);
    }
  };

  const addPaymentMethod = (type: 'allowed' | 'required') => {
    const method = prompt(`${type === 'allowed' ? '許可する' : '必須の'}決済方法を入力してください（例: credit_card, bank_transfer）`);
    if (method) {
      setFormData({
        ...formData,
        payment_methods: {
          ...formData.payment_methods,
          [type]: [...(formData.payment_methods[type] || []), method],
        },
      });
    }
  };

  const removePaymentMethod = (type: 'allowed' | 'required', index: number) => {
    const methods = [...(formData.payment_methods[type] || [])];
    methods.splice(index, 1);
    setFormData({
      ...formData,
      payment_methods: {
        ...formData.payment_methods,
        [type]: methods,
      },
    });
  };

  if (loading) {
    return <div className="loading">読み込み中...</div>;
  }

  if (error) {
    return <div className="error">{error}</div>;
  }

  const filteredContracts = selectedSite
    ? contracts.filter(c => c.site_id === selectedSite)
    : contracts;

  return (
    <div className="contracts">
      <div className="page-header">
        <h1>契約条件管理</h1>
        <button className="btn btn-primary" onClick={() => openCreateModal()}>
          + 新規契約条件登録
        </button>
      </div>

      <div className="filters">
        <select
          value={selectedSite || ''}
          onChange={(e) => setSelectedSite(e.target.value ? Number(e.target.value) : null)}
          className="site-filter"
        >
          <option value="">すべてのサイト</option>
          {sites.map(site => (
            <option key={site.id} value={site.id}>{site.name}</option>
          ))}
        </select>
      </div>

      <div className="contracts-list">
        {filteredContracts.map(contract => {
          const site = sites.find(s => s.id === contract.site_id);
          return (
            <div key={contract.id} className={`contract-card ${contract.is_current ? 'current' : 'archived'}`}>
              <div className="contract-header">
                <div>
                  <h3>{site?.name || `Site ${contract.site_id}`}</h3>
                  <span className="contract-version">バージョン {contract.version}</span>
                  {contract.is_current && <span className="badge-current">現在</span>}
                </div>
                <div className="contract-actions">
                  <button 
                    className="btn btn-sm btn-danger" 
                    onClick={() => handleDelete(contract)}
                    title="削除"
                  >
                    削除
                  </button>
                </div>
              </div>

              <div className="contract-details">
                <div className="detail-section">
                  <h4>価格</h4>
                  <ul>
                    {Object.entries(contract.prices).map(([currency, price]) => (
                      <li key={currency}>
                        {currency}: {Array.isArray(price) ? price.join(', ') : price}
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="detail-section">
                  <h4>決済方法</h4>
                  <div>
                    <strong>許可:</strong> {contract.payment_methods.allowed?.join(', ') || 'なし'}
                  </div>
                  <div>
                    <strong>必須:</strong> {contract.payment_methods.required?.join(', ') || 'なし'}
                  </div>
                </div>

                <div className="detail-section">
                  <h4>手数料</h4>
                  <div>
                    <strong>パーセンテージ:</strong> {
                      contract.fees.percentage 
                        ? (Array.isArray(contract.fees.percentage) 
                            ? contract.fees.percentage.join(', ') + '%' 
                            : contract.fees.percentage + '%')
                        : 'なし'
                    }
                  </div>
                  <div>
                    <strong>固定:</strong> {
                      contract.fees.fixed 
                        ? (Array.isArray(contract.fees.fixed) 
                            ? contract.fees.fixed.join(', ') 
                            : contract.fees.fixed)
                        : 'なし'
                    }
                  </div>
                </div>

                {contract.subscription_terms && (
                  <div className="detail-section">
                    <h4>サブスクリプション条件</h4>
                    <div>
                      <strong>契約縛り:</strong> {contract.subscription_terms.has_commitment ? 'あり' : 'なし'}
                    </div>
                    {contract.subscription_terms.commitment_months && (
                      <div>
                        <strong>契約期間:</strong> {
                          Array.isArray(contract.subscription_terms.commitment_months)
                            ? contract.subscription_terms.commitment_months.join(', ') + 'ヶ月'
                            : contract.subscription_terms.commitment_months + 'ヶ月'
                        }
                      </div>
                    )}
                    <div>
                      <strong>解約ポリシー:</strong> {contract.subscription_terms.has_cancellation_policy ? 'あり' : 'なし'}
                    </div>
                  </div>
                )}
              </div>

              <div className="contract-footer">
                <small>作成日時: {new Date(contract.created_at).toLocaleString('ja-JP')}</small>
              </div>
            </div>
          );
        })}
      </div>

      {filteredContracts.length === 0 && (
        <div className="no-data">契約条件がありません</div>
      )}

      {/* Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal-content modal-large" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>新規契約条件登録</h2>
              <button className="modal-close" onClick={closeModal}>×</button>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label htmlFor="site_id">サイト *</label>
                <select
                  id="site_id"
                  value={formData.site_id}
                  onChange={(e) => setFormData({ ...formData, site_id: Number(e.target.value) })}
                  required
                >
                  <option value={0}>サイトを選択</option>
                  {sites.map(site => (
                    <option key={site.id} value={site.id}>{site.name}</option>
                  ))}
                </select>
              </div>

              <div className="form-section">
                <h3>価格設定</h3>
                <div className="form-group">
                  <label htmlFor="price_jpy">JPY価格 *</label>
                  <input
                    type="number"
                    id="price_jpy"
                    value={formData.prices.JPY}
                    onChange={(e) => setFormData({
                      ...formData,
                      prices: { ...formData.prices, JPY: Number(e.target.value) }
                    })}
                    required
                  />
                </div>
              </div>

              <div className="form-section">
                <h3>決済方法</h3>
                <div className="form-group">
                  <label>許可する決済方法</label>
                  <div className="tag-list">
                    {formData.payment_methods.allowed?.map((method, index) => (
                      <span key={index} className="tag">
                        {method}
                        <button type="button" onClick={() => removePaymentMethod('allowed', index)}>×</button>
                      </span>
                    ))}
                    <button type="button" className="btn btn-sm" onClick={() => addPaymentMethod('allowed')}>
                      + 追加
                    </button>
                  </div>
                </div>

                <div className="form-group">
                  <label>必須の決済方法</label>
                  <div className="tag-list">
                    {formData.payment_methods.required?.map((method, index) => (
                      <span key={index} className="tag">
                        {method}
                        <button type="button" onClick={() => removePaymentMethod('required', index)}>×</button>
                      </span>
                    ))}
                    <button type="button" className="btn btn-sm" onClick={() => addPaymentMethod('required')}>
                      + 追加
                    </button>
                  </div>
                </div>
              </div>

              <div className="form-section">
                <h3>手数料</h3>
                <div className="form-row">
                  <div className="form-group">
                    <label htmlFor="fee_percentage">パーセンテージ手数料 (%)</label>
                    <input
                      type="number"
                      id="fee_percentage"
                      step="0.1"
                      value={formData.fees.percentage}
                      onChange={(e) => setFormData({
                        ...formData,
                        fees: { ...formData.fees, percentage: Number(e.target.value) }
                      })}
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="fee_fixed">固定手数料</label>
                    <input
                      type="number"
                      id="fee_fixed"
                      value={formData.fees.fixed}
                      onChange={(e) => setFormData({
                        ...formData,
                        fees: { ...formData.fees, fixed: Number(e.target.value) }
                      })}
                    />
                  </div>
                </div>
              </div>

              <div className="form-section">
                <h3>サブスクリプション条件</h3>
                <div className="form-group">
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={formData.subscription_terms?.has_commitment || false}
                      onChange={(e) => setFormData({
                        ...formData,
                        subscription_terms: {
                          ...formData.subscription_terms,
                          has_commitment: e.target.checked,
                        }
                      })}
                    />
                    <span>契約期間の縛りあり</span>
                  </label>
                </div>

                {formData.subscription_terms?.has_commitment && (
                  <div className="form-group">
                    <label htmlFor="commitment_months">契約期間（月）</label>
                    <input
                      type="number"
                      id="commitment_months"
                      value={formData.subscription_terms?.commitment_months || 0}
                      onChange={(e) => setFormData({
                        ...formData,
                        subscription_terms: {
                          ...formData.subscription_terms,
                          commitment_months: Number(e.target.value),
                        }
                      })}
                    />
                  </div>
                )}

                <div className="form-group">
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={formData.subscription_terms?.has_cancellation_policy || false}
                      onChange={(e) => setFormData({
                        ...formData,
                        subscription_terms: {
                          ...formData.subscription_terms,
                          has_cancellation_policy: e.target.checked,
                        }
                      })}
                    />
                    <span>解約ポリシーあり</span>
                  </label>
                </div>
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
                  {submitting ? '処理中...' : '登録'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Contracts;
