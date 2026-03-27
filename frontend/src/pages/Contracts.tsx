import { useEffect, useState } from 'react';
import { getSites, getContracts, getSiteContracts, createContract, deleteContract, type Site, type ContractCondition, type ContractConditionCreate } from '../services/api';
import { Select } from '../components/ui/Select/Select';
import { Card } from '../components/ui/Card/Card';
import { Modal } from '../components/ui/Modal/Modal';
import { Badge } from '../components/ui/Badge/Badge';
import { Button } from '../components/ui/Button/Button';
import { HelpButton } from '../components/ui/HelpButton/HelpButton';
import './Contracts.css';

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

  const modalFooter = (
    <div className="contract-modal-footer">
      <Button
        variant="secondary"
        size="md"
        onClick={closeModal}
        disabled={submitting}
      >
        キャンセル
      </Button>
      <Button
        variant="primary"
        size="md"
        type="submit"
        disabled={submitting}
        loading={submitting}
        onClick={() => {
          const form = document.getElementById('contract-form') as HTMLFormElement;
          form?.requestSubmit();
        }}
      >
        登録
      </Button>
    </div>
  );

  return (
    <div className="contracts">
      <div className="page-header">
        <h1>契約条件管理 <HelpButton title="契約条件管理の使い方">
          <div className="help-content">
            <h3>ユーザーストーリー</h3>
            <p>サイトごとの契約条件を登録・管理し、監視の基準を設定したい</p>

            <h3>サイトフィルター</h3>
            <p>サイトフィルターで特定サイトの契約を絞り込むことができます。「すべてのサイト」を選択するとすべての契約が表示されます。</p>

            <h3>契約条件の設定</h3>
            <ul>
              <li><strong>価格</strong>: 通貨ごとの価格を設定します</li>
              <li><strong>決済方法</strong>: 許可する決済方法と必須の決済方法を設定します</li>
              <li><strong>手数料</strong>: パーセンテージ手数料と固定手数料を設定します</li>
              <li><strong>サブスクリプション条件</strong>: 契約期間の縛りや解約ポリシーを設定します</li>
            </ul>

            <h3>バージョン管理</h3>
            <p>契約条件はバージョン管理されており、変更の履歴を追跡できます。各契約にはバージョン番号が付与されます。</p>

            <h3>「現在」バッジ</h3>
            <p>「現在」バッジが付いた契約が、そのサイトの監視基準として使用されます。監視システムはこの契約条件に基づいて違反を検出します。</p>
          </div>
        </HelpButton></h1>
        <Button variant="primary" size="md" onClick={() => openCreateModal()}>
          + 新規契約条件登録
        </Button>
      </div>

      <div className="filters">
        <Select
          label="サイト"
          value={selectedSite ? String(selectedSite) : ''}
          onChange={(val) => setSelectedSite(val ? Number(val) : null)}
          options={[
            { value: '', label: 'すべてのサイト' },
            ...sites.map(site => ({ value: String(site.id), label: site.name })),
          ]}
          aria-label="サイトフィルター"
          filterable
          placeholder="サイト名で絞り込み..."
        />
      </div>

      <div className="contracts-list">
        {filteredContracts.map(contract => {
          const site = sites.find(s => s.id === contract.site_id);
          return (
            <Card
              key={contract.id}
              hoverable
              borderLeft={contract.is_current ? 'success' : undefined}
              className={!contract.is_current ? 'contract-card--archived' : ''}
            >
              <div className="contract-header">
                <div>
                  <h3>{site?.name || `Site ${contract.site_id}`}</h3>
                  <div className="contract-header__title">
                    <span className="contract-version">バージョン {contract.version}</span>
                    {contract.is_current && <Badge variant="success" size="sm">現在</Badge>}
                  </div>
                </div>
                <div>
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => handleDelete(contract)}
                    aria-label="削除"
                  >
                    削除
                  </Button>
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
            </Card>
          );
        })}
      </div>

      {filteredContracts.length === 0 && (
        <div className="no-data">契約条件がありません</div>
      )}

      <Modal
        isOpen={showModal}
        onClose={closeModal}
        title="新規契約条件登録"
        size="lg"
        footer={modalFooter}
      >
        <form id="contract-form" onSubmit={handleSubmit}>
          <div className="contract-form-group">
            <Select
              label="サイト *"
              value={formData.site_id ? String(formData.site_id) : '0'}
              onChange={(val) => setFormData({ ...formData, site_id: Number(val) })}
              options={[
                { value: '0', label: 'サイトを選択' },
                ...sites.map(site => ({ value: String(site.id), label: site.name })),
              ]}
              aria-label="契約対象サイト"
              filterable
              placeholder="サイト名で絞り込み..."
            />
          </div>

          <div className="contract-form-section">
            <h3>価格設定</h3>
            <div className="contract-form-group">
              <label htmlFor="price_jpy">JPY価格 *</label>
              <input
                type="number"
                id="price_jpy"
                value={Array.isArray(formData.prices.JPY) ? formData.prices.JPY[0] ?? 0 : formData.prices.JPY}
                onChange={(e) => setFormData({
                  ...formData,
                  prices: { ...formData.prices, JPY: Number(e.target.value) }
                })}
                required
              />
            </div>
          </div>

          <div className="contract-form-section">
            <h3>決済方法</h3>
            <div className="contract-form-group">
              <label>許可する決済方法</label>
              <div className="contract-tag-list">
                {formData.payment_methods.allowed?.map((method, index) => (
                  <span key={index} className="contract-tag">
                    {method}
                    <button type="button" onClick={() => removePaymentMethod('allowed', index)}>×</button>
                  </span>
                ))}
                <Button variant="ghost" size="sm" onClick={() => addPaymentMethod('allowed')}>
                  + 追加
                </Button>
              </div>
            </div>

            <div className="contract-form-group">
              <label>必須の決済方法</label>
              <div className="contract-tag-list">
                {formData.payment_methods.required?.map((method, index) => (
                  <span key={index} className="contract-tag">
                    {method}
                    <button type="button" onClick={() => removePaymentMethod('required', index)}>×</button>
                  </span>
                ))}
                <Button variant="ghost" size="sm" onClick={() => addPaymentMethod('required')}>
                  + 追加
                </Button>
              </div>
            </div>
          </div>

          <div className="contract-form-section">
            <h3>手数料</h3>
            <div className="contract-form-row">
              <div className="contract-form-group">
                <label htmlFor="fee_percentage">パーセンテージ手数料 (%)</label>
                <input
                  type="number"
                  id="fee_percentage"
                  step="0.1"
                  value={Array.isArray(formData.fees.percentage) ? formData.fees.percentage[0] ?? 0 : formData.fees.percentage ?? 0}
                  onChange={(e) => setFormData({
                    ...formData,
                    fees: { ...formData.fees, percentage: Number(e.target.value) }
                  })}
                />
              </div>

              <div className="contract-form-group">
                <label htmlFor="fee_fixed">固定手数料</label>
                <input
                  type="number"
                  id="fee_fixed"
                  value={Array.isArray(formData.fees.fixed) ? formData.fees.fixed[0] ?? 0 : formData.fees.fixed ?? 0}
                  onChange={(e) => setFormData({
                    ...formData,
                    fees: { ...formData.fees, fixed: Number(e.target.value) }
                  })}
                />
              </div>
            </div>
          </div>

          <div className="contract-form-section">
            <h3>サブスクリプション条件</h3>
            <div className="contract-form-group">
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
              <div className="contract-form-group">
                <label htmlFor="commitment_months">契約期間（月）</label>
                <input
                  type="number"
                  id="commitment_months"
                  value={Array.isArray(formData.subscription_terms?.commitment_months) ? formData.subscription_terms?.commitment_months[0] ?? 0 : formData.subscription_terms?.commitment_months || 0}
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

            <div className="contract-form-group">
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
            <div className="contract-form-error">{formError}</div>
          )}
        </form>
      </Modal>
    </div>
  );
};

export default Contracts;
