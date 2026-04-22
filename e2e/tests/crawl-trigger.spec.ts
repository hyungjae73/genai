import { test, expect } from '@playwright/test';

test.describe('Crawl Trigger', () => {
  test.use({ storageState: 'auth/admin.json' });

  test('should trigger a crawl and poll for completion', async ({ page }) => {
    await page.goto('/sites');
    await page.waitForLoadState('networkidle');

    // Find a site row with a crawl button
    const crawlButton = page.locator('button', { hasText: '今すぐクロール' }).first();
    const hasSites = await crawlButton.isVisible().catch(() => false);

    if (hasSites) {
      // Trigger crawl
      await crawlButton.click();

      // Verify the button changes to crawling state
      await expect(
        page.locator('button', { hasText: 'クロール中...' }).first()
      ).toBeVisible({ timeout: 5_000 });

      // Wait for crawl to complete (poll via UI — toast notification)
      // The crawl may take a while, so we use a generous timeout
      const toast = page.locator('.toast');
      await expect(toast).toBeVisible({ timeout: 60_000 });

      // Verify the crawl button returns to normal state
      await expect(
        page.locator('button', { hasText: '今すぐクロール' }).first()
      ).toBeVisible({ timeout: 60_000 });
    }
  });

  test('should display crawl results after completion', async ({ page }) => {
    await page.goto('/sites');
    await page.waitForLoadState('networkidle');

    // Check if any site has a last crawled date (clickable)
    const crawlDateButton = page.locator('.crawl-date-button').first();
    const hasCrawlResults = await crawlDateButton.isVisible().catch(() => false);

    if (hasCrawlResults) {
      // Click to view crawl result
      await crawlDateButton.click();

      // Verify modal opens with crawl result details
      await expect(page.locator('text=クロール結果詳細')).toBeVisible({ timeout: 5_000 });

      // Verify result details are shown
      await expect(page.locator('.crawl-result-details')).toBeVisible({ timeout: 10_000 });
    }
  });
});
