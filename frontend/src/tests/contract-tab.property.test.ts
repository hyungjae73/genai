import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { groupContractsByCategory } from '../components/hierarchy/tabs/ContractTab';
import type { ContractCondition, Category } from '../services/api';

// --- Arbitrary generators ---

const arbISODate = fc
  .integer({ min: 946684800000, max: 1924905600000 }) // 2000-01-01 to 2030-12-31 in ms
  .map((ts) => new Date(ts).toISOString());

const arbCategory: fc.Arbitrary<Category> = fc.record({
  id: fc.integer({ min: 1, max: 100 }),
  name: fc.string({ minLength: 1, maxLength: 50 }),
  description: fc.option(fc.string({ minLength: 1, maxLength: 200 }), { nil: null }),
  color: fc.option(
    fc.constantFrom('#FF0000', '#00FF00', '#0000FF', '#FFFF00', '#FF00FF', '#00FFFF'),
    { nil: null }
  ),
  created_at: arbISODate,
  updated_at: arbISODate,
});

const arbCategoriesWithUniqueIds: fc.Arbitrary<Category[]> = fc
  .uniqueArray(fc.integer({ min: 1, max: 100 }), { minLength: 0, maxLength: 20 })
  .chain((ids) =>
    ids.length === 0
      ? fc.constant([])
      : fc.tuple(...ids.map((id) => arbCategory.map((c) => ({ ...c, id }))))
  );

const arbContractCondition = (
  categoryIds: (number | null)[]
): fc.Arbitrary<ContractCondition> => {
  const categoryIdArb = categoryIds.length > 0
    ? fc.constantFrom(...categoryIds)
    : fc.constant(null);

  return fc.record({
    id: fc.integer({ min: 1, max: 100000 }),
    site_id: fc.integer({ min: 1, max: 10000 }),
    category_id: categoryIdArb,
    version: fc.integer({ min: 1, max: 100 }),
    is_current: fc.boolean(),
    created_at: arbISODate,
    prices: fc.dictionary(
      fc.constantFrom('USD', 'JPY', 'EUR', 'GBP'),
      fc.oneof(
        fc.float({ min: 0, max: 10000 }),
        fc.array(fc.float({ min: 0, max: 10000 }), { minLength: 1, maxLength: 5 })
      ),
      { minKeys: 0, maxKeys: 3 }
    ),
    payment_methods: fc.record({
      allowed: fc.option(
        fc.array(fc.constantFrom('credit_card', 'debit_card', 'paypal', 'bank_transfer'), {
          minLength: 1,
          maxLength: 4,
        }),
        { nil: undefined }
      ),
      required: fc.option(
        fc.array(fc.constantFrom('credit_card', 'debit_card'), {
          minLength: 1,
          maxLength: 2,
        }),
        { nil: undefined }
      ),
    }),
    fees: fc.record({
      percentage: fc.option(
        fc.oneof(
          fc.float({ min: 0, max: 100 }),
          fc.array(fc.float({ min: 0, max: 100 }), { minLength: 1, maxLength: 3 })
        ),
        { nil: undefined }
      ),
      fixed: fc.option(
        fc.oneof(
          fc.float({ min: 0, max: 1000 }),
          fc.array(fc.float({ min: 0, max: 1000 }), { minLength: 1, maxLength: 3 })
        ),
        { nil: undefined }
      ),
    }),
    subscription_terms: fc.option(
      fc.record({
        has_commitment: fc.option(fc.boolean(), { nil: undefined }),
        commitment_months: fc.option(
          fc.oneof(
            fc.integer({ min: 1, max: 36 }),
            fc.array(fc.integer({ min: 1, max: 36 }), { minLength: 1, maxLength: 3 })
          ),
          { nil: undefined }
        ),
        has_cancellation_policy: fc.option(fc.boolean(), { nil: undefined }),
      }),
      { nil: undefined }
    ),
  });
};

const arbContractsForCategories = (
  categoryIds: number[]
): fc.Arbitrary<ContractCondition[]> => {
  // Include null as a possible category_id (for uncategorized contracts)
  const possibleCategoryIds: (number | null)[] = [...categoryIds, null];
  
  return fc.array(arbContractCondition(possibleCategoryIds), {
    minLength: 0,
    maxLength: 50,
  }).map((contracts) =>
    // Ensure unique IDs
    contracts.map((c, i) => ({ ...c, id: i + 1 }))
  );
};

// --- Property 6: 契約条件のカテゴリ別グルーピング ---

