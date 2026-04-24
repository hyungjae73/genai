import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { classifyBreakpoint, Breakpoint } from '../hooks/useMediaQuery';

// Feature: screenshot-integration-rename, Property 1: Breakpoint classification is consistent

const VALID_BREAKPOINTS: Breakpoint[] = ['mobile', 'tablet', 'desktop'];

describe('Property 1: Breakpoint classification is consistent', () => {
  /**
   * Validates: Requirements 5.1, 5.4, 5.5
   *
   * For any positive integer viewport width, classifyBreakpoint returns the correct
   * breakpoint category: 'mobile' if width < 768, 'tablet' if 768 ≤ width ≤ 1023,
   * 'desktop' if width ≥ 1024. The three ranges are exhaustive and mutually exclusive.
   */
  it('should classify any positive integer width into exactly one correct breakpoint category', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 100000 }),
        (width: number) => {
          const result = classifyBreakpoint(width);

          // Result must be a valid breakpoint (exhaustive — every width maps to a category)
          expect(VALID_BREAKPOINTS).toContain(result);

          // Verify correct category assignment
          if (width < 768) {
            expect(result).toBe('mobile');
          } else if (width >= 768 && width <= 1023) {
            expect(result).toBe('tablet');
          } else {
            expect(result).toBe('desktop');
          }
        }
      ),
      { numRuns: 200 }
    );
  });

  /**
   * Validates: Requirements 5.1, 5.4, 5.5
   *
   * The three breakpoint ranges are mutually exclusive: for any positive integer width,
   * exactly one of the three conditions (mobile, tablet, desktop) holds true.
   */
  it('should have mutually exclusive breakpoint ranges for any positive width', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 100000 }),
        (width: number) => {
          const isMobile = width < 768;
          const isTablet = width >= 768 && width <= 1023;
          const isDesktop = width >= 1024;

          // Exactly one condition must be true (mutual exclusivity + exhaustiveness)
          const trueCount = [isMobile, isTablet, isDesktop].filter(Boolean).length;
          expect(trueCount).toBe(1);

          // classifyBreakpoint must agree with the true condition
          const result = classifyBreakpoint(width);
          if (isMobile) expect(result).toBe('mobile');
          if (isTablet) expect(result).toBe('tablet');
          if (isDesktop) expect(result).toBe('desktop');
        }
      ),
      { numRuns: 200 }
    );
  });
});

// Feature: screenshot-integration-rename, Property 2: No empty navigation groups are rendered

import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import React from 'react';
import { Sidebar } from '../components/ui/Sidebar/Sidebar';
import type { NavItem } from '../components/ui/Sidebar/Sidebar';
import { createTestQueryClient } from '../test/testQueryClient';
import { QueryClientProvider } from '@tanstack/react-query';

/**
 * Arbitrary: generates a list of unique group definitions (1–5 groups).
 */
const arbGroups = fc.uniqueArray(
  fc.record({
    key: fc.stringMatching(/^[a-z]{2,8}$/),
    label: fc.stringMatching(/^[A-Za-z\u3040-\u309F]{1,10}$/),
  }),
  { minLength: 1, maxLength: 5, selector: (g) => g.key },
);

/**
 * Arbitrary: given a set of group keys, generates a list of NavItem[] where
 * each item's group is drawn from the provided keys. The list may be empty,
 * meaning some groups could end up with zero items.
 */
const arbItemsForGroups = (groupKeys: string[]) =>
  fc.array(
    fc.record({
      path: fc.stringMatching(/^\/[a-z]{1,12}$/).chain((p) =>
        fc.constant(p),
      ),
      label: fc.stringMatching(/^[A-Za-z\u3040-\u309F]{1,10}$/),
      group: fc.constantFrom(...groupKeys),
    }),
    { minLength: 0, maxLength: 20 },
  ).map((items) => {
    // Ensure unique paths so NavLink keys don't collide
    const seen = new Set<string>();
    const unique: NavItem[] = [];
    for (const item of items) {
      if (!seen.has(item.path)) {
        seen.add(item.path);
        unique.push(item);
      }
    }
    return unique;
  });

