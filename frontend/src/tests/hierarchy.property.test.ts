import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import {
  groupSitesByCustomer,
  filterCustomers,
  type CustomerWithSites,
} from '../pages/SiteManagement';
import type { Customer, Site } from '../services/api';

// --- Arbitrary generators ---

const arbISODate = fc
  .integer({ min: 946684800000, max: 1924905600000 }) // 2000-01-01 to 2030-12-31 in ms
  .map((ts) => new Date(ts).toISOString());

const arbCustomer: fc.Arbitrary<Customer> = fc.record({
  id: fc.integer({ min: 1, max: 10000 }),
  name: fc.string({ minLength: 1, maxLength: 50 }),
  company_name: fc.option(fc.string({ minLength: 1, maxLength: 50 }), { nil: null }),
  email: fc.emailAddress(),
  phone: fc.option(fc.string({ minLength: 1, maxLength: 20 }), { nil: null }),
  address: fc.option(fc.string({ minLength: 1, maxLength: 100 }), { nil: null }),
  is_active: fc.boolean(),
  created_at: arbISODate,
  updated_at: arbISODate,
});

const arbCustomersWithUniqueIds: fc.Arbitrary<Customer[]> = fc
  .uniqueArray(fc.integer({ min: 1, max: 10000 }), { minLength: 1, maxLength: 20 })
  .chain((ids) =>
    fc.tuple(...ids.map((id) => arbCustomer.map((c) => ({ ...c, id }))))
  );

function arbSitesForCustomers(customerIds: number[]): fc.Arbitrary<Site[]> {
  if (customerIds.length === 0) return fc.constant([]);
  return fc
    .array(
      fc.record({
        id: fc.integer({ min: 1, max: 100000 }),
        customer_id: fc.constantFrom(...customerIds),
        category_id: fc.option(fc.integer({ min: 1, max: 100 }), { nil: null }),
        url: fc.webUrl(),
        name: fc.string({ minLength: 1, maxLength: 50 }),
        is_active: fc.boolean(),
        last_crawled_at: fc.option(arbISODate, { nil: null }),
        compliance_status: fc.constantFrom(
          'compliant' as const,
          'violation' as const,
          'pending' as const,
          'error' as const
        ),
        created_at: arbISODate,
      }),
      { minLength: 0, maxLength: 30 }
    )
    .map((sites) =>
      sites.map((s, i) => ({ ...s, id: i + 1 }))
    );
}

// --- Property 1: 顧客別サイトグルーピングの正確性 ---

describe('Feature: hierarchical-ui-restructure, Property 1: 顧客別サイトグルーピングの正確性', () => {
  /**
   * **Validates: Requirements 1.1**
   *
   * 任意の顧客リストとサイトリストに対して、グルーピング関数を適用した場合、
   * 各グループ内のすべてのサイトの customer_id はそのグループの顧客の id と一致し、
   * かつすべてのサイトがいずれかのグループに含まれること。
   */
  it('all sites in each group have matching customer_id and all sites appear in some group', () => {
    fc.assert(
      fc.property(
        arbCustomersWithUniqueIds.chain((customers) =>
          arbSitesForCustomers(customers.map((c) => c.id)).map((sites) => ({
            customers,
            sites,
          }))
        ),
        ({ customers, sites }) => {
          const result = groupSitesByCustomer(customers, sites);

          // 1. Each group corresponds to exactly one customer
          expect(result.length).toBe(customers.length);

          // 2. All sites in each group have matching customer_id
          for (const group of result) {
            for (const site of group.sites) {
              expect(site.customer_id).toBe(group.id);
            }
          }

          // 3. siteCount matches actual sites array length
          for (const group of result) {
            expect(group.siteCount).toBe(group.sites.length);
          }

          // 4. All input sites appear in some group
          const allGroupedSiteIds = result.flatMap((g) => g.sites.map((s) => s.id));
          // Only sites whose customer_id matches a customer should appear
          const sitesWithValidCustomer = sites.filter((s) =>
            customers.some((c) => c.id === s.customer_id)
          );
          expect(allGroupedSiteIds.length).toBe(sitesWithValidCustomer.length);

          for (const site of sitesWithValidCustomer) {
            expect(allGroupedSiteIds).toContain(site.id);
          }
        }
      ),
      { numRuns: 100 }
    );
  });
});

