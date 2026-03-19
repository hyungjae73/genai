import { useState } from 'react';

interface ComplianceRule {
  id: string;
  category: string;
  name: string;
  description: string;
  severity: 'low' | 'medium' | 'high';
  enabled: boolean;
  checkPoints: string[];
}

const Rules = () => {
  const [rules] = useState<ComplianceRule[]>([
    {
      id: 'price-validation',
      category: '価格チェック',
      name: '契約価格との一致',
      description: '表示されている価格が契約で合意した価格と一致しているか確認します',
      severity: 'high',
      enabled: true,
      checkPoints: [
        '各通貨の価格が契約価格と一致しているか',
        '価格の許容誤差範囲内であるか',
        '必須通貨の価格が表示されているか',
      ],
    },
    {
      id: 'payment-method-validation',
      category: '決済方法チェック',
      name: '許可された決済方法',
      description: '契約で許可された決済方法のみが提供されているか確認します',
      severity: 'medium',
      enabled: true,
      checkPoints: [
        '許可されていない決済方法が表示されていないか',
        '必須の決済方法が提供されているか',
        '決済方法の表示が適切か',
      ],
    },
    {
      id: 'fee-validation',
      category: '手数料チェック',
      name: '手数料の妥当性',
      description: '表示されている手数料が契約条件と一致しているか確認します',
      severity: 'medium',
      enabled: true,
      checkPoints: [
        'パーセンテージ手数料が契約と一致しているか',
        '固定手数料が契約と一致しているか',
        '手数料の表示が明確か',
      ],
    },
    {
      id: 'subscription-validation',
      category: 'サブスクリプションチェック',
      name: 'サブスクリプション条件',
      description: 'サブスクリプションの契約条件が正しく表示されているか確認します',
      severity: 'high',
      enabled: true,
      checkPoints: [
        '契約期間の縛りが正しく表示されているか',
        '解約ポリシーが明記されているか',
        '自動更新の条件が明確か',
        '契約期間（月数）が契約と一致しているか',
      ],
    },
    {
      id: 'transparency-check',
      category: '透明性チェック',
      name: '情報の透明性',
      description: '重要な決済情報が明確に表示されているか確認します',
      severity: 'medium',
      enabled: true,
      checkPoints: [
        '価格が明確に表示されているか',
        '追加費用が事前に開示されているか',
        '返金ポリシーが明記されているか',
      ],
    },
  ]);

  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [expandedRule, setExpandedRule] = useState<string | null>(null);

  const categories = ['all', ...Array.from(new Set(rules.map(r => r.category)))];

  const filteredRules = selectedCategory === 'all' 
    ? rules 
    : rules.filter(r => r.category === selectedCategory);

  const getSeverityBadge = (severity: string) => {
    const severityMap: Record<string, { label: string; className: string }> = {
      low: { label: '低', className: 'severity-low' },
      medium: { label: '中', className: 'severity-medium' },
      high: { label: '高', className: 'severity-high' },
    };
    const severityInfo = severityMap[severity] || { label: severity, className: '' };
    return <span className={`severity-badge ${severityInfo.className}`}>{severityInfo.label}</span>;
  };

  const toggleExpand = (ruleId: string) => {
    setExpandedRule(expandedRule === ruleId ? null : ruleId);
  };

  return (
    <div className="rules">
      <div className="page-header">
        <h1>コンプライアンスチェックルール</h1>
        <p className="page-description">
          監視システムが確認している項目の一覧です
        </p>
      </div>

      <div className="filters">
        <select
          value={selectedCategory}
          onChange={(e) => setSelectedCategory(e.target.value)}
          className="category-filter"
        >
          <option value="all">すべてのカテゴリ</option>
          {categories.filter(c => c !== 'all').map(category => (
            <option key={category} value={category}>{category}</option>
          ))}
        </select>
      </div>

      <div className="rules-list">
        {filteredRules.map(rule => (
          <div key={rule.id} className="rule-card">
            <div className="rule-header" onClick={() => toggleExpand(rule.id)}>
              <div className="rule-title-section">
                <h3>{rule.name}</h3>
                <span className="rule-category">{rule.category}</span>
              </div>
              <div className="rule-meta">
                {getSeverityBadge(rule.severity)}
                <span className={`status-badge ${rule.enabled ? 'status-enabled' : 'status-disabled'}`}>
                  {rule.enabled ? '有効' : '無効'}
                </span>
                <button className="expand-btn">
                  {expandedRule === rule.id ? '▼' : '▶'}
                </button>
              </div>
            </div>

            <p className="rule-description">{rule.description}</p>

            {expandedRule === rule.id && (
              <div className="rule-details">
                <h4>チェックポイント:</h4>
                <ul className="checkpoint-list">
                  {rule.checkPoints.map((point, index) => (
                    <li key={index}>
                      <span className="checkpoint-icon">✓</span>
                      {point}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
      </div>

      {filteredRules.length === 0 && (
        <div className="no-data">該当するルールがありません</div>
      )}
    </div>
  );
};

export default Rules;