describe('Property 2: No empty navigation groups are rendered', () => {
  /**
   * Validates: Requirements 4.4
   *
   * For any set of navigation items and group definitions, the Sidebar component
   * shall not render a group element (role="group") that contains zero links.
   * Groups with no matching items should either be absent from the DOM or contain
   * at least one link.
   */
  it('should never render a group element with zero links inside', () => {
    fc.assert(
      fc.property(
        arbGroups.chain((groups) =>
          arbItemsForGroups(groups.map((g) => g.key)).map((items) => ({
            groups,
            items,
          })),
        ),
        ({ groups, items }) => {
          const { container } = render(
            React.createElement(
              MemoryRouter,
              null,
              React.createElement(Sidebar, { items, groups }),
            ),
          );

          const groupElements = container.querySelectorAll('[role="group"]');

          for (const groupEl of groupElements) {
            const links = groupEl.querySelectorAll('a');
            expect(links.length).toBeGreaterThan(0);
          }
        },
      ),
      { numRuns: 100 },
    );
  });
});


// Feature: screenshot-integration-rename, Property 3: Verification results display all required fields

import { waitFor, cleanup } from '@testing-library/react';
import { vi, beforeEach, afterEach } from 'vitest';
import * as api from '../services/api';

vi.mock('../services/api', () => ({
  triggerVerification: vi.fn(),
  getVerificationResults: vi.fn(),
  getVerificationStatus: vi.fn(),
  getStatistics: vi.fn(),
  getMonitoringHistory: vi.fn(),
  getSites: vi.fn(),
  getCustomers: vi.fn(),
  getAlerts: vi.fn(),
  getCategories: vi.fn(),
  getContracts: vi.fn(),
  getSiteContracts: vi.fn(),
  createCustomer: vi.fn(),
  updateCustomer: vi.fn(),
  deleteCustomer: vi.fn(),
  createSite: vi.fn(),
  updateSite: vi.fn(),
  deleteSite: vi.fn(),
  createContract: vi.fn(),
  deleteContract: vi.fn(),
  triggerCrawl: vi.fn(),
  getCrawlStatus: vi.fn(),
  getLatestCrawlResult: vi.fn(),
  getSiteScreenshots: vi.fn(),
  getExtractedData: vi.fn(),
  getScreenshotUrl: vi.fn().mockImplementation((id: number) => `http://localhost/api/screenshots/view/${id}`),
  uploadScreenshot: vi.fn(),
  captureScreenshot: vi.fn(),
  deleteScreenshot: vi.fn(),
  extractData: vi.fn(),
  updateExtractedData: vi.fn(),
  getFieldSchemas: vi.fn(),
}));

vi.mock('react-chartjs-2', () => ({
  Line: () => null,
}));

vi.mock('chart.js', () => ({
  Chart: { register: vi.fn() },
  CategoryScale: vi.fn(),
  LinearScale: vi.fn(),
  PointElement: vi.fn(),
  LineElement: vi.fn(),
  Title: vi.fn(),
  Tooltip: vi.fn(),
  Legend: vi.fn(),
}));

vi.mock('../hooks/useAutoRefresh', () => ({
  useAutoRefresh: vi.fn(),
}));

vi.mock('../api/extractedData', () => ({
  fetchExtractedData: vi.fn(),
  updateExtractedData: vi.fn(),
  approveExtractedData: vi.fn(),
  rejectExtractedData: vi.fn(),
  fetchAuditLogs: vi.fn(),
  fetchVisualConfirmationData: vi.fn(),
}));

