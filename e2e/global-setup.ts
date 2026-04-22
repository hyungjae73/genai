import { chromium, type FullConfig } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

const ROLES = [
  { role: 'admin', username: 'hjkim93', password: 'Admin1234!', file: 'auth/admin.json' },
  { role: 'reviewer', username: 'reviewer1', password: 'Reviewer1!', file: 'auth/reviewer.json' },
  { role: 'viewer', username: 'viewer1', password: 'Viewer1!', file: 'auth/viewer.json' },
] as const;

async function globalSetup(config: FullConfig) {
  const baseURL = config.projects[0].use.baseURL || 'http://localhost:5173';

  // Ensure auth directory exists
  const authDir = path.join(__dirname, 'auth');
  if (!fs.existsSync(authDir)) {
    fs.mkdirSync(authDir, { recursive: true });
  }

  const browser = await chromium.launch();

  for (const { role, username, password, file } of ROLES) {
    const context = await browser.newContext();
    const page = await context.newPage();

    await page.goto(`${baseURL}/login`);
    await page.fill('[placeholder="ユーザ名を入力"]', username);
    await page.fill('[placeholder="パスワードを入力"]', password);
    await page.click('button[type="submit"]');
    await page.waitForURL('**/');

    await context.storageState({ path: path.join(__dirname, file) });
    await context.close();
  }

  await browser.close();
}

export default globalSetup;
