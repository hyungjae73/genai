import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import type { NavItem } from './Sidebar';

const testItems: NavItem[] = [
  { path: '/', label: 'ダッシュボード', group: 'monitoring' },
  { path: '/sites', label: '監視サイト', group: 'monitoring' },
  { path: '/alerts', label: 'アラート', group: 'monitoring' },
  { path: '/fake-sites', label: '偽サイト検知', group: 'monitoring' },
  { path: '/hierarchy', label: '階層型ビュー', group: 'analysis' },
  { path: '/screenshots', label: 'スクリーンショット', group: 'analysis' },
  { path: '/verification', label: '検証・比較', group: 'analysis' },
  { path: '/customers', label: '顧客', group: 'settings' },
  { path: '/contracts', label: '契約条件', group: 'settings' },
  { path: '/rules', label: 'チェックルール', group: 'settings' },
];

const testGroups = [
  { key: 'monitoring', label: '監視' },
  { key: 'analysis', label: '分析' },
  { key: 'settings', label: '設定' },
];

function renderSidebar(props: Partial<Parameters<typeof Sidebar>[0]> = {}, initialPath = '/') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Sidebar items={testItems} groups={testGroups} {...props} />
    </MemoryRouter>,
  );
}

describe('Sidebar', () => {
  it('renders navigation with aria-label', () => {
    renderSidebar();
    expect(screen.getByRole('navigation', { name: 'メインナビゲーション' })).toBeInTheDocument();
  });

  it('renders all 10 navigation items', () => {
    renderSidebar();
    const links = screen.getAllByRole('link');
    expect(links).toHaveLength(10);
  });

  it('renders group labels', () => {
    renderSidebar();
    expect(screen.getByText('監視')).toBeInTheDocument();
    expect(screen.getByText('分析')).toBeInTheDocument();
    expect(screen.getByText('設定')).toBeInTheDocument();
  });

  it('marks the active page with aria-current="page"', () => {
    renderSidebar({}, '/alerts');
    const activeLink = screen.getByRole('link', { name: 'アラート' });
    expect(activeLink).toHaveAttribute('aria-current', 'page');
  });

  it('does not mark inactive pages with aria-current', () => {
    renderSidebar({}, '/alerts');
    const inactiveLink = screen.getByRole('link', { name: 'ダッシュボード' });
    expect(inactiveLink).not.toHaveAttribute('aria-current');
  });

  it('applies active class to current page link', () => {
    renderSidebar({}, '/sites');
    const activeLink = screen.getByRole('link', { name: '監視サイト' });
    expect(activeLink.className).toContain('sidebar__link--active');
  });

  it('hides group labels when collapsed', () => {
    renderSidebar({ collapsed: true });
    expect(screen.queryByText('監視')).not.toBeInTheDocument();
    expect(screen.queryByText('分析')).not.toBeInTheDocument();
    expect(screen.queryByText('設定')).not.toBeInTheDocument();
  });

  it('hides item labels when collapsed', () => {
    renderSidebar({ collapsed: true });
    expect(screen.queryByText('ダッシュボード')).not.toBeInTheDocument();
  });

  it('adds collapsed class when collapsed', () => {
    renderSidebar({ collapsed: true });
    const nav = screen.getByRole('navigation');
    expect(nav.className).toContain('sidebar--collapsed');
  });

  it('renders toggle button when onToggle is provided', () => {
    const toggle = vi.fn();
    renderSidebar({ onToggle: toggle });
    const btn = screen.getByRole('button', { name: 'サイドバーを折りたたむ' });
    expect(btn).toBeInTheDocument();
  });

  it('calls onToggle when toggle button is clicked', () => {
    const toggle = vi.fn();
    renderSidebar({ onToggle: toggle });
    fireEvent.click(screen.getByRole('button', { name: 'サイドバーを折りたたむ' }));
    expect(toggle).toHaveBeenCalledOnce();
  });

  it('shows expand label when collapsed', () => {
    const toggle = vi.fn();
    renderSidebar({ collapsed: true, onToggle: toggle });
    expect(screen.getByRole('button', { name: 'サイドバーを展開' })).toBeInTheDocument();
  });

  it('does not render toggle button when onToggle is not provided', () => {
    renderSidebar();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('calls onToggle on Escape key', () => {
    const toggle = vi.fn();
    renderSidebar({ onToggle: toggle });
    const nav = screen.getByRole('navigation');
    fireEvent.keyDown(nav, { key: 'Escape' });
    expect(toggle).toHaveBeenCalledOnce();
  });

  it('links are keyboard focusable', () => {
    renderSidebar();
    const link = screen.getByRole('link', { name: 'ダッシュボード' });
    link.focus();
    expect(document.activeElement).toBe(link);
  });

  it('groups items correctly — monitoring has 4 items', () => {
    renderSidebar();
    const groups = screen.getAllByRole('group');
    expect(groups).toHaveLength(3);
    // First group (監視) should have 4 links
    const monitoringGroup = groups[0];
    const links = monitoringGroup.querySelectorAll('a');
    expect(links).toHaveLength(4);
  });

  it('renders dividers between groups', () => {
    const { container } = renderSidebar();
    const dividers = container.querySelectorAll('.sidebar__divider');
    // 3 groups → 2 dividers
    expect(dividers).toHaveLength(2);
  });

  it('shows title tooltip on links when collapsed', () => {
    renderSidebar({ collapsed: true });
    const links = screen.getAllByRole('link');
    for (const link of links) {
      expect(link).toHaveAttribute('title');
    }
  });

  it('does not show title tooltip on links when expanded', () => {
    renderSidebar();
    const links = screen.getAllByRole('link');
    for (const link of links) {
      expect(link).not.toHaveAttribute('title');
    }
  });
});

describe('Sidebar hover-expanded (Requirements 5.2, 5.3, 5.7)', () => {
  it('adds sidebar--hover-expanded class when hoverExpanded is true', () => {
    renderSidebar({ hoverExpanded: true });
    const nav = screen.getByRole('navigation');
    expect(nav.className).toContain('sidebar--hover-expanded');
  });

  it('does not add sidebar--hover-expanded class when hoverExpanded is false', () => {
    renderSidebar({ hoverExpanded: false });
    const nav = screen.getByRole('navigation');
    expect(nav.className).not.toContain('sidebar--hover-expanded');
  });

  it('shows labels when collapsed and hoverExpanded', () => {
    renderSidebar({ collapsed: true, hoverExpanded: true });
    expect(screen.getByText('ダッシュボード')).toBeInTheDocument();
    expect(screen.getByText('監視サイト')).toBeInTheDocument();
  });

  it('shows group labels when collapsed and hoverExpanded', () => {
    renderSidebar({ collapsed: true, hoverExpanded: true });
    expect(screen.getByText('監視')).toBeInTheDocument();
    expect(screen.getByText('分析')).toBeInTheDocument();
    expect(screen.getByText('設定')).toBeInTheDocument();
  });

  it('does not show title tooltip on links when collapsed and hoverExpanded', () => {
    renderSidebar({ collapsed: true, hoverExpanded: true });
    const links = screen.getAllByRole('link');
    for (const link of links) {
      expect(link).not.toHaveAttribute('title');
    }
  });

  it('applies both collapsed and hover-expanded classes together', () => {
    renderSidebar({ collapsed: true, hoverExpanded: true });
    const nav = screen.getByRole('navigation');
    expect(nav.className).toContain('sidebar--collapsed');
    expect(nav.className).toContain('sidebar--hover-expanded');
  });
});

