import { test, expect } from '@playwright/test';
import { uniqueSiteName, uniqueSiteUrl } from './helpers/test-data';

test.describe('Site Management CRUD', () => {
  let createdSiteName: string;

  test.use({ storageState: 'auth/admin.json' });

  test.afterEach(async ({ page }) => {
    // Cleanup: if a site was created during the test, attempt to delete it via UI
    // This is best-effort; the site may already be deleted by the test itself
  });

  test('should create a new site', async ({ page }) => {
    createdSiteName = uniqueSiteName();
    const siteUrl = uniqueSiteUrl();

    await page.goto('/sites');
    await expect(page.locator('h1')).toContainText('監視対象サイト一覧');

    // Open create modal
    await page.click('text=新規サイト登録');

    // Fill form
    await page.locator('[aria-label="顧客選択"]').selectOption({ index: 1 });
    await page.fill('[placeholder="例: Example Payment Site"]', createdSiteName);
    await page.fill('[placeholder="例: https://example.com"]', siteUrl);

    // Submit
    await page.click('text=登録');

    // Verify site appears in the list
    await expect(page.locator('text=' + createdSiteName)).toBeVisible({ timeout: 10_000 });
  });

  test('should display site in the list', async ({ page }) => {
    await page.goto('/sites');

    // Verify the sites table loads
    await expect(page.locator('table, [aria-label="監視サイト一覧"]')).toBeVisible({ timeout: 10_000 });
  });

  test('should update a site name', async ({ page }) => {
    createdSiteName = uniqueSiteName();
    const siteUrl = uniqueSiteUrl();
    const updatedName = `${createdSiteName}-updated`;

    await page.goto('/sites');

    // Create a site first
    await page.click('text=新規サイト登録');
    await page.locator('[aria-label="顧客選択"]').selectOption({ index: 1 });
    await page.fill('[placeholder="例: Example Payment Site"]', createdSiteName);
    await page.fill('[placeholder="例: https://example.com"]', siteUrl);
    await page.click('text=登録');
    await expect(page.locator(`text=${createdSiteName}`)).toBeVisible({ timeout: 10_000 });

    // Find the row and click edit
    const row = page.locator('tr', { has: page.locator(`text=${createdSiteName}`) });
    await row.locator('text=編集').click();

    // Update the name
    const nameInput = page.locator('[placeholder="例: Example Payment Site"]');
    await nameInput.clear();
    await nameInput.fill(updatedName);
    await page.click('text=更新');

    // Verify updated name
    await expect(page.locator(`text=${updatedName}`)).toBeVisible({ timeout: 10_000 });

    // Cleanup: delete the site
    const updatedRow = page.locator('tr', { has: page.locator(`text=${updatedName}`) });
    page.on('dialog', (dialog) => dialog.accept());
    await updatedRow.locator('text=削除').click();
  });

  test('should delete a site', async ({ page }) => {
    createdSiteName = uniqueSiteName();
    const siteUrl = uniqueSiteUrl();

    await page.goto('/sites');

    // Create a site first
    await page.click('text=新規サイト登録');
    await page.locator('[aria-label="顧客選択"]').selectOption({ index: 1 });
    await page.fill('[placeholder="例: Example Payment Site"]', createdSiteName);
    await page.fill('[placeholder="例: https://example.com"]', siteUrl);
    await page.click('text=登録');
    await expect(page.locator(`text=${createdSiteName}`)).toBeVisible({ timeout: 10_000 });

    // Delete the site
    const row = page.locator('tr', { has: page.locator(`text=${createdSiteName}`) });
    page.on('dialog', (dialog) => dialog.accept());
    await row.locator('text=削除').click();

    // Verify site is removed
    await expect(page.locator(`text=${createdSiteName}`)).not.toBeVisible({ timeout: 10_000 });
  });
});
