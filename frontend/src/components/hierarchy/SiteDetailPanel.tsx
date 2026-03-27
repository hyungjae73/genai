import { useState } from 'react';
import { Link } from 'react-router-dom';
import ContractTab from './tabs/ContractTab';
import ScreenshotTab from './tabs/ScreenshotTab';
import VerificationTab from './tabs/VerificationTab';
import AlertTab from './tabs/AlertTab';
import ScheduleTab from './tabs/ScheduleTab';

export interface SiteDetailPanelProps {
  siteId: number;
  customerName: string;
}

export type TabType = 'contracts' | 'screenshots' | 'verification' | 'alerts' | 'schedule';

const SiteDetailPanel = ({ siteId, customerName }: SiteDetailPanelProps) => {
  const [activeTab, setActiveTab] = useState<TabType>('contracts');
  const [loadedTabs, setLoadedTabs] = useState<Set<TabType>>(new Set(['contracts']));

  const handleTabChange = (tab: TabType) => {
    setActiveTab(tab);
    // Mark tab as loaded when it's selected
    if (!loadedTabs.has(tab)) {
      setLoadedTabs((prev) => new Set([...prev, tab]));
    }
  };

  const getTabLabel = (tab: TabType): string => {
    const labels: Record<TabType, string> = {
      contracts: '契約条件',
      screenshots: 'スクリーンショット',
      verification: '検証・比較',
      alerts: 'アラート',
      schedule: 'スケジュール',
    };
    return labels[tab];
  };

  const tabs: TabType[] = ['contracts', 'screenshots', 'verification', 'alerts', 'schedule'];

  return (
    <div className="site-detail-panel">
      <div className="tab-navigation">
        {tabs.map((tab) => (
          <button
            key={tab}
            className={`tab-button ${activeTab === tab ? 'active' : ''}`}
            onClick={() => handleTabChange(tab)}
          >
            {getTabLabel(tab)}
          </button>
        ))}
        <Link
          to={`/sites/${siteId}/crawl-results/compare`}
          className="tab-button"
          style={{ textDecoration: 'none' }}
        >
          クロール結果比較
        </Link>
      </div>

      <div className="tab-content">
        {activeTab === 'contracts' && loadedTabs.has('contracts') && (
          <ContractTab siteId={siteId} />
        )}
        {activeTab === 'screenshots' && loadedTabs.has('screenshots') && (
          <ScreenshotTab siteId={siteId} />
        )}
        {activeTab === 'verification' && loadedTabs.has('verification') && (
          <VerificationTab siteId={siteId} />
        )}
        {activeTab === 'alerts' && loadedTabs.has('alerts') && (
          <AlertTab siteId={siteId} customerName={customerName} />
        )}
        {activeTab === 'schedule' && loadedTabs.has('schedule') && (
          <ScheduleTab siteId={siteId} />
        )}
      </div>
    </div>
  );
};

export default SiteDetailPanel;
