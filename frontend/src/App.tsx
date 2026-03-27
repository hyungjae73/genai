import { Component, ErrorInfo, ReactNode, lazy, Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useParams } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Customers from './pages/Customers';
import Sites from './pages/Sites';
import Alerts from './pages/Alerts';
import FakeSites from './pages/FakeSites';
import Rules from './pages/Rules';
import Contracts from './pages/Contracts';
import SiteManagement from './pages/SiteManagement';
import AuthGuard from './components/AuthGuard';
import { AppLayout } from './layouts/AppLayout';
import './App.css';

// Lazy-loaded components for performance (Req Performance.2)
const CrawlResultReviewPage = lazy(() => import('./pages/CrawlResultReview'));
const CrawlResultComparison = lazy(() => import('./components/CrawlResultComparison'));

/** Wrapper that extracts siteId from the URL and passes it to CrawlResultComparison */
function CrawlResultComparePage() {
  const { siteId } = useParams<{ siteId: string }>();
  if (!siteId) return <div>サイトIDが指定されていません</div>;
  return <CrawlResultComparison siteId={Number(siteId)} />;
}

// Error Boundary Component
class ErrorBoundary extends Component<
  { children: ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Error caught by boundary:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '20px', color: 'red' }}>
          <h1>エラーが発生しました</h1>
          <pre>{this.state.error?.message}</pre>
          <pre>{this.state.error?.stack}</pre>
        </div>
      );
    }

    return this.props.children;
  }
}

function App() {
  return (
    <ErrorBoundary>
      <Router>
        <AppLayout>
          <ErrorBoundary>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/customers" element={<Customers />} />
              <Route path="/sites" element={<Sites />} />
              <Route path="/contracts" element={<Contracts />} />
              <Route path="/site-management" element={<SiteManagement />} />
              <Route path="/hierarchy" element={<Navigate to="/site-management" replace />} />
              <Route path="/screenshots" element={<Navigate to="/site-management" replace />} />
              <Route path="/verification" element={<Navigate to="/site-management" replace />} />
              <Route path="/alerts" element={<Alerts />} />
              <Route path="/fake-sites" element={<FakeSites />} />
              <Route path="/rules" element={<Rules />} />
              <Route path="/sites/:siteId/crawl-results/:crawlResultId/review" element={<AuthGuard><Suspense fallback={<div className="loading-fallback">読み込み中...</div>}><CrawlResultReviewPage /></Suspense></AuthGuard>} />
              <Route path="/sites/:siteId/crawl-results/compare" element={<AuthGuard><Suspense fallback={<div className="loading-fallback">読み込み中...</div>}><CrawlResultComparePage /></Suspense></AuthGuard>} />
            </Routes>
          </ErrorBoundary>
        </AppLayout>
      </Router>
    </ErrorBoundary>
  );
}

export default App;
