import { test, expect } from '@playwright/test';

test.describe('Login Flow', () => {
  test('should login with valid credentials and redirect to dashboard', async ({ page }) => {
    await page.goto('/login');

    // Verify login page elements
    await expect(page.locator('h1')).toContainText('ログイン');

    // Fill credentials
    await page.fill('[placeholder="ユーザ名を入力"]', 'hjkim93');
    await page.fill('[placeholder="パスワードを入力"]', 'Admin1234!');

    // Submit
    await page.click('button[type="submit"]');

    // Verify redirect to dashboard
    await page.waitForURL('**/');
    await expect(page).not.toHaveURL(/\/login/);
  });

  test('should show error for invalid credentials', async ({ page }) => {
    await page.goto('/login');

    await page.fill('[placeholder="ユーザ名を入力"]', 'invaliduser');
    await page.fill('[placeholder="パスワードを入力"]', 'WrongPass1!');
    await page.click('button[type="submit"]');

    // Verify error message
    await expect(page.locator('[role="alert"]')).toBeVisible();
  });

  test('should show validation error for empty fields', async ({ page }) => {
    await page.goto('/login');

    await page.click('button[type="submit"]');

    // Verify client-side validation error
    await expect(page.locator('[role="alert"]')).toContainText('ユーザ名とパスワードを入力してください');
  });
});
