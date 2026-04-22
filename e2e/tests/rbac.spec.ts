import { test, expect } from '@playwright/test';

test.describe('RBAC — Viewer Access', () => {
  test.use({ storageState: 'auth/viewer.json' });

  test('viewer cannot access user management page', async ({ page }) => {
    await page.goto('/users');

    // Should see 403 forbidden message or redirect
    const forbidden = page.locator('text=権限がありません');
    const loginPage = page.locator('h1', { hasText: 'ログイン' });
    await expect(forbidden.or(loginPage)).toBeVisible({ timeout: 10_000 });
  });

  test('viewer cannot access categories page (admin only)', async ({ page }) => {
    await page.goto('/categories');

    const forbidden = page.locator('text=権限がありません');
    const loginPage = page.locator('h1', { hasText: 'ログイン' });
    await expect(forbidden.or(loginPage)).toBeVisible({ timeout: 10_000 });
  });

  test('viewer can access dashboard', async ({ page }) => {
    await page.goto('/');

    // Dashboard should load without access denied
    await expect(page.locator('text=権限がありません')).not.toBeVisible({ timeout: 5_000 });
  });
});

test.describe('RBAC — Reviewer Access', () => {
  test.use({ storageState: 'auth/reviewer.json' });

  test('reviewer can access review dashboard', async ({ page }) => {
    await page.goto('/review-dashboard');

    await expect(page.locator('h1')).toContainText('審査ダッシュボード');
  });

  test('reviewer can access reviews list', async ({ page }) => {
    await page.goto('/reviews');

    // Should load without access denied
    await expect(page.locator('text=権限がありません')).not.toBeVisible({ timeout: 5_000 });
  });

  test('reviewer cannot access user management page', async ({ page }) => {
    await page.goto('/users');

    const forbidden = page.locator('text=権限がありません');
    const loginPage = page.locator('h1', { hasText: 'ログイン' });
    await expect(forbidden.or(loginPage)).toBeVisible({ timeout: 10_000 });
  });

  test('reviewer cannot access categories page (admin only)', async ({ page }) => {
    await page.goto('/categories');

    const forbidden = page.locator('text=権限がありません');
    const loginPage = page.locator('h1', { hasText: 'ログイン' });
    await expect(forbidden.or(loginPage)).toBeVisible({ timeout: 10_000 });
  });
});

test.describe('RBAC — Admin Access', () => {
  test.use({ storageState: 'auth/admin.json' });

  test('admin can access user management page', async ({ page }) => {
    await page.goto('/users');

    // Should load without access denied
    await expect(page.locator('text=権限がありません')).not.toBeVisible({ timeout: 5_000 });
  });

  test('admin can access categories page', async ({ page }) => {
    await page.goto('/categories');

    await expect(page.locator('text=権限がありません')).not.toBeVisible({ timeout: 5_000 });
  });

  test('admin can access review dashboard', async ({ page }) => {
    await page.goto('/review-dashboard');

    await expect(page.locator('h1')).toContainText('審査ダッシュボード');
  });

  test('admin can access all pages', async ({ page }) => {
    const pages = ['/', '/sites', '/alerts', '/reviews', '/review-dashboard', '/users', '/categories'];

    for (const path of pages) {
      await page.goto(path);
      await expect(page.locator('text=権限がありません')).not.toBeVisible({ timeout: 5_000 });
    }
  });
});
