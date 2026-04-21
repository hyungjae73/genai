import React, { useState, useCallback, useEffect, useMemo } from 'react';
import { Sidebar } from '../components/ui/Sidebar/Sidebar';
import type { NavItem } from '../components/ui/Sidebar/Sidebar';
import { ThemeToggle } from '../components/ui/ThemeToggle/ThemeToggle';
import { Badge } from '../components/ui/Badge/Badge';
import { Button } from '../components/ui/Button/Button';
import { useBreakpoint } from '../hooks/useMediaQuery';
import { useAuth } from '../contexts/AuthContext';
import './AppLayout.css';

export interface AppLayoutProps {
  children: React.ReactNode;
}

const navigationGroups = [
  { key: 'monitoring', label: '監視' },
  { key: 'analysis', label: '分析' },
  { key: 'review', label: '審査' },
  { key: 'settings', label: '設定' },
  { key: 'admin', label: '管理' },
];

const navigationItems: NavItem[] = [
  { path: '/', label: 'ダッシュボード', group: 'monitoring' },
  { path: '/sites', label: '監視サイト', group: 'monitoring' },
  { path: '/alerts', label: 'アラート', group: 'monitoring' },
  { path: '/fake-sites', label: '偽サイト検知', group: 'monitoring' },
  { path: '/site-management', label: 'サイト管理', group: 'analysis' },
  { path: '/reviews', label: '審査キュー', group: 'review' },
  { path: '/review-dashboard', label: '審査ダッシュボード', group: 'review' },
  { path: '/customers', label: '顧客', group: 'settings' },
  { path: '/contracts', label: '契約条件', group: 'settings' },
  { path: '/rules', label: 'チェックルール', group: 'settings' },
  { path: '/users', label: 'ユーザ管理', group: 'admin' },
  { path: '/categories', label: 'カテゴリ管理', group: 'admin' },
];

/** Filter navigation items based on user role */
function getFilteredItems(role: string | undefined): NavItem[] {
  if (!role) return [];
  switch (role) {
    case 'admin':
      return navigationItems; // all items including ユーザ管理
    case 'reviewer':
      // monitoring + analysis + review items (no admin group)
      return navigationItems.filter(
        (item) => item.group === 'monitoring' || item.group === 'analysis' || item.group === 'review',
      );
    case 'viewer':
      // monitoring + review-dashboard (read-only)
      return navigationItems.filter(
        (item) => item.group === 'monitoring' || item.path === '/review-dashboard',
      );
    default:
      return [];
  }
}

const roleBadgeVariant: Record<string, 'danger' | 'warning' | 'info'> = {
  admin: 'danger',
  reviewer: 'warning',
  viewer: 'info',
};

export const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
  const breakpoint = useBreakpoint();
  const isMobile = breakpoint === 'mobile';
  const isTablet = breakpoint === 'tablet';
  const { user, isAuthenticated, logout } = useAuth();

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [isHoverExpanded, setIsHoverExpanded] = useState(false);

  const filteredItems = useMemo(
    () => getFilteredItems(user?.role),
    [user?.role],
  );

  // Close drawer when switching away from mobile
  useEffect(() => {
    if (!isMobile) {
      setDrawerOpen(false);
    }
  }, [isMobile]);

  // Reset hover expanded state when leaving tablet breakpoint
  useEffect(() => {
    if (!isTablet) {
      setIsHoverExpanded(false);
    }
  }, [isTablet]);

  const toggleDrawer = useCallback(() => {
    setDrawerOpen((prev) => !prev);
  }, []);

  const closeDrawer = useCallback(() => {
    setDrawerOpen(false);
  }, []);

  const handleOverlayKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Escape') {
        closeDrawer();
      }
    },
    [closeDrawer],
  );

  return (
    <div className="app-layout">
      {/* Header */}
      <header className="app-layout__header">
        <div className="app-layout__header-left">
          {isMobile && (
            <button
              className="app-layout__hamburger"
              onClick={toggleDrawer}
              aria-label={drawerOpen ? 'メニューを閉じる' : 'メニューを開く'}
              aria-expanded={drawerOpen}
              type="button"
            >
              <span aria-hidden="true">☰</span>
            </button>
          )}
          <h1 className="app-layout__title">決済条件監視システム</h1>
        </div>
        <div className="app-layout__header-right">
          {isAuthenticated && user && (
            <div className="app-layout__user-info">
              <span className="app-layout__username">{user.username}</span>
              <Badge variant={roleBadgeVariant[user.role] || 'info'} size="sm">
                {user.role}
              </Badge>
              <Button variant="ghost" size="sm" onClick={logout} aria-label="ログアウト">
                ログアウト
              </Button>
            </div>
          )}
          <ThemeToggle />
        </div>
      </header>

      {/* Body: sidebar + main */}
      <div className="app-layout__body">
        {/* Desktop / Tablet sidebar */}
        {!isMobile && (
          <aside
            className="app-layout__sidebar"
            onMouseEnter={isTablet ? () => setIsHoverExpanded(true) : undefined}
            onMouseLeave={isTablet ? () => setIsHoverExpanded(false) : undefined}
          >
            <Sidebar
              items={filteredItems}
              groups={navigationGroups}
              collapsed={isTablet}
              onToggle={isTablet ? undefined : undefined}
              hoverExpanded={isHoverExpanded}
            />
          </aside>
        )}

        {/* Mobile drawer overlay */}
        {isMobile && (
          <>
            <div
              className={`app-layout__overlay${drawerOpen ? ' app-layout__overlay--visible' : ''}`}
              onClick={closeDrawer}
              onKeyDown={handleOverlayKeyDown}
              role="presentation"
            />
            <aside
              className={`app-layout__drawer${drawerOpen ? ' app-layout__drawer--open' : ''}`}
              aria-label="ナビゲーションドロワー"
              role="dialog"
              aria-modal={drawerOpen}
            >
              <Sidebar
                items={filteredItems}
                groups={navigationGroups}
                collapsed={false}
                onToggle={closeDrawer}
              />
            </aside>
          </>
        )}

        {/* Main content */}
        <main className="app-layout__main">
          {children}
        </main>
      </div>
    </div>
  );
};

export default AppLayout;