vi.mock('react-zoom-pan-pinch', () => ({
  TransformWrapper: ({ children }: { children: (utils: Record<string, () => void>) => React.ReactNode }) =>
    children({ zoomIn: vi.fn(), zoomOut: vi.fn(), resetTransform: vi.fn() }),
  TransformComponent: ({ children }: { children: React.ReactNode }) => children,
}));

/**
 * Arbitrary: generates a record of 1–5 unique field names mapped to simple string values.
 * Field names are short alphabetic strings; values are non-empty alphanumeric strings.
 */
const arbFieldData = fc.uniqueArray(
  fc.tuple(
    fc.stringMatching(/^[a-z]{2,10}$/),
    fc.stringMatching(/^[a-zA-Z0-9]{1,20}$/),
  ),
  { minLength: 1, maxLength: 5, selector: ([key]) => key },
).map((pairs) => {
  const record: Record<string, string> = {};
  for (const [key, value] of pairs) {
    record[key] = value;
  }
  return record;
});

/**
 * Arbitrary: generates a pair of html_data and ocr_data records that share the same field names.
 * This ensures the comparison table will have rows for each field.
 */
const arbVerificationData = arbFieldData.chain((htmlData) => {
  const fieldNames = Object.keys(htmlData);
  return fc.tuple(
    ...fieldNames.map((name) =>
      fc.stringMatching(/^[a-zA-Z0-9]{1,20}$/).map((val) => [name, val] as const),
    ),
  ).map((ocrPairs) => {
    const ocrData: Record<string, string> = {};
    for (const [key, value] of ocrPairs) {
      ocrData[key] = value;
    }
    return { htmlData, ocrData, fieldNames };
  });
});

describe('Property 3: Verification results display all required fields', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  /**
   * Validates: Requirements 3.3
   *
   * For any verification result with a completed status, the rendered VerificationTab
   * output shall contain the HTML value, OCR value, and status indicator for each
   * comparison entry.
   */
  it('should display HTML value, OCR value, and status for every field in the comparison table', async () => {
    await fc.assert(
      fc.asyncProperty(
        arbVerificationData,
        async ({ htmlData, ocrData, fieldNames }) => {
          cleanup();
          vi.clearAllMocks();

          const mockResult: api.VerificationResult = {
            id: 1,
            site_id: 100,
            site_name: 'テストサイト',
            html_data: htmlData,
            ocr_data: ocrData,
            discrepancies: [],
            html_violations: [],
            ocr_violations: [],
            screenshot_path: '/screenshots/test.png',
            ocr_confidence: 0.95,
            status: 'completed',
            error_message: null,
            created_at: '2024-06-01T10:00:00Z',
          };

          vi.mocked(api.getVerificationResults).mockResolvedValue({
            results: [mockResult],
            total: 1,
            limit: 10,
            offset: 0,
          });

          const { container } = render(
            React.createElement(
              (await import('../components/hierarchy/tabs/VerificationTab')).default,
              { siteId: 100 },
            ),
          );

          // Wait for the comparison table to render
          await waitFor(() => {
            const table = container.querySelector('table');
            expect(table).not.toBeNull();
          });

          const table = container.querySelector('table')!;
          const rows = table.querySelectorAll('tbody tr');

          // There should be one row per field
          expect(rows.length).toBe(fieldNames.length);

          // Verify each field has its HTML value, OCR value, and a status indicator
          for (const fieldName of fieldNames) {
            const htmlValue = htmlData[fieldName];
            const ocrValue = ocrData[fieldName];

            // Find the row whose first cell exactly matches the field name
            let matchingRow: Element | null = null;
            for (const row of rows) {
              const firstCell = row.querySelector('td');
              if (firstCell && firstCell.textContent === fieldName) {
                matchingRow = row;
                break;
              }
            }

            expect(matchingRow).not.toBeNull();

            // Get all cells in the row
            const cells = matchingRow!.querySelectorAll('td');
            // Column order: フィールド名, HTML値, OCR値, ステータス
            expect(cells.length).toBeGreaterThanOrEqual(4);

            // The HTML value cell (index 1) should contain the html value
            expect(cells[1].textContent).toContain(htmlValue);

            // The OCR value cell (index 2) should contain the ocr value
            expect(cells[2].textContent).toContain(ocrValue);

            // The status cell (index 3) should contain a status indicator
            const statusCell = cells[3].querySelector('.verification-status-cell');
            expect(statusCell).not.toBeNull();
            expect(statusCell!.textContent!.length).toBeGreaterThan(0);
          }
        },
      ),
      { numRuns: 100 },
    );
  });
});


