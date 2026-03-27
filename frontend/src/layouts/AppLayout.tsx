import React, { useState, useCallback, useEffect } from 'react';
import { Sidebar } from '../components/ui/Sidebar/Sidebar';
import type { NavItem } from '../components/ui/Sidebar/Sidebar';
import { ThemeToggle } from '../components/ui/ThemeToggle/ThemeToggle';
import { useBreakpoint } from '../hooks/useMediaQuery';
import './AppLayout.css';

export interface AppLayoutProps {
  children: React.ReactNode;
}

const navigationGroups = [
  { key: 'monitoring', label: '監視' },
  { key: 'analysis', label: '分析' },
  { key: 'settings', label: '設定' },
];

const navigationItems: NavItem[] = [
  { path: '/', label: 'ダッシュボード', group: 'monitoring' },
  { path: '/sites', label: '監視サイト', group: 'monitoring' },
  { path: '/alerts', label: 'アラート', group: 'monitoring' },
  { path: '/fake-sites', label: '偽サイト検知', group: 'monitoring' },
  { path: '/site-management', label: 'サイト管理', group: 'analysis' },
  { path: '/customers', label: '顧客', group: 'settings' },
  { path: '/contracts', label: '契約条件', group: 'settings' },
  { path: '/rules', label: 'チェックルール', group: 'settings' },
];

export const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
  const breakpoint = useBreakpoint();
  const isMobile = breakpoint === 'mobile';
  const isTablet = breakpoint === 'tablet';

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [isHoverExpanded, setIsHoverExpanded] = useState(false);

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
              items={navigationItems}
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
                items={navigationItems}
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
