import { useState } from 'react';
import type { Site } from '../../services/api';
import { triggerCrawl, getCrawlStatus, getLatestCrawlResult } from '../../services/api';
import SiteDetailPanel from './SiteDetailPanel';
import CrawlResultModal from './CrawlResultModal';

export interface SiteRowProps {
  site: Site;
  customerName: string;
  isExpanded: boolean;
  onToggle: () => void;
  onCrawlComplete?: () => void;
}

const SiteRow = ({ site, customerName, isExpanded, onToggle, onCrawlComplete }: SiteRowProps) => {
  const [isCrawling, setIsCrawling] = useState(false);
  const [crawlError, setCrawlError] = useState<string | null>(null);
  const [lastCrawlDate, setLastCrawlDate] = useState<string | null>(site.last_crawled_at);
  const [latestCrawlResultId, setLatestCrawlResultId] = useState<number | null>(null);
  const [showResultModal, setShowResultModal] = useState(false);
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);

  // Poll for crawl status
  const pollCrawlStatus = async (jobId: string) => {
    const maxAttempts = 60; // 5 minutes with 5 second intervals
    let attempts = 0;

    const poll = async () => {
      try {
        const statusResponse = await getCrawlStatus(jobId);
        
        if (statusResponse.status === 'completed') {
          setIsCrawling(false);
          setCrawlError(null);
          setCurrentJobId(jobId);
          
          // Fetch the latest crawl result to update UI
          try {
            const latestResult = await getLatestCrawlResult(site.id);
            setLastCrawlDate(latestResult.crawled_at);
            setLatestCrawlResultId(latestResult.id);
          } catch (err) {
            console.error('Failed to fetch latest crawl result:', err);
          }
          
          // Automatically show results modal
          setShowResultModal(true);
          
          // Notify parent component
          if (onCrawlComplete) {
            onCrawlComplete();
          }
          
          return;
        } else if (statusResponse.status === 'failed') {
          setIsCrawling(false);
          setCrawlError('クロールに失敗しました');
          return;
        }
        
        // Continue polling if still pending or running
        attempts++;
        if (attempts < maxAttempts) {
          setTimeout(poll, 5000); // Poll every 5 seconds
        } else {
          setIsCrawling(false);
          setCrawlError('クロールがタイムアウトしました');
        }
      } catch (err) {
        setIsCrawling(false);
        setCrawlError('クロールステータスの取得に失敗しました');
      }
    };

    poll();
  };

  const handleCrawlClick = async (e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent row expansion
    
    if (isCrawling) {
      return;
    }

    setIsCrawling(true);
    setCrawlError(null);

    try {
      const response = await triggerCrawl(site.id);
      setCurrentJobId(response.job_id);
      
      // Start polling for status
      pollCrawlStatus(response.job_id);
    } catch (err: any) {
      setIsCrawling(false);
      
      if (err.response?.status === 409) {
        setCrawlError('クロールが実行中です');
      } else {
        setCrawlError('クロールの開始に失敗しました');
      }
    }
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return '未実行';
    
    const date = new Date(dateString);
    return date.toLocaleString('ja-JP', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getComplianceStatusLabel = (status: string) => {
    const labels: Record<string, string> = {
      compliant: '準拠',
      violation: '違反',
      pending: '保留中',
      error: 'エラー'
    };
    return labels[status] || status;
  };

  const handleShowResults = (e: React.MouseEvent) => {
    e.stopPropagation();
    setShowResultModal(true);
  };

  return (
    <div className="site-row-wrapper">
      <div
        className="site-row-header"
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
        <span className="site-name">{site.name}</span>
        <span className="site-url">{site.url}</span>
        <span className="site-category">
          {site.category_id ? `カテゴリ ${site.category_id}` : '未分類'}
        </span>
        <span className={`compliance-badge compliance-${site.compliance_status}`}>
          {getComplianceStatusLabel(site.compliance_status)}
        </span>
        <span className="last-crawl">
          {formatDate(lastCrawlDate)}
        </span>
        <span className={site.is_active ? 'badge-active' : 'badge-inactive'}>
          {site.is_active ? '有効' : '無効'}
        </span>
        
        <button
          className="crawl-button"
          onClick={handleCrawlClick}
          disabled={isCrawling}
          title="今すぐクロール"
        >
          {isCrawling ? (
            <>
              <span className="spinner">⟳</span>
              クロール中...
            </>
          ) : (
            '今すぐクロール'
          )}
        </button>
        
        {latestCrawlResultId && currentJobId && (
          <button
            className="crawl-result-button"
            onClick={handleShowResults}
          >
            結果を表示
          </button>
        )}
      </div>

      {crawlError && (
        <div className="crawl-error" onClick={(e) => e.stopPropagation()}>
          {crawlError}
        </div>
      )}

      {isExpanded && (
        <div className="site-detail-panel">
          <SiteDetailPanel siteId={site.id} customerName={customerName} />
        </div>
      )}

      {showResultModal && currentJobId && (
        <CrawlResultModal
          jobId={currentJobId}
          onClose={() => setShowResultModal(false)}
        />
      )}
    </div>
  );
};

export default SiteRow;