// Feature: screenshot-integration-rename, Property 4: Discrepancies are displayed with severity badges

/**
 * Arbitrary: generates 1–5 discrepancy objects with random field names, values,
 * difference types, and severities drawn from ['high', 'medium', 'low'].
 */
const arbDiscrepancies = fc.uniqueArray(
  fc.record({
    field_name: fc.stringMatching(/^[a-z]{2,10}$/),
    html_value: fc.stringMatching(/^[a-zA-Z0-9]{1,15}$/),
    ocr_value: fc.stringMatching(/^[a-zA-Z0-9]{1,15}$/),
    difference_type: fc.constantFrom('value_mismatch', 'missing_field', 'format_difference'),
    severity: fc.constantFrom('high', 'medium', 'low'),
  }),
  { minLength: 1, maxLength: 5, selector: (d) => d.field_name },
);

describe('Property 4: Discrepancies are displayed with severity badges', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  /**
   * Validates: Requirements 3.4
   *
   * For any verification result that contains one or more discrepancies, the rendered
   * VerificationTab output shall display each discrepancy's field_name and its
   * corresponding severity badge.
   */
  it('should display each discrepancy field name and severity badge', async () => {
    await fc.assert(
      fc.asyncProperty(
        arbDiscrepancies,
        async (discrepancies) => {
          cleanup();
          vi.clearAllMocks();

          // Build html_data and ocr_data from discrepancies so the result is realistic
          const htmlData: Record<string, string> = {};
          const ocrData: Record<string, string> = {};
          for (const disc of discrepancies) {
            htmlData[disc.field_name] = disc.html_value;
            ocrData[disc.field_name] = disc.ocr_value;
          }

          const mockResult: api.VerificationResult = {
            id: 1,
            site_id: 100,
            site_name: 'テストサイト',
            html_data: htmlData,
            ocr_data: ocrData,
            discrepancies,
            html_violations: [],
            ocr_violations: [],
            screenshot_path: '/screenshots/test.png',
            ocr_confidence: 0.90,
            status: 'completed',
            error_message: null,
            created_at: '2024-06-01T10:00:00Z',
          };

          vi.mocked(api.getVerificationResults).mockResolvedValue({
            results: [mockResult],
            total: 1,
            limit: 10,
            offset: 0,
          });

          const { container } = render(
            React.createElement(
              (await import('../components/hierarchy/tabs/VerificationTab')).default,
              { siteId: 100 },
            ),
          );

          // Wait for the discrepancy section to render
          await waitFor(() => {
            const sections = container.querySelectorAll('.verification-tab-section');
            // Find the section with heading "検出された差異"
            let found = false;
            for (const section of sections) {
              const heading = section.querySelector('h3');
              if (heading && heading.textContent === '検出された差異') {
                found = true;
                break;
              }
            }
            expect(found).toBe(true);
          });

          // Find the discrepancy section
          const sections = container.querySelectorAll('.verification-tab-section');
          let discrepancySection: Element | null = null;
          for (const section of sections) {
            const heading = section.querySelector('h3');
            if (heading && heading.textContent === '検出された差異') {
              discrepancySection = section;
              break;
            }
          }
          expect(discrepancySection).not.toBeNull();

          // Verify each discrepancy's field_name and severity badge appear
          for (const disc of discrepancies) {
            // Check field name is displayed
            const fieldNames = discrepancySection!.querySelectorAll('.verification-tab-field-name');
            const fieldNameTexts = Array.from(fieldNames).map((el) => el.textContent);
            expect(fieldNameTexts).toContain(disc.field_name);

            // Check severity badge is displayed — Badge renders with role="status"
            const badges = discrepancySection!.querySelectorAll('[role="status"]');
            const badgeTexts = Array.from(badges).map((el) => el.textContent);
            expect(badgeTexts).toContain(disc.severity);
          }
        },
      ),
      { numRuns: 100 },
    );
  });
});


