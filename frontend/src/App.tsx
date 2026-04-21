import { Component, lazy, Suspense } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useParams } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import Customers from './pages/Customers';
import Sites from './pages/Sites';
import Alerts from './pages/Alerts';
import FakeSites from './pages/FakeSites';
import Rules from './pages/Rules';
import Contracts from './pages/Contracts';
import SiteManagement from './pages/SiteManagement';
import Login from './pages/Login';
import ChangePassword from './pages/ChangePassword';
import Users from './pages/Users';
import Reviews from './pages/Reviews';
import ReviewDetailPage from './pages/ReviewDetail';
import ReviewDashboard from './pages/ReviewDashboard';
import Categories from './pages/Categories';
import ProtectedRoute from './components/ProtectedRoute';
import { AuthProvider } from './contexts/AuthContext';
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
        <AuthProvider>
          <Routes>
            {/* Login route — outside ProtectedRoute and AppLayout */}
            <Route path="/login" element={<Login />} />
            <Route path="/change-password" element={<ChangePassword />} />

            {/* All other routes — protected and inside AppLayout */}
            <Route
              path="/*"
              element={
                <ProtectedRoute>
                  <AppLayout>
                    <ErrorBoundary>
                      <Routes>
                        <Route path="/" element={<Dashboard />} />
                        <Route path="/customers" element={<Customers />} />
                        <Route path="/sites" element={<Sites />} />
                        <Route path="/contracts" element={<Contracts />} />
                        <Route
                          path="/categories"
                          element={
                            <ProtectedRoute requiredRoles={['admin']}>
                              <Categories />
                            </ProtectedRoute>
                          }
                        />
                        <Route path="/site-management" element={<SiteManagement />} />
                        <Route path="/hierarchy" element={<Navigate to="/site-management" replace />} />
                        <Route path="/screenshots" element={<Navigate to="/site-management" replace />} />
                        <Route path="/verification" element={<Navigate to="/site-management" replace />} />
                        <Route path="/alerts" element={<Alerts />} />
                        <Route path="/fake-sites" element={<FakeSites />} />
                        <Route path="/rules" element={<Rules />} />
                        <Route
                          path="/reviews"
                          element={
                            <ProtectedRoute requiredRoles={['reviewer', 'admin']}>
                              <Reviews />
                            </ProtectedRoute>
                          }
                        />
                        <Route
                          path="/reviews/:id"
                          element={
                            <ProtectedRoute requiredRoles={['reviewer', 'admin']}>
                              <ReviewDetailPage />
                            </ProtectedRoute>
                          }
                        />
                        <Route
                          path="/review-dashboard"
                          element={
                            <ProtectedRoute requiredRoles={['viewer', 'reviewer', 'admin']}>
                              <ReviewDashboard />
                            </ProtectedRoute>
                          }
                        />
                        <Route
                          path="/users"
                          element={
                            <ProtectedRoute requiredRoles={['admin']}>
                              <Users />
                            </ProtectedRoute>
                          }
                        />
                        <Route
                          path="/sites/:siteId/crawl-results/:crawlResultId/review"
                          element={
                            <Suspense fallback={<div className="loading-fallback">読み込み中...</div>}>
                              <CrawlResultReviewPage />
                            </Suspense>
                          }
                        />
                        <Route
                          path="/sites/:siteId/crawl-results/compare"
                          element={
                            <Suspense fallback={<div className="loading-fallback">読み込み中...</div>}>
                              <CrawlResultComparePage />
                            </Suspense>
                          }
                        />
                      </Routes>
                    </ErrorBoundary>
                  </AppLayout>
                </ProtectedRoute>
              }
            />
          </Routes>
        </AuthProvider>
      </Router>
    </ErrorBoundary>
  );
}

export default App;
