/**
 * Generate a unique site name for E2E tests to avoid data collisions.
 */
export function uniqueSiteName(): string {
  return `e2e-site-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

/**
 * Generate a unique URL for E2E test sites.
 */
export function uniqueSiteUrl(): string {
  return `https://e2e-test-${Date.now()}-${Math.random().toString(36).slice(2, 7)}.example.com`;
}
