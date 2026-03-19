import { useEffect, useState } from 'react';
import {
  getCustomers,
  getSites,
  getCategories,
  type Customer,
  type Site,
  type Category,
} from '../services/api';
import CustomerGroup from '../components/hierarchy/CustomerGroup';

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

const HierarchyView = () => {
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

  if (loading) {
    return <div className="loading">読み込み中...</div>;
  }

  if (error) {
    return <div className="error">{error}</div>;
  }

  return (
    <div className="hierarchy-view">
      <div className="page-header">
        <h1>階層型ビュー</h1>
      </div>

      <div className="filters">
        <input
          type="text"
          placeholder="顧客名・会社名で検索..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="search-input"
        />

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as 'all' | 'active' | 'inactive')}
          className="status-filter"
        >
          <option value="all">すべてのステータス</option>
          <option value="active">有効</option>
          <option value="inactive">無効</option>
        </select>

        <select
          value={categoryFilter ?? ''}
          onChange={(e) =>
            setCategoryFilter(e.target.value ? Number(e.target.value) : null)
          }
          className="status-filter"
        >
          <option value="">すべてのカテゴリ</option>
          {categories.map((cat) => (
            <option key={cat.id} value={cat.id}>
              {cat.name}
            </option>
          ))}
        </select>
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

export default HierarchyView;
