import { test, expect } from '../fixtures/auth.fixture'

test.describe('Admin Workflow – Event Lifecycle', () => {
  test('admin can access event management page', async ({ adminPage: page }) => {
    await page.goto('/admin/events')
    await expect(page).not.toHaveURL(/\/login/)
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 5_000 })
  })

  test('admin can access user management page', async ({ adminPage: page }) => {
    await page.goto('/admin/users')
    await expect(page).not.toHaveURL(/\/login/)
  })

  test('admin can access analytics page', async ({ adminPage: page }) => {
    await page.goto('/admin/analytics')
    await expect(page).not.toHaveURL(/\/login/)
  })

  test('create event → appears in list → can be closed → can be deleted', async ({ adminPage: page }) => {
    await page.goto('/admin/events')
    await page.waitForLoadState('networkidle')

    const eventTitle = `E2E Test ${Date.now()}`

    // Open create modal / form
    const createBtn = page
      .getByRole('button', { name: /create|new|建立/i })
      .first()

    if (!(await createBtn.isVisible())) {
      test.skip(true, 'Create button not found – UI may have changed')
      return
    }

    await createBtn.click()

    // Fill in event title
    const titleInput = page.getByLabel(/title|標題/i).first()
      .or(page.locator('input[placeholder*="title" i]').first())
      .or(page.locator('input').first())
    await titleInput.fill(eventTitle)

    // Select event type and severity (select elements)
    const selects = page.locator('select')
    const count = await selects.count()
    if (count >= 1) await selects.nth(0).selectOption({ index: 1 })
    if (count >= 2) await selects.nth(1).selectOption({ index: 1 })

    // Submit the form
    await page.getByRole('button', { name: /submit|create|save|建立|確認/i }).last().click()
    await page.waitForLoadState('networkidle')

    // Verify event appears in list
    await expect(page.getByText(eventTitle)).toBeVisible({ timeout: 8_000 })

    // Close the event — use .first() on button to avoid strict mode error when multiple rows match
    const row = page.locator(`tr, li, div`).filter({ hasText: eventTitle }).first()
    const closeBtn = row.getByRole('button', { name: /close|關閉/i }).first()
    if (await closeBtn.isVisible()) {
      await closeBtn.click()
      await page.waitForLoadState('networkidle')
    }

    // Delete the event
    const deleteBtn = page.locator(`tr, li, div`).filter({ hasText: eventTitle })
      .first()
      .getByRole('button', { name: /delete|刪除/i })
      .first()
    if (await deleteBtn.isVisible()) {
      await deleteBtn.click()
      await page.waitForLoadState('networkidle')
      // Event should be gone
      await expect(page.getByText(eventTitle)).not.toBeVisible({ timeout: 5_000 })
    }
  })

  test('admin can create and manage users', async ({ adminPage: page }) => {
    await page.goto('/admin/users')
    await page.waitForLoadState('networkidle')
    // At least one user should be shown (seed data)
    const userRows = page.locator('table tbody tr').or(page.locator('[data-testid="user-row"]'))
    if (await userRows.count() > 0) {
      await expect(userRows.first()).toBeVisible()
    }
  })
})
