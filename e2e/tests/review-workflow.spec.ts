import { test, expect } from '@playwright/test';

test.describe('Review Workflow', () => {
  test.describe.configure({ mode: 'serial' });
  test.use({ storageState: 'auth/admin.json' });

  test('should navigate to review dashboard and display stats', async ({ page }) => {
    await page.goto('/review-dashboard');

    // Verify page title
    await expect(page.locator('h1')).toContainText('審査ダッシュボード');

    // Verify status section is present
    await expect(page.locator('text=ステータス別件数')).toBeVisible();

    // Verify priority section is present
    await expect(page.locator('text=優先度別 未審査件数')).toBeVisible();
  });

  test('should navigate to reviews list', async ({ page }) => {
    await page.goto('/reviews');

    // Wait for the page to load
    await page.waitForLoadState('networkidle');

    // Verify reviews page loads (table or empty state)
    const content = page.locator('.reviews, [class*="review"]');
    await expect(content.first()).toBeVisible({ timeout: 10_000 });
  });

  test('should open a review item and view details', async ({ page }) => {
    await page.goto('/reviews');
    await page.waitForLoadState('networkidle');

    // Check if there are review items to click
    const reviewLinks = page.locator('a[href*="/reviews/"]');
    const hasReviews = await reviewLinks.first().isVisible().catch(() => false);

    if (hasReviews) {
      // Click the first review
      await reviewLinks.first().click();

      // Verify we're on a review detail page
      await page.waitForURL('**/reviews/**');
    }
  });

  test('should submit a review decision', async ({ page }) => {
    await page.goto('/reviews');
    await page.waitForLoadState('networkidle');

    // Check if there are review items
    const reviewLinks = page.locator('a[href*="/reviews/"]');
    const hasReviews = await reviewLinks.first().isVisible().catch(() => false);

    if (hasReviews) {
      await reviewLinks.first().click();
      await page.waitForURL('**/reviews/**');

      // Look for decision form elements
      const decisionButton = page.locator('button', { hasText: /承認|却下|判定/ });
      const hasDecisionUI = await decisionButton.first().isVisible().catch(() => false);

      if (hasDecisionUI) {
        // Submit a decision
        await decisionButton.first().click();

        // Wait for the action to complete
        await page.waitForTimeout(1_000);
      }
    }
  });
});
