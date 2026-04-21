import { useState } from 'react';
import { Card } from '../components/ui/Card/Card';
import { Badge } from '../components/ui/Badge/Badge';
import { Select } from '../components/ui/Select/Select';
import { HelpButton } from '../components/ui/HelpButton/HelpButton';
import './Rules.css';

interface ComplianceRule {
  id: string;
  category: string;
  name: string;
  description: string;
  severity: 'low' | 'medium' | 'high';
  enabled: boolean;
  checkPoints: string[];
}

const severityVariantMap: Record<string, 'danger' | 'warning' | 'neutral'> = {
  high: 'danger',
  medium: 'warning',
  low: 'neutral',
};

const severityLabelMap: Record<string, string> = {
  high: '高',
  medium: '中',
  low: '低',
};

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
    {
      id: 'misleading-font-size',
      category: '視覚的欺瞞チェック',
      name: '重要文言の視認性',
      description: '定期購入・解約・手数料等の重要な購入条件が、ページ全体のフォントサイズと比較して著しく小さく表示されていないか確認します。消費者の視認性を意図的に低下させた表示を検出します。',
      severity: 'high',
      enabled: true,
      checkPoints: [
        '定期購入・自動更新の条件が適切なフォントサイズで表示されているか',
        '解約・キャンセルポリシーが視認しやすいサイズで表示されているか',
        '手数料・違約金・縛り期間の記載がページ全体と比較して著しく小さくないか',
        '重要事項・注意事項・同意文言が読みやすいサイズで表示されているか',
        '特定商取引法に基づく表記が適切なサイズで表示されているか',
      ],
    },
  ]);

  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [expandedRule, setExpandedRule] = useState<string | null>(null);

  const categories = ['all', ...Array.from(new Set(rules.map(r => r.category)))];

  const filteredRules = selectedCategory === 'all'
    ? rules
    : rules.filter(r => r.category === selectedCategory);

  const categoryOptions = categories.map(c => ({
    value: c,
    label: c === 'all' ? 'すべてのカテゴリ' : c,
  }));

  const toggleExpand = (ruleId: string) => {
    setExpandedRule(expandedRule === ruleId ? null : ruleId);
  };

  return (
    <div className="rules">
      <div className="page-header">
        <h1>コンプライアンスチェックルール <HelpButton title="チェックルールの使い方">
          <div className="help-content">
            <h3>ユーザーストーリー</h3>
            <p>監視システムがどのような項目をチェックしているか確認したい</p>

            <h3>カテゴリフィルター</h3>
            <p>カテゴリフィルターでルールを絞り込むことができます。「すべてのカテゴリ」を選択するとすべてのルールが表示されます。</p>

            <h3>重要度と有効/無効</h3>
            <p>各ルールには重要度（高/中/低）と有効/無効の状態が表示されます。重要度はルール違反時の影響度を示します。</p>

            <h3>チェックポイントの詳細</h3>
            <p>ルールを展開するとチェックポイントの詳細が表示されます。各チェックポイントは監視時に確認される具体的な項目です。</p>

            <h3>6つのカテゴリ</h3>
            <ul>
              <li><strong>価格チェック</strong>: 契約価格との一致を確認</li>
              <li><strong>決済方法チェック</strong>: 許可された決済方法の提供を確認</li>
              <li><strong>手数料チェック</strong>: 手数料の妥当性を確認</li>
              <li><strong>サブスクリプションチェック</strong>: サブスクリプション条件の表示を確認</li>
              <li><strong>透明性チェック</strong>: 重要情報の透明性を確認</li>
              <li><strong>視覚的欺瞞チェック</strong>: 定期購入・解約・手数料等の重要文言が著しく小さいフォントで表示されていないか確認</li>
            </ul>
          </div>
        </HelpButton></h1>
        <p className="page-description">
          監視システムが確認している項目の一覧です
        </p>
      </div>

      <div className="filters">
        <Select
          label="カテゴリ"
          value={selectedCategory}
          onChange={setSelectedCategory}
          options={categoryOptions}
          aria-label="カテゴリフィルター"
        />
      </div>

      <div className="rules-list">
        {filteredRules.map(rule => (
          <Card key={rule.id} hoverable>
            <div
              className="rule-header"
              role="button"
              tabIndex={0}
              onClick={() => toggleExpand(rule.id)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  toggleExpand(rule.id);
                }
              }}
            >
              <div className="rule-title-section">
                <h3>{rule.name}</h3>
                <span className="rule-category">{rule.category}</span>
              </div>
              <div className="rule-meta">
                <Badge variant={severityVariantMap[rule.severity] ?? 'neutral'} size="sm">
                  {severityLabelMap[rule.severity] ?? rule.severity}
                </Badge>
                <Badge variant={rule.enabled ? 'success' : 'neutral'} size="sm">
                  {rule.enabled ? '有効' : '無効'}
                </Badge>
                <span aria-hidden="true">{expandedRule === rule.id ? '▼' : '▶'}</span>
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
          </Card>
        ))}
      </div>

      {filteredRules.length === 0 && (
        <div className="no-data">該当するルールがありません</div>
      )}
    </div>
  );
};

export default Rules;
