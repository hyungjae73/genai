import { useState } from 'react';
import type { Site } from '../../services/api';
import { triggerCrawl, getCrawlStatus, getLatestCrawlResult } from '../../services/api';
import { Badge } from '../ui/Badge/Badge';
import { Button } from '../ui/Button/Button';
import SiteDetailPanel from './SiteDetailPanel';
import CrawlResultModal from './CrawlResultModal';

export interface SiteRowProps {
  site: Site;
  customerName: string;
  isExpanded: boolean;
  onToggle: () => void;
  onCrawlComplete?: () => void;
}

const complianceToBadgeVariant = (status: string): 'success' | 'warning' | 'danger' | 'info' => {
  switch (status) {
    case 'compliant': return 'success';
    case 'violation': return 'danger';
    case 'pending': return 'warning';
    case 'error': return 'danger';
    default: return 'info';
  }
};

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
        <Badge variant={complianceToBadgeVariant(site.compliance_status)} size="sm">
          {getComplianceStatusLabel(site.compliance_status)}
        </Badge>
        <span className="last-crawl">
          {formatDate(lastCrawlDate)}
        </span>
        <Badge variant={site.is_active ? 'success' : 'neutral'} size="sm">
          {site.is_active ? '有効' : '無効'}
        </Badge>
        
        <Button
          variant="primary"
          size="sm"
          loading={isCrawling}
          disabled={isCrawling}
          onClick={handleCrawlClick as any}
          aria-label="今すぐクロール"
        >
          {isCrawling ? 'クロール中...' : '今すぐクロール'}
        </Button>
        
        {latestCrawlResultId && currentJobId && (
          <Button
            variant="secondary"
            size="sm"
            onClick={handleShowResults as any}
            aria-label="結果を表示"
          >
            結果を表示
          </Button>
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