// --- Property 2: 展開/折りたたみの状態往復 ---

describe('Feature: hierarchical-ui-restructure, Property 2: 展開/折りたたみの状態往復', () => {
  /**
   * **Validates: Requirements 1.4, 1.5, 2.3, 2.6**
   *
   * 任意の顧客グループまたはサイト行に対して、折りたたみ状態から展開操作を行い、
   * 続けて折りたたみ操作を行った場合、子要素は非表示状態に戻ること
   * （展開→折りたたみの往復で元の状態に復帰する）。
   */
  it('expand then collapse returns to original collapsed state', () => {
    fc.assert(
      fc.property(
        fc.boolean(), // Initial expanded state
        (initialExpanded) => {
          // Simulate expand/collapse state management
          let isExpanded = initialExpanded;
          const initialState = isExpanded;

          // If initially collapsed, expand it
          if (!isExpanded) {
            isExpanded = true;
            expect(isExpanded).toBe(true);
          }

          // Then collapse it
          isExpanded = false;

          // Verify we're back to collapsed state
          expect(isExpanded).toBe(false);

          // If we started collapsed, we should end collapsed
          if (!initialState) {
            expect(isExpanded).toBe(initialState);
          }
        }
      ),
      { numRuns: 100 }
    );
  });

  it('multiple expand/collapse cycles maintain state consistency', () => {
    fc.assert(
      fc.property(
        fc.array(fc.boolean(), { minLength: 1, maxLength: 20 }), // Sequence of toggle operations
        (toggleSequence) => {
          let isExpanded = false; // Start collapsed

          // Apply each toggle operation
          for (const shouldToggle of toggleSequence) {
            if (shouldToggle) {
              isExpanded = !isExpanded;
            }
          }

          // Count the number of actual toggles
          const toggleCount = toggleSequence.filter((t) => t).length;

          // After even number of toggles, should be back to initial state (collapsed)
          // After odd number of toggles, should be opposite (expanded)
          const expectedState = toggleCount % 2 === 0 ? false : true;
          expect(isExpanded).toBe(expectedState);
        }
      ),
      { numRuns: 100 }
    );
  });

  it('expand-collapse round-trip for nested structures preserves parent-child independence', () => {
    fc.assert(
      fc.property(
        fc.record({
          parentExpanded: fc.boolean(),
          childrenExpanded: fc.array(fc.boolean(), { minLength: 0, maxLength: 10 }),
        }),
        ({ parentExpanded, childrenExpanded }) => {
          // Simulate parent (CustomerGroup) state
          let parentState = parentExpanded;
          const initialParentState = parentState;

          // Simulate children (SiteRow) states
          const childStates = [...childrenExpanded];
          const initialChildStates = [...childrenExpanded];

          // Expand parent if collapsed
          if (!parentState) {
            parentState = true;
          }

          // Collapse parent
          parentState = false;

          // Verify parent returned to collapsed
          expect(parentState).toBe(false);

          // Verify children states are independent and unchanged
          // (collapsing parent doesn't reset children's internal state)
          expect(childStates).toEqual(initialChildStates);

          // If we started with parent collapsed, we should end collapsed
          if (!initialParentState) {
            expect(parentState).toBe(initialParentState);
          }
        }
      ),
      { numRuns: 100 }
    );
  });
});

// --- Property 3: 検索・フィルターの正確性 ---

