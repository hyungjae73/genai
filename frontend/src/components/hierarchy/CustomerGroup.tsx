import { useState } from 'react';
import type { CustomerWithSites } from '../../pages/SiteManagement';
import { Badge } from '../ui/Badge/Badge';
import SiteRow from './SiteRow';

export interface CustomerGroupProps {
  customer: CustomerWithSites;
  isExpanded: boolean;
  onToggle: () => void;
  onSiteUpdate?: () => void;
}

const CustomerGroup = ({ customer, isExpanded, onToggle, onSiteUpdate }: CustomerGroupProps) => {
  const [expandedSites, setExpandedSites] = useState<Set<number>>(new Set());

  const handleSiteToggle = (siteId: number) => {
    setExpandedSites((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(siteId)) {
        newSet.delete(siteId);
      } else {
        newSet.add(siteId);
      }
      return newSet;
    });
  };

  return (
    <div className="customer-group-wrapper">
      <div
        className="customer-group-header"
        onClick={onToggle}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onToggle();
          }
        }}
      >
        <span className="expand-icon">{isExpanded ? '▼' : '▶'}</span>
        <span className="customer-name">{customer.name}</span>
        {customer.company_name && (
          <span className="company-name">({customer.company_name})</span>
        )}
        <Badge variant={customer.is_active ? 'success' : 'neutral'} size="sm">
          {customer.is_active ? '有効' : '無効'}
        </Badge>
        <span className="site-count">{customer.siteCount} サイト</span>
      </div>

      {isExpanded && (
        <div className="customer-sites">
          {customer.sites.length === 0 ? (
            <div className="no-data">監視サイトがありません</div>
          ) : (
            customer.sites.map((site) => (
              <SiteRow
                key={site.id}
                site={site}
                customerName={customer.name}
                isExpanded={expandedSites.has(site.id)}
                onToggle={() => handleSiteToggle(site.id)}
                onCrawlComplete={onSiteUpdate}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
};

export default CustomerGroup;