describe('Feature: hierarchical-ui-restructure, Property 6: 契約条件のカテゴリ別グルーピング', () => {
  /**
   * **Validates: Requirements 3.3**
   *
   * 任意の契約条件リストに対して、カテゴリ別グルーピング関数を適用した場合、
   * 各グループ内のすべての契約条件の category_id はそのグループのカテゴリIDと一致すること。
   */
  it('all contracts in each group have matching category_id', () => {
    fc.assert(
      fc.property(
        arbCategoriesWithUniqueIds.chain((categories) =>
          arbContractsForCategories(categories.map((c) => c.id)).map((contracts) => ({
            categories,
            contracts,
          }))
        ),
        ({ categories, contracts }) => {
          const result = groupContractsByCategory(contracts, categories);

          // Property: Each group's contracts must have matching category_id
          for (const group of result) {
            for (const contract of group.contracts) {
              // The contract's category_id should match the group's categoryId
              expect(contract.category_id ?? null).toBe(group.categoryId);
            }
          }

          // Additional verification: All contracts appear in exactly one group
          const allGroupedContractIds = result.flatMap((g) =>
            g.contracts.map((c) => c.id)
          );
          const inputContractIds = contracts.map((c) => c.id);

          // Every input contract should appear in the grouped results
          expect(allGroupedContractIds.sort()).toEqual(inputContractIds.sort());

          // No duplicates in grouped results
          const uniqueGroupedIds = new Set(allGroupedContractIds);
          expect(uniqueGroupedIds.size).toBe(allGroupedContractIds.length);
        }
      ),
      { numRuns: 100 }
    );
  }, 30000);

  it('groups with valid category_id have correct category name', () => {
    fc.assert(
      fc.property(
        arbCategoriesWithUniqueIds.chain((categories) =>
          arbContractsForCategories(categories.map((c) => c.id)).map((contracts) => ({
            categories,
            contracts,
          }))
        ),
        ({ categories, contracts }) => {
          const result = groupContractsByCategory(contracts, categories);

          for (const group of result) {
            if (group.categoryId !== null) {
              // Find the corresponding category
              const category = categories.find((c) => c.id === group.categoryId);
              
              if (category) {
                // If category exists, the group name should match
                expect(group.categoryName).toBe(category.name);
              }
            } else {
              // Null category_id should result in "未分類" (uncategorized)
              expect(group.categoryName).toBe('未分類');
            }
          }
        }
      ),
      { numRuns: 100 }
    );
  }, 30000);

  it('uncategorized contracts (category_id = null) are grouped together', () => {
    fc.assert(
      fc.property(
        arbCategoriesWithUniqueIds.chain((categories) =>
          arbContractsForCategories(categories.map((c) => c.id)).map((contracts) => ({
            categories,
            contracts,
          }))
        ),
        ({ categories, contracts }) => {
          const result = groupContractsByCategory(contracts, categories);

          // Find the uncategorized group (if any)
          const uncategorizedGroup = result.find((g) => g.categoryId === null);
          
          // Count contracts with null category_id
          const uncategorizedContracts = contracts.filter((c) => c.category_id === null);

          if (uncategorizedContracts.length > 0) {
            // There should be an uncategorized group
            expect(uncategorizedGroup).toBeDefined();
            expect(uncategorizedGroup!.categoryName).toBe('未分類');
            expect(uncategorizedGroup!.contracts.length).toBe(uncategorizedContracts.length);
            
            // All contracts in this group should have null category_id
            for (const contract of uncategorizedGroup!.contracts) {
              expect(contract.category_id).toBeNull();
            }
          } else {
            // There should be no uncategorized group
            expect(uncategorizedGroup).toBeUndefined();
          }
        }
      ),
      { numRuns: 100 }
    );
  }, 30000);

  it('empty contract list produces empty groups', () => {
    fc.assert(
      fc.property(
        arbCategoriesWithUniqueIds,
        (categories) => {
          const result = groupContractsByCategory([], categories);
          expect(result).toEqual([]);
        }
      ),
      { numRuns: 100 }
    );
  }, 30000);

  it('contracts with non-existent category_id are still grouped', () => {
    fc.assert(
      fc.property(
        arbCategoriesWithUniqueIds.chain((categories) =>
          arbContractsForCategories(categories.map((c) => c.id)).map((contracts) => ({
            categories,
            contracts,
          }))
        ),
        ({ categories, contracts }) => {
          // Add a contract with a category_id that doesn't exist in categories
          const nonExistentCategoryId = 99999;
          const contractWithNonExistentCategory: ContractCondition = {
            id: 999999,
            site_id: 1,
            category_id: nonExistentCategoryId,
            version: 1,
            is_current: true,
            created_at: new Date().toISOString(),
            prices: {},
            payment_methods: {},
            fees: {},
          };

          const allContracts = [...contracts, contractWithNonExistentCategory];
          const result = groupContractsByCategory(allContracts, categories);

          // Find the group with the non-existent category
          const nonExistentGroup = result.find((g) => g.categoryId === nonExistentCategoryId);
          
          expect(nonExistentGroup).toBeDefined();
          expect(nonExistentGroup!.categoryName).toBe('未分類'); // Should default to uncategorized
          expect(nonExistentGroup!.contracts).toContainEqual(contractWithNonExistentCategory);
        }
      ),
      { numRuns: 100 }
    );
  }, 30000);
});
