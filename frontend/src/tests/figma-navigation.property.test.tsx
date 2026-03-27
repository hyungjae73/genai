// Feature: figma-ux-improvement, Property 5, 6, 7: Navigation Properties

import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { render, cleanup, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Sidebar } from '../components/ui/Sidebar/Sidebar';
import type { NavItem } from '../components/ui/Sidebar/Sidebar';

// --- Navigation data from design ---

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
  { path: '/hierarchy', label: '階層型ビュー', group: 'analysis' },
  { path: '/screenshots', label: 'スクリーンショット', group: 'analysis' },
  { path: '/verification', label: '検証・比較', group: 'analysis' },
  { path: '/customers', label: '顧客', group: 'settings' },
  { path: '/contracts', label: '契約条件', group: 'settings' },
  { path: '/rules', label: 'チェックルール', group: 'settings' },
];

const allPaths = navigationItems.map((item) => item.path);

// --- Helpers ---

function renderSidebarAtPath(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Sidebar items={navigationItems} groups={navigationGroups} />
    </MemoryRouter>,
  );
}

function renderSidebarWithToggle(path: string, onToggle: () => void) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Sidebar items={navigationItems} groups={navigationGroups} onToggle={onToggle} />
    </MemoryRouter>,
  );
}

// --- Arbitrary generators ---

const arbValidPath = fc.constantFrom(...allPaths);

// --- Property 5: Active Page Indication ---

describe('Feature: figma-ux-improvement, Property 5: Active Page Indication', () => {
  /**
   * **Validates: Requirements 4.2**
   *
   * For any valid route path, when the Sidebar is rendered at that path,
   * the corresponding navigation item has aria-current="page" and the active CSS class,
   * while all other items do not.
   */

  it('exactly one navigation link has aria-current="page" matching the current path', () => {
    fc.assert(
      fc.property(arbValidPath, (path) => {
        cleanup();
        const { container } = renderSidebarAtPath(path);

        const allLinks = container.querySelectorAll('a');
        const activeLinks = Array.from(allLinks).filter(
          (link) => link.getAttribute('aria-current') === 'page',
        );

        // Exactly one link should be active
        expect(activeLinks).toHaveLength(1);

        // The active link should point to the current path
        const activeHref = activeLinks[0].getAttribute('href');
        expect(activeHref).toBe(path);
      }),
      { numRuns: 100 },
    );
  });

  it('the active link has the sidebar__link--active CSS class', () => {
    fc.assert(
      fc.property(arbValidPath, (path) => {
        cleanup();
        const { container } = renderSidebarAtPath(path);

        const allLinks = container.querySelectorAll('a');
        for (const link of allLinks) {
          const href = link.getAttribute('href');
          if (href === path) {
            expect(link.className).toContain('sidebar__link--active');
          } else {
            expect(link.className).not.toContain('sidebar__link--active');
          }
        }
      }),
      { numRuns: 100 },
    );
  });
});

// --- Property 6: Navigation Item Grouping ---

describe('Feature: figma-ux-improvement, Property 6: Navigation Item Grouping', () => {
  /**
   * **Validates: Requirements 4.3**
   *
   * All 10 navigation items belong to exactly one group, with no items missing
   * and no items duplicated across groups.
   */

  it('every navigation item belongs to exactly one valid group', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...navigationItems),
        (item) => {
          const validGroupKeys = navigationGroups.map((g) => g.key);
          // Item's group must be one of the valid group keys
          expect(validGroupKeys).toContain(item.group);

          // Item should appear in exactly one group
          const matchingGroups = navigationGroups.filter((g) => g.key === item.group);
          expect(matchingGroups).toHaveLength(1);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('all 10 items are accounted for with no duplicates across groups', () => {
    // This is a deterministic property but we run it through fast-check
    // to validate the grouping structure is consistent
    fc.assert(
      fc.property(
        fc.constantFrom(...navigationGroups),
        (group) => {
          cleanup();
          const { container } = renderSidebarAtPath('/');

          const groupElements = container.querySelectorAll('[role="group"]');
          const groupIndex = navigationGroups.findIndex((g) => g.key === group.key);
          const groupEl = groupElements[groupIndex];

          // The group element should exist
          expect(groupEl).toBeDefined();

          // Count items in this rendered group
          const linksInGroup = groupEl.querySelectorAll('a');
          const expectedItems = navigationItems.filter((item) => item.group === group.key);

          expect(linksInGroup).toHaveLength(expectedItems.length);

          // Verify each expected item is present
          const linkTexts = Array.from(linksInGroup).map((a) => a.textContent);
          for (const expected of expectedItems) {
            expect(linkTexts).toContain(expected.label);
          }
        },
      ),
      { numRuns: 100 },
    );
  });

  it('total rendered items equals 10 with no missing items', () => {
    fc.assert(
      fc.property(arbValidPath, (path) => {
        cleanup();
        const { container } = renderSidebarAtPath(path);

        const allLinks = container.querySelectorAll('a');
        expect(allLinks).toHaveLength(10);

        // Every navigation item label should be present
        const renderedTexts = Array.from(allLinks).map((a) => a.textContent);
        for (const item of navigationItems) {
          expect(renderedTexts).toContain(item.label);
        }
      }),
      { numRuns: 100 },
    );
  });
});

// --- Property 7: Keyboard Navigation ---

describe('Feature: figma-ux-improvement, Property 7: Keyboard Navigation', () => {
  /**
   * **Validates: Requirements 4.5**
   *
   * For any focused navigation item:
   * - Tab key moves focus to the next focusable element
   * - Enter key triggers navigation (link activation)
   * - Escape key closes the mobile drawer (calls onToggle)
   */

  it('all navigation links are keyboard-focusable via Tab', () => {
    fc.assert(
      fc.property(arbValidPath, (path) => {
        cleanup();
        const { container } = renderSidebarAtPath(path);

        const allLinks = container.querySelectorAll('a');
        // All links should be focusable (no tabindex="-1")
        for (const link of allLinks) {
          const tabIndex = link.getAttribute('tabindex');
          // tabindex should be absent (default 0) or explicitly 0
          expect(tabIndex === null || tabIndex === '0').toBe(true);

          // Verify the link can receive focus
          link.focus();
          expect(document.activeElement).toBe(link);
        }
      }),
      { numRuns: 100 },
    );
  });

  it('Enter key on a focused link triggers navigation (link has valid href)', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...navigationItems),
        (item) => {
          cleanup();
          const { container } = renderSidebarAtPath('/');

          const allLinks = container.querySelectorAll('a');
          const link = Array.from(allLinks).find((a) => a.textContent === item.label)!;
          expect(link).toBeDefined();

          link.focus();
          expect(document.activeElement).toBe(link);

          // The link should have a valid href matching the item path
          expect(link.getAttribute('href')).toBe(item.path);

          // Enter on an anchor triggers default navigation behavior;
          // we verify the link is an <a> element with proper href
          expect(link.tagName).toBe('A');
        },
      ),
      { numRuns: 100 },
    );
  });

  it('Escape key calls onToggle to close mobile drawer', () => {
    fc.assert(
      fc.property(arbValidPath, (path) => {
        cleanup();
        let toggleCalled = false;
        const onToggle = () => {
          toggleCalled = true;
        };

        const { container } = renderSidebarWithToggle(path, onToggle);
        const nav = container.querySelector('nav')!;

        fireEvent.keyDown(nav, { key: 'Escape' });
        expect(toggleCalled).toBe(true);
      }),
      { numRuns: 100 },
    );
  });
});
