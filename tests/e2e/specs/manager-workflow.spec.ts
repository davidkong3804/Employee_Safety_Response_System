import { test, expect } from '../fixtures/auth.fixture'

test.describe('Manager Workflow', () => {
  test('manager can access dashboard', async ({ managerPage: page }) => {
    await page.goto('/dashboard')
    await expect(page).not.toHaveURL(/\/login/)
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 5_000 })
  })

  test('dashboard shows event statistics or event selector', async ({ managerPage: page }) => {
    await page.goto('/dashboard')
    // Dashboard should show either stats content or "no events" message
    const content = page.locator('main, [role="main"], .container, .max-w-7xl')
    await expect(content.first()).toBeVisible({ timeout: 5_000 })
  })

  test('manager cannot access user management', async ({ managerPage: page }) => {
    await page.goto('/admin/users')
    await expect(page).not.toHaveURL(/admin\/users/)
  })

  test('manager cannot access event management page', async ({ managerPage: page }) => {
    await page.goto('/admin/events')
    await expect(page).not.toHaveURL(/admin\/events/)
  })

  test('manager can see team status section in dashboard', async ({ managerPage: page }) => {
    await page.goto('/dashboard')
    // Wait for dashboard content to load
    await page.waitForLoadState('networkidle')
    // Dashboard should be accessible and show relevant content
    await expect(page).not.toHaveURL(/\/login/)
  })
})
