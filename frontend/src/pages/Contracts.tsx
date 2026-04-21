import { useEffect, useState } from 'react';
import { getSites, getContracts, getSiteContracts, createContract, deleteContract, getCategories, getFieldSchemas, type Site, type ContractCondition, type ContractConditionCreate, type Category, type FieldSchema } from '../services/api';
import { Select } from '../components/ui/Select/Select';
import { Card } from '../components/ui/Card/Card';
import { Modal } from '../components/ui/Modal/Modal';
import { Badge } from '../components/ui/Badge/Badge';
import { Button } from '../components/ui/Button/Button';
import { HelpButton } from '../components/ui/HelpButton/HelpButton';
import DynamicFieldInput from '../components/contract/DynamicFieldInput';
import { validateDynamicField } from '../components/contract/validateDynamicField';
import './Contracts.css';

const Contracts = () => {
  const [sites, setSites] = useState<Site[]>([]);
  const [contracts, setContracts] = useState<ContractCondition[]>([]);
  const [selectedSite, setSelectedSite] = useState<number | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal state
  const [showModal, setShowModal] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Dynamic form state (tasks 6.1–6.3)
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null);
  const [fieldSchemas, setFieldSchemas] = useState<FieldSchema[]>([]);
  const [dynamicFields, setDynamicFields] = useState<Record<string, unknown>>({});
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

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
      const [sitesData, contractsData, categoriesData] = await Promise.all([
        getSites(),
        getContracts(),
        getCategories(),
      ]);
      setSites(sitesData);
      setContracts(contractsData);
      setCategories(categoriesData);
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

  // Task 6.2: handle category change — fetch schemas, clear dynamic state
  const handleCategoryChange = async (categoryId: number | null) => {
    setSelectedCategoryId(categoryId);
    setDynamicFields({});
    setFieldErrors({});
    if (categoryId) {
      try {
        const schemas = await getFieldSchemas(categoryId);
        setFieldSchemas(schemas.sort((a, b) => a.display_order - b.display_order));
      } catch (err) {
        console.error('Failed to fetch field schemas:', err);
        setFieldSchemas([]);
      }
    } else {
      setFieldSchemas([]);
    }
  };

  // Task 6.3: handle dynamic field change with validation
  const handleDynamicFieldChange = (fieldName: string, value: unknown) => {
    const updated = { ...dynamicFields, [fieldName]: value };
    setDynamicFields(updated);

    const schema = fieldSchemas.find(s => s.field_name === fieldName);
    if (schema) {
      const err = validateDynamicField(schema, value);
      setFieldErrors(prev => {
        const next = { ...prev };
        if (err) {
          next[fieldName] = err;
        } else {
          delete next[fieldName];
        }
        return next;
      });
    }
  };

  const hasDynamicFieldErrors = Object.keys(fieldErrors).some(k => fieldErrors[k]);

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
    setSelectedCategoryId(null);
    setFieldSchemas([]);
    setDynamicFields({});
    setFieldErrors({});
    setFormError(null);
    setShowModal(true);
  };

  // Task 6.5: open edit modal with pre-filled dynamic fields
  const openEditModal = (contract: ContractCondition) => {
    setFormData({
      site_id: contract.site_id,
      prices: contract.prices,
      payment_methods: contract.payment_methods,
      fees: contract.fees,
      subscription_terms: contract.subscription_terms,
    });
    setDynamicFields(contract.dynamic_fields ?? {});
    setFieldErrors({});
    setFormError(null);
    setShowModal(true);
    // Load schemas for the contract's category
    handleCategoryChange(contract.category_id ?? null);
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

      // Task 6.4: include dynamic_fields and category_id in payload
      const payload: ContractConditionCreate = {
        ...formData,
        dynamic_fields: dynamicFields,
        category_id: selectedCategoryId ?? undefined,
      };

      await createContract(payload);
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
        disabled={submitting || hasDynamicFieldErrors}
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
        <h1>契約条件管理 <HelpButton title="このページの使い方">
          <div className="help-content">
            <h3>できること</h3>
            <ul>
              <li>サイトごとの契約条件（価格・決済方法・手数料・サブスク条件）を登録</li>
              <li>サイトフィルターで特定サイトの契約を絞り込み</li>
              <li>契約のバージョン履歴を確認</li>
            </ul>

            <h3>設定項目</h3>
            <ul>
              <li><strong>価格</strong> — 通貨ごとの基準価格</li>
              <li><strong>決済方法</strong> — 許可/必須の決済方法</li>
              <li><strong>手数料</strong> — パーセンテージ・固定手数料</li>
              <li><strong>サブスク条件</strong> — 契約期間・解約ポリシー</li>
            </ul>

            <div className="help-tip">「現在」バッジの契約が監視基準です。違反検出はこの条件に基づいて行われます。</div>
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
                    variant="ghost"
                    size="sm"
                    onClick={() => openEditModal(contract)}
                    aria-label="編集"
                  >
                    編集
                  </Button>
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

                {/* Task 6.6: display dynamic_fields in contract cards */}
                {contract.dynamic_fields && Object.keys(contract.dynamic_fields).length > 0 && (
                  <div className="detail-section">
                    <h4>追加フィールド</h4>
                    {Object.entries(contract.dynamic_fields).map(([key, val]) => (
                      <div key={key} className="contract-dynamic-field">
                        <span className="contract-dynamic-field__label">{key}:</span>
                        <span className="contract-dynamic-field__value">{String(val)}</span>
                      </div>
                    ))}
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

          {/* Task 6.1: category select */}
          <div className="contract-form-group">
            <Select
              label="カテゴリ"
              value={selectedCategoryId ? String(selectedCategoryId) : ''}
              onChange={(val) => handleCategoryChange(val ? Number(val) : null)}
              options={[
                { value: '', label: 'カテゴリを選択（任意）' },
                ...categories.map(cat => ({ value: String(cat.id), label: cat.name })),
              ]}
              aria-label="カテゴリ選択"
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

          {/* Task 6.2: render dynamic fields in display_order */}
          {fieldSchemas.length > 0 && (
            <div className="contract-form-section">
              <h3>追加フィールド</h3>
              {fieldSchemas.map(schema => (
                <div key={schema.id} className="contract-form-group">
                  <DynamicFieldInput
                    schema={schema}
                    value={dynamicFields[schema.field_name]}
                    onChange={handleDynamicFieldChange}
                    error={fieldErrors[schema.field_name]}
                  />
                </div>
              ))}
            </div>
          )}

          {formError && (
            <div className="contract-form-error">{formError}</div>
          )}
        </form>
      </Modal>
    </div>
  );
};

export default Contracts;
