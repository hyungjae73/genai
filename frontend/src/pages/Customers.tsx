import { useEffect, useState } from 'react';
import { getCustomers, createCustomer, updateCustomer, deleteCustomer, type Customer, type CustomerCreate } from '../services/api';
import { Table, type TableColumn } from '../components/ui/Table/Table';
import { Badge } from '../components/ui/Badge/Badge';
import { Button } from '../components/ui/Button/Button';
import { Select } from '../components/ui/Select/Select';
import { Input } from '../components/ui/Input/Input';
import { Modal } from '../components/ui/Modal/Modal';
import { HelpButton } from '../components/ui/HelpButton/HelpButton';
import './Customers.css';

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

  const columns: TableColumn<Record<string, unknown>>[] = [
    { key: 'name', header: '顧客名' },
    {
      key: 'company_name',
      header: '会社名',
      render: (row) => (row.company_name as string) || '-',
    },
    { key: 'email', header: 'メールアドレス' },
    {
      key: 'phone',
      header: '電話番号',
      render: (row) => (row.phone as string) || '-',
    },
    {
      key: 'is_active',
      header: 'ステータス',
      render: (row) => (
        <Badge variant={row.is_active ? 'success' : 'neutral'}>
          {row.is_active ? '有効' : '無効'}
        </Badge>
      ),
    },
    {
      key: 'created_at',
      header: '登録日',
      render: (row) => new Date(row.created_at as string).toLocaleDateString('ja-JP'),
    },
    {
      key: 'actions',
      header: '操作',
      render: (row) => {
        const customer = row as unknown as Customer;
        return (
          <div className="action-buttons">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => openEditModal(customer)}
              aria-label="編集"
            >
              編集
            </Button>
            <Button
              variant="danger"
              size="sm"
              onClick={() => handleDelete(customer)}
              aria-label="削除"
            >
              削除
            </Button>
          </div>
        );
      },
    },
  ];

  const tableData = filteredCustomers.map((c) => c as unknown as Record<string, unknown>);

  if (loading) {
    return <div className="loading">読み込み中...</div>;
  }

  if (error) {
    return <div className="error">{error}</div>;
  }

  const modalFooter = (
    <div className="customer-modal-footer">
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
          const form = document.getElementById('customer-form') as HTMLFormElement;
          form?.requestSubmit();
        }}
      >
        {modalMode === 'create' ? '登録' : '更新'}
      </Button>
    </div>
  );

  return (
    <div className="customers">
      <div className="page-header">
        <h1>顧客マスター <HelpButton title="顧客マスターの使い方">
          <div className="help-content">
            <h3>ユーザーストーリー</h3>
            <p>顧客情報を登録・管理し、サイトとの紐付けの基盤を整備したい</p>

            <h3>検索</h3>
            <p>顧客名・会社名・メールアドレスで検索できます。検索ボックスにキーワードを入力すると、リアルタイムで絞り込まれます。</p>

            <h3>ステータスフィルター</h3>
            <p>ステータスフィルターで有効/無効を切り替えて表示できます。「すべてのステータス」を選択するとすべての顧客が表示されます。</p>

            <h3>新規登録・編集・削除</h3>
            <p>「新規顧客登録」ボタンで新しい顧客を登録できます。一覧の「編集」ボタンで顧客情報を更新、「削除」ボタンで顧客を削除できます。</p>

            <h3>無効化時の監視継続</h3>
            <p>顧客を無効にしても、関連サイトの監視は継続されます。無効化は顧客の管理状態を示すもので、監視の停止とは異なります。</p>
          </div>
        </HelpButton></h1>
        <Button variant="primary" size="md" onClick={openCreateModal}>
          + 新規顧客登録
        </Button>
      </div>

      <div className="filters">
        <Input
          label="検索"
          type="search"
          value={searchTerm}
          onChange={setSearchTerm}
          placeholder="顧客名、会社名、メールアドレスで検索..."
        />
        <Select
          label="ステータス"
          value={statusFilter}
          onChange={setStatusFilter}
          options={[
            { value: 'all', label: 'すべてのステータス' },
            { value: 'active', label: '有効' },
            { value: 'inactive', label: '無効' },
          ]}
          aria-label="ステータスフィルター"
        />
      </div>

      <Table
        columns={columns}
        data={tableData}
        mobileLayout="card"
        emptyMessage="該当する顧客がありません"
        aria-label="顧客一覧"
      />

      <Modal
        isOpen={showModal}
        onClose={closeModal}
        title={modalMode === 'create' ? '新規顧客登録' : '顧客編集'}
        size="md"
        footer={modalFooter}
      >
        <form id="customer-form" onSubmit={handleSubmit}>
          <div className="customer-form-group">
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

          <div className="customer-form-group">
            <label htmlFor="company_name">会社名</label>
            <input
              type="text"
              id="company_name"
              value={formData.company_name || ''}
              onChange={(e) => setFormData({ ...formData, company_name: e.target.value })}
              placeholder="例: 株式会社サンプル"
            />
          </div>

          <div className="customer-form-group">
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

          <div className="customer-form-group">
            <label htmlFor="phone">電話番号</label>
            <input
              type="tel"
              id="phone"
              value={formData.phone || ''}
              onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
              placeholder="例: 03-1234-5678"
            />
          </div>

          <div className="customer-form-group">
            <label htmlFor="address">住所</label>
            <textarea
              id="address"
              value={formData.address || ''}
              onChange={(e) => setFormData({ ...formData, address: e.target.value })}
              placeholder="例: 東京都渋谷区..."
              rows={3}
            />
          </div>

          <div className="customer-form-group">
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
            <div className="customer-form-error">{formError}</div>
          )}
        </form>
      </Modal>
    </div>
  );
};

export default Customers;