// Feature: screenshot-integration-rename, Property 5: Help button presence, accessibility, and modal behavior

import userEvent from '@testing-library/user-event';
import { Routes, Route } from 'react-router-dom';
import * as extractedDataApi from '../api/extractedData';

/**
 * Page configuration for the 9 pages that must have a help button.
 * Each entry defines the page name, the dynamic import, and a setup function
 * that configures the required mocks before rendering.
 */
interface PageConfig {
  name: string;
  importPage: () => Promise<{ default: React.ComponentType }>;
  setupMocks: () => void;
  /** Custom render wrapper; if provided, overrides the default MemoryRouter wrapping */
  renderElement?: (Component: React.ComponentType) => React.ReactElement;
}

const PAGE_CONFIGS: PageConfig[] = [
  {
    name: 'Dashboard',
    importPage: () => import('../pages/Dashboard'),
    setupMocks: () => {
      vi.mocked(api.getStatistics).mockResolvedValue({
        total_sites: 10,
        active_sites: 8,
        total_violations: 5,
        high_severity_violations: 2,
        success_rate: 95.5,
        last_crawl: '2024-01-15T10:00:00Z',
        fake_site_alerts: 3,
        unresolved_fake_site_alerts: 1,
      });
      vi.mocked(api.getMonitoringHistory).mockResolvedValue([]);
    },
  },
  {
    name: 'Sites',
    importPage: () => import('../pages/Sites'),
    setupMocks: () => {
      vi.mocked(api.getSites).mockResolvedValue([]);
      vi.mocked(api.getCustomers).mockResolvedValue([]);
      vi.mocked(api.createSite).mockResolvedValue({} as any);
      vi.mocked(api.updateSite).mockResolvedValue({} as any);
      vi.mocked(api.deleteSite).mockResolvedValue(undefined as any);
    },
  },
  {
    name: 'Alerts',
    importPage: () => import('../pages/Alerts'),
    setupMocks: () => {
      vi.mocked(api.getAlerts).mockResolvedValue([]);
    },
  },
  {
    name: 'FakeSites',
    importPage: () => import('../pages/FakeSites'),
    setupMocks: () => {
      vi.mocked(api.getAlerts).mockResolvedValue([]);
    },
  },
  {
    name: 'SiteManagement',
    importPage: () => import('../pages/SiteManagement'),
    setupMocks: () => {
      vi.mocked(api.getCustomers).mockResolvedValue([]);
      vi.mocked(api.getSites).mockResolvedValue([]);
      vi.mocked(api.getCategories).mockResolvedValue([]);
    },
  },
  {
    name: 'CrawlResultReview',
    importPage: () => import('../pages/CrawlResultReview'),
    setupMocks: () => {
      vi.mocked(extractedDataApi.fetchExtractedData).mockResolvedValue({
        id: 1,
        crawl_result_id: 10,
        site_id: 1,
        source: 'html',
        product_info: { name: 'テスト商品' },
        price_info: [{ amount: 1000, currency: 'JPY' }],
        payment_methods: [{ method_name: 'クレジットカード' }],
        fees: [],
        metadata: { url: 'https://example.com', screenshot_path: '/screenshots/test.png' },
        confidence_scores: { product_name: 0.9 },
        overall_confidence_score: 0.85,
        status: 'pending',
        language: 'ja',
        extracted_at: '2024-06-01T10:00:00Z',
      });
      vi.mocked(extractedDataApi.fetchVisualConfirmationData).mockResolvedValue({
        screenshot_url: null,
        raw_html: null,
        extraction_status: 'complete',
        html_data: null,
        ocr_data: null,
      });
    },
    renderElement: (Component: React.ComponentType) =>
      React.createElement(
        MemoryRouter,
        { initialEntries: ['/sites/1/crawl-results/10/review'] },
        React.createElement(
          Routes,
          null,
          React.createElement(Route, {
            path: '/sites/:siteId/crawl-results/:crawlResultId/review',
            element: React.createElement(Component),
          }),
        ),
      ),
  },
  {
    name: 'Contracts',
    importPage: () => import('../pages/Contracts'),
    setupMocks: () => {
      vi.mocked(api.getSites).mockResolvedValue([]);
      vi.mocked(api.getContracts).mockResolvedValue([]);
      vi.mocked(api.getSiteContracts).mockResolvedValue([]);
      vi.mocked(api.getCategories).mockResolvedValue([]);
    },
  },
  {
    name: 'Rules',
    importPage: () => import('../pages/Rules'),
    setupMocks: () => {
      // Rules page uses static data, no API calls needed
    },
  },
  {
    name: 'Customers',
    importPage: () => import('../pages/Customers'),
    setupMocks: () => {
      vi.mocked(api.getCustomers).mockResolvedValue([]);
    },
  },
];

