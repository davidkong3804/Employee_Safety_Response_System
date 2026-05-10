import { test, expect } from '@playwright/test'

test.describe('Authentication', () => {
  test('login page renders title and form', async ({ page }) => {
    await page.goto('/login')
    await expect(page.getByText('Employee Safety & Response System')).toBeVisible()
    await expect(page.getByPlaceholder('A001 / M001 / E001')).toBeVisible()
    await expect(page.getByPlaceholder('password123')).toBeVisible()
    await expect(page.getByRole('button', { name: /login|登入/i })).toBeVisible()
  })

  test('valid admin login redirects away from /login', async ({ page }) => {
    await page.goto('/login')
    await page.getByPlaceholder('A001 / M001 / E001').fill('A001')
    await page.getByPlaceholder('password123').fill('password123')
    await page.getByRole('button', { name: /login|登入/i }).click()
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 10_000 })
    expect(page.url()).not.toContain('/login')
  })

  test('invalid credentials shows error toast', async ({ page }) => {
    await page.goto('/login')
    await page.getByPlaceholder('A001 / M001 / E001').fill('INVALID')
    await page.getByPlaceholder('password123').fill('wrongpassword')
    await page.getByRole('button', { name: /login|登入/i }).click()
    // react-hot-toast renders notifications
    await expect(page.getByRole('status').first()).toBeVisible({ timeout: 5_000 })
  })

  test('unauthenticated access to protected route redirects to /login', async ({ page }) => {
    await page.goto('/admin/events')
    await expect(page).toHaveURL(/\/login/)
  })

  test('unauthenticated access to employee home redirects to /login', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveURL(/\/login/)
  })
})
