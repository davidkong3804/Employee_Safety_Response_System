import '@testing-library/jest-dom'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

// Implement a robust in-memory Storage mock to prevent experimental native Node 22+/24/25 Web Storage conflicts
class InMemoryStorage implements Storage {
  private store: Record<string, string> = {}

  get length(): number {
    return Object.keys(this.store).length
  }

  clear(): void {
    this.store = {}
  }

  getItem(key: string): string | null {
    return this.store[key] !== undefined ? this.store[key] : null
  }

  key(index: number): string | null {
    const keys = Object.keys(this.store)
    return keys[index] !== undefined ? keys[index] : null
  }

  removeItem(key: string): void {
    delete this.store[key]
  }

  setItem(key: string, value: string): void {
    this.store[key] = String(value)
  }
}

const mockLocalStorage = new InMemoryStorage()
const mockSessionStorage = new InMemoryStorage()

delete (globalThis as any).localStorage
delete (globalThis as any).sessionStorage

Object.defineProperty(globalThis, 'localStorage', {
  value: mockLocalStorage,
  writable: true,
  configurable: true
})
Object.defineProperty(globalThis, 'sessionStorage', {
  value: mockSessionStorage,
  writable: true,
  configurable: true
})

if (typeof window !== 'undefined') {
  Object.defineProperty(window, 'localStorage', {
    value: mockLocalStorage,
    writable: true,
    configurable: true
  })
  Object.defineProperty(window, 'sessionStorage', {
    value: mockSessionStorage,
    writable: true,
    configurable: true
  })
}




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
          'app.subtitle': 'Employee Safety & Response System',
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
          'facility.fabsCount': '({{count}} fabs)',
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