/**
 * Arbitrary: picks a random page from the 9-page set.
 */
const arbPage = fc.constantFrom(...PAGE_CONFIGS);

describe('Property 5: Help button presence, accessibility, and modal behavior', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  /**
   * Validates: Requirements 6.1, 6.2, 6.4
   *
   * For any page in the set {Dashboard, Sites, Alerts, FakeSites, SiteManagement,
   * CrawlResultReview, Contracts, Rules, Customers}, the page shall render a help
   * button with aria-label="ヘルプを表示", and clicking that button shall open a
   * Modal (role="dialog") containing non-empty help content.
   */
  it('should render a help button with correct aria-label and open a modal with content on click', async () => {
    await fc.assert(
      fc.asyncProperty(
        arbPage,
        async (pageConfig) => {
          cleanup();
          vi.clearAllMocks();
          pageConfig.setupMocks();

          const PageComponent = (await pageConfig.importPage()).default;

          const wrapper = pageConfig.renderElement
            ? pageConfig.renderElement(PageComponent)
            : React.createElement(
                MemoryRouter,
                null,
                React.createElement(PageComponent),
              );

          const testQueryClient = createTestQueryClient();
          const { container } = render(
            React.createElement(QueryClientProvider, { client: testQueryClient }, wrapper),
          );

          // Wait for the page to finish loading (async pages show loading state first)
          await waitFor(() => {
            const helpBtn = container.querySelector('button[aria-label="ヘルプを表示"]');
            expect(helpBtn).not.toBeNull();
          });

          // Verify help button presence and aria-label
          const helpButton = container.querySelector('button[aria-label="ヘルプを表示"]') as HTMLElement;
          expect(helpButton).not.toBeNull();
          expect(helpButton.textContent).toBe('?');

          // Click the help button to open the modal
          await userEvent.click(helpButton);

          // Verify modal opens with role="dialog"
          await waitFor(() => {
            const dialog = container.querySelector('[role="dialog"]');
            expect(dialog).not.toBeNull();
          });

          const dialog = container.querySelector('[role="dialog"]') as HTMLElement;
          // Verify the modal has non-empty content
          const modalBody = dialog.querySelector('.modal__body');
          expect(modalBody).not.toBeNull();
          expect(modalBody!.textContent!.trim().length).toBeGreaterThan(0);
        },
      ),
      { numRuns: 20 },
    );
  }, 30000);
});


