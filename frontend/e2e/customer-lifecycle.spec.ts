/**
 * E2E: Full customer lifecycle — create, invoice, print, disconnect,
 * reconnect, change plan, delete.
 *
 * Runs against the live app with real auth. Uses a unique PPPoE username
 * per run so tests are idempotent.
 */
import { test, expect, Page } from '@playwright/test'
import { fileURLToPath } from 'url'
import { dirname, join } from 'path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const AUTH_FILE = join(__dirname, '../.auth/user.json')

test.use({ storageState: AUTH_FILE })

const suffix = Date.now().toString(36)
const TEST_CUSTOMER = {
  full_name: `E2E Test ${suffix}`,
  email: `e2e-${suffix}@test.local`,
  pppoe_username: `e2e_${suffix}`,
  pppoe_password: 'testpass123',
}

let customerId: string

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function navigateTo(page: Page, path: string) {
  await page.goto(`/dashboard${path}`)
  await page.waitForLoadState('networkidle')
}

async function waitForToastOrTable(page: Page) {
  // Wait for either success feedback or table refresh
  await page.waitForTimeout(1000)
}

// ---------------------------------------------------------------------------
// Tests run in order — each depends on the previous
// ---------------------------------------------------------------------------

test.describe.serial('Customer lifecycle', () => {

  test('1. Login and reach dashboard', async ({ page }) => {
    await page.goto('/dashboard')
    await expect(page).toHaveURL(/\/dashboard/)
    await expect(page.locator('text=Dashboard')).toBeVisible()
  })

  test('2. Navigate to customers page', async ({ page }) => {
    await navigateTo(page, '/customers')
    await expect(page.locator('text=Add Customer')).toBeVisible()
  })

  test('3. Create a new customer', async ({ page }) => {
    await navigateTo(page, '/customers')

    // Open add modal
    await page.click('text=Add Customer')
    await expect(page.locator('text=Create Customer').last()).toBeVisible({ timeout: 5000 })

    // Fill form
    await page.fill('input[placeholder="Juan Dela Cruz"]', TEST_CUSTOMER.full_name)
    await page.fill('input[placeholder="juan@example.com"]', TEST_CUSTOMER.email)
    await page.fill('input[placeholder="juan.delacruz"]', TEST_CUSTOMER.pppoe_username)

    // Clear auto-generated password and type ours
    const pwField = page.locator('input').filter({ has: page.locator('[placeholder]') }).nth(4)
    // Find the pppoe_password field — it's after pppoe_username
    const passwordInput = page.locator('input[type="text"]').filter({ hasText: '' })
    // Use a more specific approach: find by nearby label
    const pwInput = page.getByLabel(/PPPoE Password/i).or(
      page.locator('input').nth(4)
    ).first()
    await pwInput.fill(TEST_CUSTOMER.pppoe_password)

    // Select a plan (first available)
    const planSelect = page.getByLabel(/Plan/i).or(
      page.locator('select').first()
    ).first()
    await planSelect.selectOption({ index: 1 })

    // Submit
    const submitBtn = page.locator('button:has-text("Create Customer")')
    await submitBtn.click()

    // Wait for modal to close and customer to appear in table
    await page.waitForTimeout(2000)

    // Verify customer appears in search
    await page.fill('input[placeholder*="Search"]', TEST_CUSTOMER.pppoe_username)
    await page.waitForTimeout(1000)
    await expect(page.locator(`text=${TEST_CUSTOMER.full_name}`)).toBeVisible({ timeout: 5000 })

    // Get customer ID from the row link
    const customerLink = page.locator(`a:has-text("${TEST_CUSTOMER.full_name}")`)
    const href = await customerLink.getAttribute('href')
    if (href) {
      customerId = href.split('/').pop() || ''
    }
  })

  test('4. Customer has MikroTik secret synced', async ({ page }) => {
    test.skip(!customerId, 'No customer created')

    // Go to customer detail page
    await navigateTo(page, `/customers/${customerId}`)

    // Check that mikrotik_secret_id is shown (not null/empty)
    // The detail page should show the MT secret ID somewhere
    const pageContent = await page.textContent('body')
    // We can also verify via API
    const response = await page.request.get(`/api/v1/customers/${customerId}`)
    const data = await response.json()
    expect(data.mikrotik_secret_id).toBeTruthy()
    expect(data.pppoe_username).toBe(TEST_CUSTOMER.pppoe_username)
    expect(data.status).toBe('active')
  })

  test('5. Generate invoice for customer', async ({ page }) => {
    test.skip(!customerId, 'No customer created')

    await navigateTo(page, '/billing/invoices')

    // Click "Generate for Customer"
    await page.click('text=Generate for Customer')
    await page.waitForTimeout(500)

    // Search for our customer in the modal
    const searchInput = page.locator('input[placeholder*="Search"]').last()
    await searchInput.fill(TEST_CUSTOMER.full_name)
    await page.waitForTimeout(1000)

    // Click the customer in the dropdown/results
    await page.click(`text=${TEST_CUSTOMER.full_name}`)
    await page.waitForTimeout(500)

    // Confirm generation
    const generateBtn = page.locator('button:has-text("Generate")').last()
    await generateBtn.click()
    await page.waitForTimeout(2000)

    // Verify invoice appears
    await page.fill('input[placeholder*="Search"]', '')
    await page.waitForTimeout(500)
    await expect(page.locator(`text=${TEST_CUSTOMER.full_name}`).first()).toBeVisible({ timeout: 5000 })
  })

  test('6. Print invoice opens PDF (not auth error)', async ({ page }) => {
    test.skip(!customerId, 'No customer created')

    await navigateTo(page, '/billing/invoices')
    await page.waitForTimeout(1000)

    // Find our customer's invoice row and click the print button
    const row = page.locator('tr', { hasText: TEST_CUSTOMER.full_name }).first()

    // Listen for new page/popup (PDF opens in new tab)
    const popupPromise = page.waitForEvent('popup', { timeout: 10_000 })
    await row.locator('button[title="Print"]').click()

    const popup = await popupPromise
    await popup.waitForLoadState()

    // The popup should show a PDF (blob URL), NOT a login page or error
    const url = popup.url()
    expect(url).toMatch(/^blob:|\.pdf/)

    // Should NOT contain "not authenticated" or redirect to login
    const content = await popup.textContent('body').catch(() => '')
    expect(content).not.toContain('not authenticated')
    expect(content).not.toContain('Not authenticated')

    await popup.close()
  })

  test('7. Download invoice PDF works', async ({ page }) => {
    test.skip(!customerId, 'No customer created')

    await navigateTo(page, '/billing/invoices')
    await page.waitForTimeout(1000)

    const row = page.locator('tr', { hasText: TEST_CUSTOMER.full_name }).first()

    // Click download — should trigger file download
    const downloadPromise = page.waitForEvent('download', { timeout: 10_000 })
    await row.locator('button[title="Download PDF"]').click()
    const download = await downloadPromise

    expect(download.suggestedFilename()).toMatch(/invoice.*\.pdf/i)
  })

  test('8. Disconnect customer', async ({ page }) => {
    test.skip(!customerId, 'No customer created')

    await navigateTo(page, `/customers/${customerId}`)

    // Find and click disconnect button
    await page.click('button:has-text("Disconnect")')
    await page.waitForTimeout(500)

    // Confirm if there's a confirmation dialog
    const confirmBtn = page.locator('button:has-text("Confirm")').or(
      page.locator('button:has-text("Yes")')
    ).first()
    if (await confirmBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await confirmBtn.click()
    }

    await page.waitForTimeout(2000)

    // Verify status changed
    const response = await page.request.get(`/api/v1/customers/${customerId}`)
    const data = await response.json()
    expect(data.status).toBe('disconnected')
  })

  test('9. Reconnect customer', async ({ page }) => {
    test.skip(!customerId, 'No customer created')

    await navigateTo(page, `/customers/${customerId}`)

    await page.click('button:has-text("Reconnect")')
    await page.waitForTimeout(500)

    const confirmBtn = page.locator('button:has-text("Confirm")').or(
      page.locator('button:has-text("Yes")')
    ).first()
    if (await confirmBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await confirmBtn.click()
    }

    await page.waitForTimeout(2000)

    const response = await page.request.get(`/api/v1/customers/${customerId}`)
    const data = await response.json()
    expect(data.status).toBe('active')
    expect(data.mikrotik_secret_id).toBeTruthy()
  })

  test('10. Delete customer (cleanup)', async ({ page }) => {
    test.skip(!customerId, 'No customer created')

    await navigateTo(page, `/customers/${customerId}`)

    // Click delete
    await page.click('button:has-text("Delete")')
    await page.waitForTimeout(500)

    // Fill admin password for confirmation
    const pwInput = page.locator('input[type="password"]').last()
    await pwInput.fill(process.env.E2E_PASSWORD || 'admin123')

    // Confirm delete
    const confirmBtn = page.locator('button:has-text("Confirm Delete")').or(
      page.locator('button:has-text("Delete")')
    ).last()
    await confirmBtn.click()

    await page.waitForTimeout(2000)

    // Verify customer is gone
    const response = await page.request.get(`/api/v1/customers/${customerId}`)
    expect([404, 200]).toContain(response.status())
    if (response.status() === 200) {
      const data = await response.json()
      expect(data.status).toBe('terminated')
    }
  })
})
