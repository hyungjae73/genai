import { useEffect, useState } from 'react';
import { getCustomers, createCustomer, updateCustomer, deleteCustomer, type Customer, type CustomerCreate } from '../services/api';

const Customers = () => {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  
  // Modal state
  const [showModal, setShowModal] = useState(false);
  const [modalMode, setModalMode] = useState<'create' | 'edit'>('create');
  const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null);
  const [formData, setFormData] = useState<CustomerCreate>({
    name: '',
    company_name: '',
    email: '',
    phone: '',
    address: '',
    is_active: true,
  });
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const fetchCustomers = async () => {
    try {
      setLoading(true);
      const data = await getCustomers(false);
      setCustomers(data);
      setError(null);
    } catch (err) {
      setError('顧客一覧の取得に失敗しました');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCustomers();
  }, []);

  const filteredCustomers = customers.filter(customer => {
    const matchesSearch = 
      customer.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (customer.company_name && customer.company_name.toLowerCase().includes(searchTerm.toLowerCase())) ||
      customer.email.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'all' || 
      (statusFilter === 'active' && customer.is_active) ||
      (statusFilter === 'inactive' && !customer.is_active);
    return matchesSearch && matchesStatus;
  });

  const openCreateModal = () => {
    setModalMode('create');
    setEditingCustomer(null);
    setFormData({
      name: '',
      company_name: '',
      email: '',
      phone: '',
      address: '',
      is_active: true,
    });
    setFormError(null);
    setShowModal(true);
  };

  const openEditModal = (customer: Customer) => {
    setModalMode('edit');
    setEditingCustomer(customer);
    setFormData({
      name: customer.name,
      company_name: customer.company_name || '',
      email: customer.email,
      phone: customer.phone || '',
      address: customer.address || '',
      is_active: customer.is_active,
    });
    setFormError(null);
    setShowModal(true);
  };

  const closeModal = () => {
    setShowModal(false);
    setEditingCustomer(null);
    setFormData({
      name: '',
      company_name: '',
      email: '',
      phone: '',
      address: '',
      is_active: true,
    });
    setFormError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setSubmitting(true);

    try {
      // Validation
      if (!formData.name.trim()) {
        setFormError('顧客名を入力してください');
        setSubmitting(false);
        return;
      }
      if (!formData.email.trim()) {
        setFormError('メールアドレスを入力してください');
        setSubmitting(false);
        return;
      }
      
      // Email validation
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(formData.email)) {
        setFormError('有効なメールアドレスを入力してください');
        setSubmitting(false);
        return;
      }

      if (modalMode === 'create') {
        await createCustomer(formData);
      } else if (editingCustomer) {
        await updateCustomer(editingCustomer.id, formData);
      }

      await fetchCustomers();
      closeModal();
    } catch (err: any) {
      setFormError(err.response?.data?.detail || 'エラーが発生しました');
      console.error(err);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (customer: Customer) => {
    if (!confirm(`「${customer.name}」を削除してもよろしいですか？`)) {
      return;
    }

    try {
      await deleteCustomer(customer.id);
      await fetchCustomers();
    } catch (err: any) {
      alert(err.response?.data?.detail || '削除に失敗しました');
      console.error(err);
    }
  };

  if (loading) {
    return <div className="loading">読み込み中...</div>;
  }

  if (error) {
    return <div className="error">{error}</div>;
  }

  return (
    <div className="customers">
      <div className="page-header">
        <h1>顧客マスター</h1>
        <button className="btn btn-primary" onClick={openCreateModal}>
          + 新規顧客登録
        </button>
      </div>
      
      <div className="filters">
        <input
          type="text"
          placeholder="顧客名、会社名、メールアドレスで検索..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="search-input"
        />
        
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="status-filter"
        >
          <option value="all">すべてのステータス</option>
          <option value="active">有効</option>
          <option value="inactive">無効</option>
        </select>
      </div>

      <div className="customers-table">
        <table>
          <thead>
            <tr>
              <th>顧客名</th>
              <th>会社名</th>
              <th>メールアドレス</th>
              <th>電話番号</th>
              <th>ステータス</th>
              <th>登録日</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {filteredCustomers.map(customer => (
              <tr key={customer.id}>
                <td>{customer.name}</td>
                <td>{customer.company_name || '-'}</td>
                <td>{customer.email}</td>
                <td>{customer.phone || '-'}</td>
                <td>
                  <span className={customer.is_active ? 'badge-active' : 'badge-inactive'}>
                    {customer.is_active ? '有効' : '無効'}
                  </span>
                </td>
                <td>{new Date(customer.created_at).toLocaleDateString('ja-JP')}</td>
                <td>
                  <div className="action-buttons">
                    <button 
                      className="btn btn-sm btn-secondary" 
                      onClick={() => openEditModal(customer)}
                      title="編集"
                    >
                      編集
                    </button>
                    <button 
                      className="btn btn-sm btn-danger" 
                      onClick={() => handleDelete(customer)}
                      title="削除"
                    >
                      削除
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        
        {filteredCustomers.length === 0 && (
          <div className="no-data">該当する顧客がありません</div>
        )}
      </div>

      {/* Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{modalMode === 'create' ? '新規顧客登録' : '顧客編集'}</h2>
              <button className="modal-close" onClick={closeModal}>×</button>
            </div>
            
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label htmlFor="name">顧客名 *</label>
                <input
                  type="text"
                  id="name"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="例: 山田太郎"
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="company_name">会社名</label>
                <input
                  type="text"
                  id="company_name"
                  value={formData.company_name || ''}
                  onChange={(e) => setFormData({ ...formData, company_name: e.target.value })}
                  placeholder="例: 株式会社サンプル"
                />
              </div>

              <div className="form-group">
                <label htmlFor="email">メールアドレス *</label>
                <input
                  type="email"
                  id="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  placeholder="例: example@example.com"
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="phone">電話番号</label>
                <input
                  type="tel"
                  id="phone"
                  value={formData.phone || ''}
                  onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                  placeholder="例: 03-1234-5678"
                />
              </div>

              <div className="form-group">
                <label htmlFor="address">住所</label>
                <textarea
                  id="address"
                  value={formData.address || ''}
                  onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                  placeholder="例: 東京都渋谷区..."
                  rows={3}
                />
              </div>

              <div className="form-group">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={formData.is_active}
                    onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                  />
                  <span>有効</span>
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
    </div>
  );
};

export default Customers;
