import { useEffect, useState } from 'react';
import {
  getCustomers,
  getSites,
  getCategories,
  type Customer,
  type Site,
  type Category,
} from '../services/api';
import { Input } from '../components/ui/Input/Input';
import { Select } from '../components/ui/Select/Select';
import CustomerGroup from '../components/hierarchy/CustomerGroup';
import { HelpButton } from '../components/ui/HelpButton/HelpButton';
import './SiteManagement.css';

// --- Exported interfaces ---

export interface CustomerWithSites extends Customer {
  sites: Site[];
  siteCount: number;
}

// --- Exported pure logic functions (for property testing) ---

export function groupSitesByCustomer(
  customers: Customer[],
  sites: Site[]
): CustomerWithSites[] {
  const sitesByCustomer = new Map<number, Site[]>();
  for (const site of sites) {
    const list = sitesByCustomer.get(site.customer_id) || [];
    list.push(site);
    sitesByCustomer.set(site.customer_id, list);
  }
  return customers.map((customer) => ({
    ...customer,
    sites: sitesByCustomer.get(customer.id) || [],
    siteCount: (sitesByCustomer.get(customer.id) || []).length,
  }));
}

export function filterCustomers(
  customers: CustomerWithSites[],
  searchQuery: string,
  statusFilter: 'all' | 'active' | 'inactive',
  categoryFilter: number | null
): CustomerWithSites[] {
  return customers.filter((customer) => {
    // Search filter: case-insensitive partial match on name or company_name
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const nameMatch = customer.name.toLowerCase().includes(q);
      const companyMatch = customer.company_name
        ? customer.company_name.toLowerCase().includes(q)
        : false;
      if (!nameMatch && !companyMatch) return false;
    }

    // Status filter
    if (statusFilter === 'active' && !customer.is_active) return false;
    if (statusFilter === 'inactive' && customer.is_active) return false;

    // Category filter: customer passes if at least one of its sites has the category
    if (categoryFilter !== null) {
      const hasCategorySite = customer.sites.some(
        (site) => site.category_id === categoryFilter
      );
      if (!hasCategorySite) return false;
    }

    return true;
  });
}

// --- Main component ---

const SiteManagement = () => {
  const [customers, setCustomers] = useState<CustomerWithSites[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [categoryFilter, setCategoryFilter] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedCustomers, setExpandedCustomers] = useState<Set<number>>(new Set());

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [customersData, sitesData, categoriesData] = await Promise.all([
        getCustomers(),
        getSites(),
        getCategories(),
      ]);
      const grouped = groupSitesByCustomer(customersData, sitesData);
      setCustomers(grouped);
      setCategories(categoriesData);
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

  const filtered = filterCustomers(customers, searchQuery, statusFilter, categoryFilter);

  const toggleCustomer = (customerId: number) => {
    setExpandedCustomers((prev) => {
      const next = new Set(prev);
      if (next.has(customerId)) {
        next.delete(customerId);
      } else {
        next.add(customerId);
      }
      return next;
    });
  };

  const statusOptions = [
    { value: 'all', label: 'すべてのステータス' },
    { value: 'active', label: '有効' },
    { value: 'inactive', label: '無効' },
  ];

  const categoryOptions = [
    { value: '', label: 'すべてのカテゴリ' },
    ...categories.map((cat) => ({ value: String(cat.id), label: cat.name })),
  ];

  if (loading) {
    return <div className="loading">読み込み中...</div>;
  }

  if (error) {
    return <div className="error">{error}</div>;
  }

  return (
    <div className="site-management">
      <div className="page-header">
        <h1>サイト管理 <HelpButton title="サイト管理の使い方">
          <div className="help-content">
            <h3>できること</h3>
            <ul>
              <li>顧客→サイトの階層構造でサイトを管理</li>
              <li>顧客名クリックでサイト一覧を展開</li>
              <li>サイト展開で詳細タブにアクセス</li>
            </ul>

            <h3>詳細タブ</h3>
            <ul>
              <li><strong>契約条件</strong> — 契約内容の確認・編集</li>
              <li><strong>スクリーンショット</strong> — ベースライン画像の管理</li>
              <li><strong>検証・比較</strong> — 検証実行と結果確認</li>
              <li><strong>アラート</strong> — 違反アラートの確認</li>
            </ul>

            <div className="help-tip">ベースラインは1サイト1枚です。再キャプチャで上書きされます。</div>
          </div>
        </HelpButton></h1>
      </div>

      <div className="filters">
        <Input
          label="検索"
          type="search"
          placeholder="顧客名・会社名で検索..."
          value={searchQuery}
          onChange={setSearchQuery}
        />

        <Select
          label="ステータス"
          value={statusFilter}
          onChange={(val) => setStatusFilter(val as 'all' | 'active' | 'inactive')}
          options={statusOptions}
          aria-label="ステータスフィルター"
        />

        <Select
          label="カテゴリ"
          value={categoryFilter !== null ? String(categoryFilter) : ''}
          onChange={(val) => setCategoryFilter(val ? Number(val) : null)}
          options={categoryOptions}
          aria-label="カテゴリフィルター"
        />
      </div>

      <div className="hierarchy-list">
        {filtered.length === 0 ? (
          <div className="no-data">該当する顧客がありません</div>
        ) : (
          filtered.map((customer) => (
            <CustomerGroup
              key={customer.id}
              customer={customer}
              isExpanded={expandedCustomers.has(customer.id)}
              onToggle={() => toggleCustomer(customer.id)}
              onSiteUpdate={fetchData}
            />
          ))
        )}
      </div>
    </div>
  );
};

export default SiteManagement;
