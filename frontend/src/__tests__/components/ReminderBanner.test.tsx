import { render, waitFor, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import ReminderBanner from '../../components/ReminderBanner'
import * as AuthContextModule from '../../contexts/AuthContext'
import * as remindersApi from '../../api/reminders'
import type { User } from '../../types'

vi.mock('../../api/reminders', () => ({
  getMyReminders: vi.fn(),
}))

const mockedGet = vi.mocked(remindersApi.getMyReminders)

function makeUser(role: 'employee' | 'manager' | 'admin' = 'employee'): User {
  return {
    id: 'u-1',
    employee_id: 'E001',
    name: 'Test',
    email: 't@example.com',
    role,
    department: 'Engineering',
    facility: 'Fab14',
    phone: null,
  }
}

function mockAuth(user: User | null) {
  vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
    user,
    loading: false,
    login: vi.fn(),
    logout: vi.fn(),
  })
}

describe('ReminderBanner', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders nothing when not logged in', () => {
    mockAuth(null)
    mockedGet.mockResolvedValue([])
    const { container } = render(<ReminderBanner />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing for non-employee roles', () => {
    mockAuth(makeUser('manager'))
    mockedGet.mockResolvedValue([
      {
        event_id: 'e1',
        event_title: 'X',
        severity: 'high',
        reminder_count: 1,
        last_reminded: null,
      },
    ])
    const { container } = render(<ReminderBanner />)
    expect(container).toBeEmptyDOMElement()
    expect(mockedGet).not.toHaveBeenCalled()
  })

  it('renders nothing for employee with no pending reminders', async () => {
    mockAuth(makeUser('employee'))
    mockedGet.mockResolvedValue([])
    const { container } = render(<ReminderBanner />)
    await waitFor(() => expect(mockedGet).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })

  it('renders the marquee with the single-event message', async () => {
    mockAuth(makeUser('employee'))
    mockedGet.mockResolvedValue([
      {
        event_id: 'e1',
        event_title: 'Earthquake',
        severity: 'high',
        reminder_count: 1,
        last_reminded: null,
      },
    ])
    render(<ReminderBanner />)
    // The marquee triplicates the message, so the event title appears 3×.
    await waitFor(() => {
      const banner = document.querySelector('.safety-marquee-track')
      expect(banner).not.toBeNull()
      expect(banner!.textContent).toContain('Earthquake')
    })
  })

  it('polls every 20 seconds while mounted', async () => {
    vi.useFakeTimers()
    mockAuth(makeUser('employee'))
    mockedGet.mockResolvedValue([])

    render(<ReminderBanner />)
    // Initial fetchOnce schedules a microtask; flush it.
    await vi.waitFor(() => expect(mockedGet).toHaveBeenCalledTimes(1))

    await act(async () => {
      vi.advanceTimersByTime(20_000)
    })
    await vi.waitFor(() => expect(mockedGet).toHaveBeenCalledTimes(2))

    await act(async () => {
      vi.advanceTimersByTime(20_000)
    })
    await vi.waitFor(() => expect(mockedGet).toHaveBeenCalledTimes(3))
  })

  it('swallows API errors silently (banner just stays hidden)', async () => {
    mockAuth(makeUser('employee'))
    mockedGet.mockRejectedValue(new Error('Network down'))
    const { container } = render(<ReminderBanner />)
    await waitFor(() => expect(mockedGet).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })
})
