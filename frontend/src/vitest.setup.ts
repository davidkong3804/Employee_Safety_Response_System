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
          'app.title': 'Safety Response System',
          'report.title': 'Safety Report',
          'report.imSafe': "I'm Safe",
          'report.needHelp': 'Need Help',
          'report.message': 'Additional message (optional)',
          'report.submitted': 'Report submitted!',
          'report.failed': 'Report failed, please retry',
          'report.alreadyReported': 'You have already reported',
          'report.status': 'Your Status',
          'report.updateHint': 'Want to update? Tap again.',
          'event.allFacilities': 'All Facilities',
          'facility.taiwan': 'Taiwan',
          'facility.hsinchu': 'Hsinchu',
          'facility.zhunan': 'Miaoli / Zhunan',
          'facility.taichung': 'Taichung',
          'facility.tainan': 'Tainan',
          'facility.kaohsiung': 'Kaohsiung',
          'facility.usa': 'United States',
          'facility.arizona': 'Arizona',
          'facility.japan': 'Japan',
          'facility.kumamoto': 'Kumamoto',
          'facility.germany': 'Germany',
          'facility.dresden': 'Saxony / Dresden',
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
