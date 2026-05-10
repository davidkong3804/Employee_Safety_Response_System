import { test as base, type Page } from '@playwright/test'

async function loginAs(page: Page, employeeId: string, password = 'password123') {
  await page.goto('/login')
  await page.getByPlaceholder('A001 / M001 / E001').fill(employeeId)
  await page.getByPlaceholder('password123').fill(password)
  await page.getByRole('button', { name: 'Login' }).click()
  await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 10_000 })
}

type AuthFixtures = {
  adminPage: Page
  managerPage: Page
  employeePage: Page
}

export const test = base.extend<AuthFixtures>({
  adminPage: async ({ browser }, use) => {
    const context = await browser.newContext()
    const page = await context.newPage()
    await loginAs(page, 'A001')
    await use(page)
    await context.close()
  },

  managerPage: async ({ browser }, use) => {
    const context = await browser.newContext()
    const page = await context.newPage()
    await loginAs(page, 'M001')
    await use(page)
    await context.close()
  },

  employeePage: async ({ browser }, use) => {
    const context = await browser.newContext()
    const page = await context.newPage()
    await loginAs(page, 'E001')
    await use(page)
    await context.close()
  },
})

export { expect } from '@playwright/test'