// Feature: screenshot-integration-rename, Property 6: Baseline screenshot invariant (one per site)

import type { Screenshot } from '../services/api';

/**
 * Arbitrary: generates a random site ID (positive integer).
 */
const arbSiteId = fc.integer({ min: 1, max: 10000 });

/**
 * Arbitrary: generates a random screenshot array with 0–3 baseline and 0–5 monitoring screenshots.
 * Each screenshot has a unique ID, the given siteId, and appropriate type.
 */
const arbScreenshotArray = (siteId: number) => {
  const arbBaselineCount = fc.integer({ min: 0, max: 3 });
  const arbMonitoringCount = fc.integer({ min: 0, max: 5 });

  return fc.tuple(arbBaselineCount, arbMonitoringCount).map(([baselineCount, monitoringCount]) => {
    const screenshots: Screenshot[] = [];
    let nextId = 1;

    for (let i = 0; i < baselineCount; i++) {
      screenshots.push({
        id: nextId++,
        site_id: siteId,
        site_name: `Site-${siteId}`,
        screenshot_type: 'baseline',
        file_path: `/screenshots/baseline-${i}.png`,
        file_format: 'png',
        crawled_at: new Date(2024, 0, 1 + i).toISOString(),
      });
    }

    for (let i = 0; i < monitoringCount; i++) {
      screenshots.push({
        id: nextId++,
        site_id: siteId,
        site_name: `Site-${siteId}`,
        screenshot_type: 'violation',
        file_path: `/screenshots/monitoring-${i}.png`,
        file_format: 'png',
        crawled_at: new Date(2024, 1, 1 + i).toISOString(),
      });
    }

    return { screenshots, baselineCount, monitoringCount };
  });
};

describe('Property 6: Baseline screenshot invariant (one per site)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  /**
   * Validates: Requirements 2.5
   *
   * For any site, the ScreenshotTab shall display at most one baseline screenshot
   * in the baseline section, even if the API returns multiple baselines.
   * The component uses `screenshots.find(s => s.screenshot_type === 'baseline')`
   * which inherently picks only the first match.
   */
  it('should display at most 1 baseline screenshot card in the baseline section regardless of API data', async () => {
    await fc.assert(
      fc.asyncProperty(
        arbSiteId.chain((siteId) =>
          arbScreenshotArray(siteId).map((data) => ({ siteId, ...data })),
        ),
        async ({ siteId, screenshots, baselineCount }) => {
          cleanup();
          vi.clearAllMocks();

          // Mock getSiteScreenshots to return the generated array
          vi.mocked(api.getSiteScreenshots).mockResolvedValue(screenshots);

          // Mock getExtractedData to reject (no extracted data)
          vi.mocked(api.getExtractedData).mockRejectedValue(new Error('Not found'));

          // Mock getScreenshotUrl
          vi.mocked(api.getScreenshotUrl).mockImplementation(
            (id: number) => `http://localhost/api/screenshots/view/${id}`,
          );

          const { container } = render(
            React.createElement(
              (await import('../components/hierarchy/tabs/ScreenshotTab')).default,
              { siteId },
            ),
          );

          // Wait for loading to complete and content to render
          await waitFor(() => {
            const baselineSec = container.querySelector('[data-testid="baseline-section"]');
            expect(baselineSec).not.toBeNull();
          });

          // Find the baseline section
          const baselineSection = container.querySelector('[data-testid="baseline-section"]')!;

          // Count screenshot cards in the baseline section
          const baselineCards = baselineSection!.querySelectorAll('.screenshot-item');

          if (baselineCount === 0) {
            // No baselines → should show empty state, no cards
            expect(baselineCards.length).toBe(0);
          } else {
            // Even if API returns multiple baselines, at most 1 should be rendered
            expect(baselineCards.length).toBe(1);
          }
        },
      ),
      { numRuns: 100 },
    );
  });
});
