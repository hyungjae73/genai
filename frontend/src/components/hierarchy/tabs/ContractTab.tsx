import { useState, useEffect } from 'react';
import { getSiteContracts, getCategories } from '../../../services/api';
import type { ContractCondition, Category } from '../../../services/api';

export interface ContractTabProps {
  siteId: number;
}

export interface GroupedContracts {
  categoryId: number | null;
  categoryName: string;
  contracts: ContractCondition[];
}

/**
 * Groups contracts by category_id.
 * Pure function for testing purposes.
 * 
 * @param contracts - Array of contract conditions to group
 * @param categories - Array of available categories
 * @returns Array of grouped contracts by category
 */
export const groupContractsByCategory = (
  contracts: ContractCondition[],
  categories: Category[]
): GroupedContracts[] => {
  const groups = new Map<number | null, GroupedContracts>();
  
  contracts.forEach((contract) => {
    const categoryId = contract.category_id ?? null;
    
    if (!groups.has(categoryId)) {
      const category = categoryId !== null 
        ? categories.find(c => c.id === categoryId)
        : null;
      
      groups.set(categoryId, {
        categoryId,
        categoryName: category?.name ?? '未分類',
        contracts: []
      });
    }
    
    groups.get(categoryId)!.contracts.push(contract);
  });
  
  return Array.from(groups.values());
};

const ContractTab = ({ siteId }: ContractTabProps) => {
  const [contracts, setContracts] = useState<ContractCondition[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);
        
        // Fetch contracts and categories in parallel
        const [contractsData, categoriesData] = await Promise.all([
          getSiteContracts(siteId),
          getCategories()
        ]);
        
        setContracts(contractsData);
        setCategories(categoriesData);
      } catch (err) {
        setError(err instanceof Error ? err.message : '契約条件の取得に失敗しました');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [siteId]);

  // Group contracts by category
  const groupedContracts: GroupedContracts[] = groupContractsByCategory(contracts, categories);

  if (loading) {
    return (
      <div className="tab-loading">
        <span className="spinner">⟳</span>
        <span>読み込み中...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="tab-error">
        <p>エラー: {error}</p>
      </div>
    );
  }

  if (contracts.length === 0) {
    return (
      <div className="tab-empty">
        <p>契約条件がありません</p>
      </div>
    );
  }

  return (
    <div className="contract-tab">
      {groupedContracts.map((group) => (
        <div key={group.categoryId ?? 'uncategorized'} className="contract-group">
          <h3 className="category-title">{group.categoryName}</h3>
          
          {group.contracts.map((contract) => (
            <div key={contract.id} className="contract-item">
              <div className="contract-header">
                <span className="contract-version">バージョン {contract.version}</span>
                {contract.is_current && (
                  <span className="current-badge">現在</span>
                )}
                <span className="contract-date">
                  {new Date(contract.created_at).toLocaleDateString('ja-JP')}
                </span>
              </div>
              
              <div className="contract-details">
                {/* Prices */}
                {Object.keys(contract.prices).length > 0 && (
                  <div className="contract-section">
                    <h4>価格</h4>
                    <ul>
                      {Object.entries(contract.prices).map(([currency, value]) => (
                        <li key={currency}>
                          {currency}: {Array.isArray(value) ? value.join(', ') : value}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                
                {/* Payment Methods */}
                {(contract.payment_methods.allowed || contract.payment_methods.required) && (
                  <div className="contract-section">
                    <h4>決済方法</h4>
                    {contract.payment_methods.allowed && (
                      <p>利用可能: {contract.payment_methods.allowed.join(', ')}</p>
                    )}
                    {contract.payment_methods.required && (
                      <p>必須: {contract.payment_methods.required.join(', ')}</p>
                    )}
                  </div>
                )}
                
                {/* Fees */}
                {(contract.fees.percentage !== undefined || contract.fees.fixed !== undefined) && (
                  <div className="contract-section">
                    <h4>手数料</h4>
                    {contract.fees.percentage !== undefined && (
                      <p>
                        パーセンテージ: {Array.isArray(contract.fees.percentage) 
                          ? contract.fees.percentage.join(', ') 
                          : contract.fees.percentage}%
                      </p>
                    )}
                    {contract.fees.fixed !== undefined && (
                      <p>
                        固定: {Array.isArray(contract.fees.fixed) 
                          ? contract.fees.fixed.join(', ') 
                          : contract.fees.fixed}
                      </p>
                    )}
                  </div>
                )}
                
                {/* Subscription Terms */}
                {contract.subscription_terms && (
                  <div className="contract-section">
                    <h4>サブスクリプション条件</h4>
                    {contract.subscription_terms.has_commitment !== undefined && (
                      <p>契約期間: {contract.subscription_terms.has_commitment ? 'あり' : 'なし'}</p>
                    )}
                    {contract.subscription_terms.commitment_months !== undefined && (
                      <p>
                        契約月数: {Array.isArray(contract.subscription_terms.commitment_months)
                          ? contract.subscription_terms.commitment_months.join(', ')
                          : contract.subscription_terms.commitment_months}ヶ月
                      </p>
                    )}
                    {contract.subscription_terms.has_cancellation_policy !== undefined && (
                      <p>
                        解約ポリシー: {contract.subscription_terms.has_cancellation_policy ? 'あり' : 'なし'}
                      </p>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
};

export default ContractTab;
