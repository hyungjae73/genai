import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { AppLayout } from './AppLayout';

// Mock useBreakpoint
let mockBreakpoint = 'desktop';
vi.mock('../hooks/useMediaQuery', () => ({
  useBreakpoint: () => mockBreakpoint,
  useMediaQuery: () => false,
  classifyBreakpoint: (w: number) => {
    if (w < 768) return 'mobile';
    if (w < 1024) return 'tablet';
    return 'desktop';
  },
}));

// Mock useAuth — default to admin so all nav items show
const mockLogout = vi.fn();
let mockAuthState = {
  user: { id: 1, username: 'admin', role: 'admin' },
  accessToken: 'test-token',
  isAuthenticated: true,
  isLoading: false,
  login: vi.fn(),
  logout: mockLogout,
  refreshToken: vi.fn(),
  hasRole: (...roles: string[]) => roles.includes('admin'),
};

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => mockAuthState,
}));

function renderLayout(children: React.ReactNode = <div>Test Content</div>) {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <AppLayout>{children}</AppLayout>
    </MemoryRouter>,
  );
}

describe('AppLayout', () => {
  beforeEach(() => {
    mockBreakpoint = 'desktop';
  });

  it('renders header with title', () => {
    renderLayout();
    expect(screen.getByText('決済条件監視システム')).toBeInTheDocument();
  });

  it('renders children in main content area', () => {
    renderLayout(<p>Hello World</p>);
    expect(screen.getByText('Hello World')).toBeInTheDocument();
  });

  it('renders main element', () => {
    renderLayout();
    expect(screen.getByRole('main')).toBeInTheDocument();
  });

  describe('Desktop (≥1024px)', () => {
    beforeEach(() => {
      mockBreakpoint = 'desktop';
    });

    it('renders sidebar navigation', () => {
      renderLayout();
      expect(screen.getByRole('navigation', { name: 'メインナビゲーション' })).toBeInTheDocument();
    });

    it('renders all 9 navigation items', () => {
      renderLayout();
      expect(screen.getAllByRole('link')).toHaveLength(9);
    });

    it('does not show hamburger button', () => {
      renderLayout();
      expect(screen.queryByLabelText('メニューを開く')).not.toBeInTheDocument();
    });

    it('renders sidebar expanded (not collapsed)', () => {
      renderLayout();
      const nav = screen.getByRole('navigation', { name: 'メインナビゲーション' });
      expect(nav.className).not.toContain('sidebar--collapsed');
    });

    it('renders group labels', () => {
      renderLayout();
      expect(screen.getByText('監視')).toBeInTheDocument();
      expect(screen.getByText('分析')).toBeInTheDocument();
      expect(screen.getByText('設定')).toBeInTheDocument();
      expect(screen.getByText('管理')).toBeInTheDocument();
    });

    it('renders サイト管理 link with /site-management path', () => {
      renderLayout();
      const link = screen.getByText('サイト管理').closest('a');
      expect(link).toBeInTheDocument();
      expect(link).toHaveAttribute('href', '/site-management');
    });

    it('does not render スクリーンショット navigation item', () => {
      renderLayout();
      expect(screen.queryByText('スクリーンショット')).not.toBeInTheDocument();
    });

    it('does not render 検証・比較 navigation item', () => {
      renderLayout();
      expect(screen.queryByText('検証・比較')).not.toBeInTheDocument();
    });

    it('renders 分析 group with at least one navigation item', () => {
      renderLayout();
      const analysisGroupLabel = screen.getByText('分析');
      expect(analysisGroupLabel).toBeInTheDocument();
      // The group label is rendered, meaning the group has items (empty groups are not rendered)
      // Verify サイト管理 is present as the item in the 分析 group
      expect(screen.getByText('サイト管理')).toBeInTheDocument();
    });
  });

  describe('Tablet (768-1023px)', () => {
    beforeEach(() => {
      mockBreakpoint = 'tablet';
    });

    it('renders sidebar in collapsed mode', () => {
      renderLayout();
      const nav = screen.getByRole('navigation', { name: 'メインナビゲーション' });
      expect(nav.className).toContain('sidebar--collapsed');
    });

    it('does not show hamburger button', () => {
      renderLayout();
      expect(screen.queryByLabelText('メニューを開く')).not.toBeInTheDocument();
    });

    it('hides group labels when collapsed', () => {
      renderLayout();
      expect(screen.queryByText('監視')).not.toBeInTheDocument();
    });

    it('expands sidebar labels on mouseenter over sidebar wrapper', () => {
      renderLayout();
      const aside = document.querySelector('.app-layout__sidebar')!;
      expect(screen.queryByText('監視')).not.toBeInTheDocument();

      fireEvent.mouseEnter(aside);
      expect(screen.getByText('監視')).toBeInTheDocument();
      expect(screen.getByText('分析')).toBeInTheDocument();
      expect(screen.getByText('設定')).toBeInTheDocument();
      expect(screen.getByText('管理')).toBeInTheDocument();
    });

    it('collapses sidebar labels on mouseleave from sidebar wrapper', () => {
      renderLayout();
      const aside = document.querySelector('.app-layout__sidebar')!;

      fireEvent.mouseEnter(aside);
      expect(screen.getByText('監視')).toBeInTheDocument();

      fireEvent.mouseLeave(aside);
      expect(screen.queryByText('監視')).not.toBeInTheDocument();
    });

    it('adds sidebar--hover-expanded class on hover', () => {
      renderLayout();
      const aside = document.querySelector('.app-layout__sidebar')!;
      const nav = screen.getByRole('navigation', { name: 'メインナビゲーション' });

      expect(nav.className).not.toContain('sidebar--hover-expanded');

      fireEvent.mouseEnter(aside);
      expect(nav.className).toContain('sidebar--hover-expanded');

      fireEvent.mouseLeave(aside);
      expect(nav.className).not.toContain('sidebar--hover-expanded');
    });
  });

  describe('Mobile (<768px)', () => {
    beforeEach(() => {
      mockBreakpoint = 'mobile';
    });

    it('shows hamburger button', () => {
      renderLayout();
      expect(screen.getByLabelText('メニューを開く')).toBeInTheDocument();
    });

    it('does not render sidebar in body', () => {
      renderLayout();
      // The sidebar should only be in the drawer, not in the body aside
      const asides = document.querySelectorAll('.app-layout__sidebar');
      expect(asides).toHaveLength(0);
    });

    it('opens drawer when hamburger is clicked', () => {
      renderLayout();
      const hamburger = screen.getByLabelText('メニューを開く');
      fireEvent.click(hamburger);

      // Drawer should be open
      const drawer = document.querySelector('.app-layout__drawer');
      expect(drawer?.className).toContain('app-layout__drawer--open');
    });

    it('closes drawer when overlay is clicked', () => {
      renderLayout();
      // Open drawer
      fireEvent.click(screen.getByLabelText('メニューを開く'));

      // Click overlay
      const overlay = document.querySelector('.app-layout__overlay--visible');
      expect(overlay).not.toBeNull();
      fireEvent.click(overlay!);

      // Drawer should be closed
      const drawer = document.querySelector('.app-layout__drawer');
      expect(drawer?.className).not.toContain('app-layout__drawer--open');
    });

    it('closes drawer on Escape key', () => {
      renderLayout();
      // Open drawer
      fireEvent.click(screen.getByLabelText('メニューを開く'));

      // Press Escape on overlay
      const overlay = document.querySelector('.app-layout__overlay--visible');
      fireEvent.keyDown(overlay!, { key: 'Escape' });

      const drawer = document.querySelector('.app-layout__drawer');
      expect(drawer?.className).not.toContain('app-layout__drawer--open');
    });

    it('hamburger has aria-expanded attribute', () => {
      renderLayout();
      const hamburger = screen.getByLabelText('メニューを開く');
      expect(hamburger).toHaveAttribute('aria-expanded', 'false');

      fireEvent.click(hamburger);
      const hamburgerAfter = screen.getByLabelText('メニューを閉じる');
      expect(hamburgerAfter).toHaveAttribute('aria-expanded', 'true');
    });

    it('drawer has dialog role when open', () => {
      renderLayout();
      fireEvent.click(screen.getByLabelText('メニューを開く'));
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('renders navigation items inside drawer', () => {
      renderLayout();
      fireEvent.click(screen.getByLabelText('メニューを開く'));
      expect(screen.getAllByRole('link')).toHaveLength(9);
    });
  });
});
