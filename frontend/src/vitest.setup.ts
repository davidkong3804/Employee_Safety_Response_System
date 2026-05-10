import '@testing-library/jest-dom'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

// Minimal i18n setup for component tests
if (!i18n.isInitialized) {
  i18n.use(initReactI18next).init({
    lng: 'en',
    fallbackLng: 'en',
    resources: {
      en: {
        translation: {
          'status.safe': 'Safe',
          'status.need_help': 'Need Help',
          'status.unreported': 'Unreported',
          'login.title': 'Safety Response System',
          'login.employeeId': 'Employee ID',
          'login.password': 'Password',
          'login.submit': 'Login',
          'login.error': 'Invalid employee ID or password',
          'nav.logout': 'Logout',
          'nav.home': 'Home',
          'nav.dashboard': 'Dashboard',
          'nav.events': 'Event Management',
          'nav.users': 'User Management',
        },
      },
    },
    interpolation: { escapeValue: false },
  })
}

afterEach(() => {
  cleanup()
  localStorage.clear()
  vi.clearAllMocks()
})
