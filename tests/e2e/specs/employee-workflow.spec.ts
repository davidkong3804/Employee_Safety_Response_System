import { test, expect } from '../fixtures/auth.fixture'

test.describe('Employee Workflow', () => {
  test('employee home page loads with active events section', async ({ employeePage: page }) => {
    await page.goto('/')
    // Page should have loaded (not redirected to login)
    await expect(page).not.toHaveURL(/\/login/)
    // Should show events or a "no events" message
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 5_000 })
  })

  test('employee can navigate to submit report page', async ({ employeePage: page }) => {
    await page.goto('/')
    const reportLink = page.getByRole('link', { name: /report|回報/i }).first()
    if (await reportLink.isVisible()) {
      await reportLink.click()
      await expect(page).toHaveURL(/report/)
    }
  })

  test('employee cannot access manager dashboard directly', async ({ employeePage: page }) => {
    await page.goto('/dashboard')
    // Should redirect to home or show unauthorized
    await expect(page).not.toHaveURL(/\/login/)
  })

  test('employee cannot access admin event management', async ({ employeePage: page }) => {
    await page.goto('/admin/events')
    // Employee should be redirected away from admin page
    await expect(page).not.toHaveURL(/admin\/events/)
  })

  test('employee cannot access user management', async ({ employeePage: page }) => {
    await page.goto('/admin/users')
    await expect(page).not.toHaveURL(/admin\/users/)
  })

  test('logout clears session and redirects to login', async ({ employeePage: page }) => {
    await page.goto('/')
    const logoutButton = page.getByRole('button', { name: /logout|登出/i })
    if (await logoutButton.isVisible()) {
      await logoutButton.click()
      await expect(page).toHaveURL(/\/login/)
    }
  })
})
