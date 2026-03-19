import { Component, ErrorInfo, ReactNode, lazy, Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useParams } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Customers from './pages/Customers';
import Sites from './pages/Sites';
import Alerts from './pages/Alerts';
import Rules from './pages/Rules';
import Contracts from './pages/Contracts';
import Screenshots from './pages/Screenshots';
import Verification from './pages/Verification';
import HierarchyView from './pages/HierarchyView';
import AuthGuard from './components/AuthGuard';
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
        <div className="app">
          <nav className="navbar">
            <div className="nav-brand">
              <h2>決済条件監視システム</h2>
            </div>
            <ul className="nav-links">
              <li><Link to="/">ダッシュボード</Link></li>
              <li><Link to="/customers">顧客</Link></li>
              <li><Link to="/sites">監視サイト</Link></li>
              <li><Link to="/hierarchy">階層型ビュー</Link></li>
              <li><Link to="/contracts">契約条件</Link></li>
              <li><Link to="/screenshots">スクリーンショット</Link></li>
              <li><Link to="/verification">検証・比較</Link></li>
              <li><Link to="/alerts">アラート</Link></li>
              <li><Link to="/rules">チェックルール</Link></li>
            </ul>
          </nav>

          <main className="main-content">
            <ErrorBoundary>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/customers" element={<Customers />} />
                <Route path="/sites" element={<Sites />} />
                <Route path="/contracts" element={<Contracts />} />
                <Route path="/screenshots" element={<Screenshots />} />
                <Route path="/verification" element={<Verification />} />
                <Route path="/alerts" element={<Alerts />} />
                <Route path="/rules" element={<Rules />} />
                <Route path="/hierarchy" element={<HierarchyView />} />
                <Route path="/sites/:siteId/crawl-results/:crawlResultId/review" element={<AuthGuard><Suspense fallback={<div className="loading-fallback">読み込み中...</div>}><CrawlResultReviewPage /></Suspense></AuthGuard>} />
                <Route path="/sites/:siteId/crawl-results/compare" element={<AuthGuard><Suspense fallback={<div className="loading-fallback">読み込み中...</div>}><CrawlResultComparePage /></Suspense></AuthGuard>} />
              </Routes>
            </ErrorBoundary>
          </main>
        </div>
      </Router>
    </ErrorBoundary>
  );
}

export default App;
