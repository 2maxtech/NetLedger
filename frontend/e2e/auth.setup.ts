/**
 * Shared auth setup — logs in once and saves storage state for all tests.
 *
 * Set credentials via environment variables:
 *   E2E_USERNAME=admin E2E_PASSWORD=yourpass npm run test:e2e
 */
import { test as setup, expect } from '@playwright/test'
import { fileURLToPath } from 'url'
import { dirname, join } from 'path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const AUTH_FILE = join(__dirname, '../.auth/user.json')

setup('authenticate as admin', async ({ page }) => {
  const username = process.env.E2E_USERNAME
  const password = process.env.E2E_PASSWORD

  if (!username || !password) {
    throw new Error(
      'E2E_USERNAME and E2E_PASSWORD must be set.\n' +
      'Run: E2E_USERNAME=admin E2E_PASSWORD=yourpass npm run test:e2e'
    )
  }

  await page.goto('/login')
  await expect(page.locator('#username')).toBeVisible({ timeout: 5000 })

  await page.fill('#username', username)
  await page.fill('#password', password)
  await page.click('button[type="submit"]')

  // Check for login error
  const errorMsg = page.locator('text=Invalid').or(page.locator('text=incorrect'))
  const dashboard = page.locator('text=Dashboard')

  await expect(dashboard.or(errorMsg)).toBeVisible({ timeout: 10_000 })

  if (await errorMsg.isVisible().catch(() => false)) {
    throw new Error('Login failed — check E2E_USERNAME and E2E_PASSWORD')
  }

  await expect(page).toHaveURL(/\/dashboard/, { timeout: 5_000 })
  await page.context().storageState({ path: AUTH_FILE })
})