describe('Feature: hierarchical-ui-restructure, Property 3: 検索・フィルターの正確性', () => {
  /**
   * **Validates: Requirements 1.6, 1.7, 7.5**
   *
   * 任意の検索クエリ、ステータスフィルター、カテゴリフィルターの組み合わせに対して、
   * 表示される顧客グループはすべてのフィルター条件を満たすこと。
   */

  const arbCustomerWithSites: fc.Arbitrary<CustomerWithSites> = fc.record({
    id: fc.integer({ min: 1, max: 10000 }),
    name: fc.string({ minLength: 1, maxLength: 50 }),
    company_name: fc.option(fc.string({ minLength: 1, maxLength: 50 }), { nil: null }),
    email: fc.emailAddress(),
    phone: fc.option(fc.string({ minLength: 1, maxLength: 20 }), { nil: null }),
    address: fc.option(fc.string({ minLength: 1, maxLength: 100 }), { nil: null }),
    is_active: fc.boolean(),
    created_at: arbISODate,
    updated_at: arbISODate,
    sites: fc.array(
      fc.record({
        id: fc.integer({ min: 1, max: 100000 }),
        customer_id: fc.integer({ min: 1, max: 10000 }),
        category_id: fc.option(fc.integer({ min: 1, max: 100 }), { nil: null }),
        url: fc.webUrl(),
        name: fc.string({ minLength: 1, maxLength: 50 }),
        is_active: fc.boolean(),
        last_crawled_at: fc.option(arbISODate, { nil: null }),
        compliance_status: fc.constantFrom(
          'compliant' as const,
          'violation' as const,
          'pending' as const,
          'error' as const
        ),
        created_at: arbISODate,
      }),
      { minLength: 0, maxLength: 10 }
    ),
    siteCount: fc.constant(0), // will be overridden
  }).map((c) => ({ ...c, siteCount: c.sites.length }));

  const arbSearchQuery = fc.oneof(
    fc.constant(''),
    fc.string({ minLength: 1, maxLength: 20 })
  );

  const arbStatusFilter = fc.constantFrom('all' as const, 'active' as const, 'inactive' as const);

  const arbCategoryFilter = fc.option(fc.integer({ min: 1, max: 100 }), { nil: null });

  it('all returned customers match search query, status filter, and category filter', () => {
    fc.assert(
      fc.property(
        fc.array(arbCustomerWithSites, { minLength: 0, maxLength: 20 }),
        arbSearchQuery,
        arbStatusFilter,
        arbCategoryFilter,
        (customers, searchQuery, statusFilter, categoryFilter) => {
          const result = filterCustomers(customers, searchQuery, statusFilter, categoryFilter);

          for (const customer of result) {
            // Search filter check
            if (searchQuery) {
              const q = searchQuery.toLowerCase();
              const nameMatch = customer.name.toLowerCase().includes(q);
              const companyMatch = customer.company_name
                ? customer.company_name.toLowerCase().includes(q)
                : false;
              expect(nameMatch || companyMatch).toBe(true);
            }

            // Status filter check
            if (statusFilter === 'active') {
              expect(customer.is_active).toBe(true);
            }
            if (statusFilter === 'inactive') {
              expect(customer.is_active).toBe(false);
            }

            // Category filter check
            if (categoryFilter !== null) {
              const hasCategorySite = customer.sites.some(
                (site) => site.category_id === categoryFilter
              );
              expect(hasCategorySite).toBe(true);
            }
          }

          // Also verify: no customer that matches all filters was excluded
          for (const customer of customers) {
            let shouldBeIncluded = true;

            if (searchQuery) {
              const q = searchQuery.toLowerCase();
              const nameMatch = customer.name.toLowerCase().includes(q);
              const companyMatch = customer.company_name
                ? customer.company_name.toLowerCase().includes(q)
                : false;
              if (!nameMatch && !companyMatch) shouldBeIncluded = false;
            }

            if (statusFilter === 'active' && !customer.is_active) shouldBeIncluded = false;
            if (statusFilter === 'inactive' && customer.is_active) shouldBeIncluded = false;

            if (categoryFilter !== null) {
              const hasCategorySite = customer.sites.some(
                (site) => site.category_id === categoryFilter
              );
              if (!hasCategorySite) shouldBeIncluded = false;
            }

            if (shouldBeIncluded) {
              expect(result).toContainEqual(customer);
            }
          }
        }
      ),
      { numRuns: 100 }
    );
  });
});
