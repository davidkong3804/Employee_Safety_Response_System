import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import Home from '../../pages/employee/Home'
import * as AuthContextModule from '../../contexts/AuthContext'
import * as eventsApi from '../../api/events'
import * as reportsApi from '../../api/reports'
import * as remindersApi from '../../api/reminders'
import type { Event, User } from '../../types'

vi.mock('../../api/events', () => ({ listEvents: vi.fn() }))
vi.mock('../../api/reports', () => ({ getMyReport: vi.fn() }))
vi.mock('../../api/reminders', () => ({ getMyReminders: vi.fn() }))

// Stub i18n so we don't depend on translation keys.
vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}))

// StatusBadge/ReminderModal pull in i18n internally; the i18next mock
// above already takes care of them.

const mockedList = vi.mocked(eventsApi.listEvents)
const mockedGetMyReport = vi.mocked(reportsApi.getMyReport)
const mockedGetReminders = vi.mocked(remindersApi.getMyReminders)

function makeUser(): User {
  return {
    id: 'u-1',
    employee_id: 'E001',
    name: 'Alice',
    email: 'a@example.com',
    role: 'employee',
    department: 'Engineering',
    facility: 'Fab14',
    phone: null,
  }
}

function makeEvent(overrides: Partial<Event> = {}): Event {
  return {
    id: 'ev-1',
    title: 'Earthquake',
    description: 'M6.0 shake',
    event_type: 'earthquake',
    severity: 'high',
    status: 'active',
    facility: ['Fab14'],
    created_by: 'admin-1',
    created_at: '2026-05-26T10:00:00Z',
    closed_at: null,
    ...overrides,
  }
}

function mockAuth(user: User | null = makeUser()) {
  vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
    user,
    loading: false,
    login: vi.fn(),
    logout: vi.fn(),
  })
}

function renderHome() {
  return render(
    <MemoryRouter>
      <Home />
    </MemoryRouter>,
  )
}

describe('Home (employee)', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    sessionStorage.clear()
  })

  it('shows the spinner before listEvents resolves', async () => {
    mockAuth()
    let resolve: (es: Event[]) => void = () => {}
    mockedList.mockImplementation(() => new Promise((r) => { resolve = r }))
    const { container } = renderHome()
    expect(container.querySelector('.animate-spin')).not.toBeNull()
    resolve([])
    await waitFor(() => expect(container.querySelector('.animate-spin')).toBeNull())
  })

  it('renders the active event card with the event title and report link', async () => {
    mockAuth()
    mockedList.mockResolvedValue([makeEvent({ title: 'Quake' })])
    mockedGetMyReport.mockResolvedValue(null)

    renderHome()
    await waitFor(() => {
      expect(screen.getByText('Quake')).toBeInTheDocument()
    })
    // The report link points at /events/{id}/report
    const link = screen.getByRole('link', { name: /report\.title|report\.update/i })
    expect(link).toHaveAttribute('href', '/events/ev-1/report')
  })

  it('separates active and closed events into two sections', async () => {
    mockAuth()
    mockedList.mockResolvedValue([
      makeEvent({ id: 'a', title: 'ActiveOne', status: 'active' }),
      makeEvent({ id: 'b', title: 'ClosedOne', status: 'closed' }),
    ])
    mockedGetMyReport.mockResolvedValue(null)

    renderHome()
    await waitFor(() => {
      expect(screen.getByText('ActiveOne')).toBeInTheDocument()
      expect(screen.getByText('ClosedOne')).toBeInTheDocument()
    })
  })

  it('shows the "no events" placeholder when the list is empty', async () => {
    mockAuth()
    mockedList.mockResolvedValue([])
    renderHome()
    await waitFor(() => {
      expect(screen.getByText('event.noEvents')).toBeInTheDocument()
    })
  })

  it('shows the load-error UI with a retry button when listEvents rejects', async () => {
    mockAuth()
    mockedList.mockRejectedValue(new Error('500'))
    renderHome()
    await waitFor(() => {
      expect(screen.getByText('event.loadError')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /common\.retry/i })).toBeInTheDocument()
    })
  })

  it('retries listEvents when the retry button is clicked', async () => {
    mockAuth()
    mockedList.mockRejectedValueOnce(new Error('boom'))
    mockedList.mockResolvedValueOnce([makeEvent({ title: 'RecoveredEvent' })])
    mockedGetMyReport.mockResolvedValue(null)

    renderHome()
    await waitFor(() =>
      expect(screen.getByText('event.loadError')).toBeInTheDocument(),
    )

    fireEvent.click(screen.getByRole('button', { name: /common\.retry/i }))
    await waitFor(() => {
      expect(screen.getByText('RecoveredEvent')).toBeInTheDocument()
    })
  })

  it('triggers the reminder modal flow when the session flag is set', async () => {
    mockAuth()
    sessionStorage.setItem('reminder-modal-pending', '1')
    mockedList.mockResolvedValue([])
    mockedGetReminders.mockResolvedValue([
      {
        event_id: 'e1',
        event_title: 'Quake',
        severity: 'high',
        reminder_count: 1,
        last_reminded: null,
      },
    ])

    renderHome()
    await waitFor(() => expect(mockedGetReminders).toHaveBeenCalled())
    // sessionStorage flag should be cleared after one read
    expect(sessionStorage.getItem('reminder-modal-pending')).toBeNull()
  })

  it('does NOT call getMyReminders when no session flag is present', async () => {
    mockAuth()
    mockedList.mockResolvedValue([])
    renderHome()
    await waitFor(() => expect(mockedList).toHaveBeenCalled())
    expect(mockedGetReminders).not.toHaveBeenCalled()
  })
})
