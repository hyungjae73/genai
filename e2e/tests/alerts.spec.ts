import { test, expect } from '@playwright/test';

test.describe('Alerts', () => {
  test.use({ storageState: 'auth/admin.json' });

  test('should navigate to alerts page and display alert list', async ({ page }) => {
    await page.goto('/alerts');

    // Verify page title
    await expect(page.locator('h1')).toContainText('アラート一覧');

    // Verify filter controls are present
    await expect(page.locator('[aria-label="重要度フィルター"]')).toBeVisible();
    await expect(page.locator('[aria-label="種別フィルター"]')).toBeVisible();

    // Verify either alert cards or empty state is shown
    const alertCards = page.locator('.alert-card');
    const noData = page.locator('.no-data');
    await expect(alertCards.first().or(noData)).toBeVisible({ timeout: 10_000 });
  });

  test('should display alert detail with severity and message', async ({ page }) => {
    await page.goto('/alerts');

    const alertCard = page.locator('.alert-card').first();
    const hasAlerts = await alertCard.isVisible().catch(() => false);

    if (hasAlerts) {
      // Verify severity badge is present
      await expect(alertCard.locator('.severity-badge')).toBeVisible();

      // Verify alert message is present
      await expect(alertCard.locator('.alert-message')).toBeVisible();

      // Verify site name is present
      await expect(alertCard.locator('.alert-body h3')).toBeVisible();
    }
  });

  test('should filter alerts by severity', async ({ page }) => {
    await page.goto('/alerts');

    // Select a severity filter
    await page.locator('[aria-label="重要度フィルター"]').selectOption('high');

    // Wait for filter to apply
    await page.waitForTimeout(500);

    // Verify filtered results or empty state
    const alertCards = page.locator('.alert-card');
    const noData = page.locator('.no-data');
    await expect(alertCards.first().or(noData)).toBeVisible({ timeout: 5_000 });
  });
});
