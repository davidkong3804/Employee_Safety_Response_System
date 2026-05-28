import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import EventManagement from '../../pages/admin/EventManagement'
import * as eventsApi from '../../api/events'
import type { Event } from '../../types'

// Mock all API calls so the component runs against in-memory fixtures.
vi.mock('../../api/events', () => ({
  listEvents: vi.fn(),
  createEvent: vi.fn(),
  updateEvent: vi.fn(),
  deleteEvent: vi.fn(),
}))

vi.mock('react-hot-toast', () => ({
  default: { success: vi.fn(), error: vi.fn() },
}))

// react-i18next: stub t() to return the key so we can assert against keys
// instead of polluting vitest.setup.ts with hundreds of admin strings.
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      if (!params) return key
      return key + ':' + Object.values(params).join(',')
    },
  }),
}))

// FacilitySelector pulls in i18n + headlessui; stub it out so we can focus
// on EventManagement's own CRUD behaviour.
vi.mock('../../components/FacilitySelector', () => ({
  default: ({ value }: { value: string[] }) => (
    <div data-testid="facility-selector">selected:{value.join(',')}</div>
  ),
}))

const mockedList = vi.mocked(eventsApi.listEvents)
const mockedCreate = vi.mocked(eventsApi.createEvent)
const mockedUpdate = vi.mocked(eventsApi.updateEvent)
const mockedDelete = vi.mocked(eventsApi.deleteEvent)

function makeEvent(overrides: Partial<Event> = {}): Event {
  return {
    id: 'ev-1',
    title: 'Earthquake',
    description: 'M6.0',
    event_type: 'earthquake',
    severity: 'high',
    status: 'active',
    facility: ['Fab14'],
    created_by: 'u-1',
    created_at: '2026-05-26T10:00:00Z',
    closed_at: null,
    ...overrides,
  }
}

describe('EventManagement', () => {
  beforeEach(() => {
    // resetAllMocks() clears implementations too, not just call history —
    // important because one test below pins listEvents to a never-resolving
    // promise to test the spinner state; without a reset that implementation
    // would leak into later tests and time them out.
    vi.resetAllMocks()
    vi.spyOn(window, 'confirm').mockImplementation(() => true)
  })

  it('shows the loading spinner until listEvents resolves', async () => {
    let resolveList: (events: Event[]) => void = () => {}
    mockedList.mockImplementation(
      () => new Promise<Event[]>((resolve) => { resolveList = resolve }),
    )
    const { container } = render(<EventManagement />)
    // spinner is rendered as a div with animate-spin
    expect(container.querySelector('.animate-spin')).not.toBeNull()
    resolveList([])
    await waitFor(() => expect(container.querySelector('.animate-spin')).toBeNull())
  })

  it('renders rows for each event returned by listEvents', async () => {
    mockedList.mockResolvedValue([
      makeEvent({ id: 'a', title: 'Quake-A', status: 'active' }),
      makeEvent({ id: 'b', title: 'Fire-B', status: 'closed', facility: [] }),
    ])
    const { container } = render(<EventManagement />)
    await waitFor(() => {
      const table = container.querySelector('table')!
      expect(within(table).getByText('Quake-A')).toBeInTheDocument()
      expect(within(table).getByText('Fire-B')).toBeInTheDocument()
    })
  })

  it('shows the "no events" placeholder when the list is empty', async () => {
    mockedList.mockResolvedValue([])
    render(<EventManagement />)
    await waitFor(() => {
      expect(screen.getByText('event.noEvents')).toBeInTheDocument()
    })
  })

  it('opens the create modal and posts to createEvent on submit', async () => {
    mockedList.mockResolvedValueOnce([])
    mockedCreate.mockResolvedValue(makeEvent())
    mockedList.mockResolvedValueOnce([makeEvent()]) // post-create refetch

    render(<EventManagement />)
    await waitFor(() => expect(mockedList).toHaveBeenCalledTimes(1))

    // The "Create Event" button uses the key `event.create`.
    const createButtons = screen.getAllByText('event.create')
    fireEvent.click(createButtons[0])

    // Title input inside the modal.
    const titleInput = document.querySelector('input[required]') as HTMLInputElement
    fireEvent.change(titleInput, { target: { value: 'New Quake' } })

    // The submit button inside the form lives in the modal; grab the form
    // submit button and click it.
    const form = document.querySelector('form')!
    fireEvent.submit(form)

    await waitFor(() => expect(mockedCreate).toHaveBeenCalledTimes(1))
    expect(mockedCreate).toHaveBeenCalledWith({
      title: 'New Quake',
      description: '',
      event_type: 'earthquake',
      severity: 'high',
      facility: undefined,
    })
    // After creation, list is refetched.
    await waitFor(() => expect(mockedList).toHaveBeenCalledTimes(2))
  })

  it('closes an active event via updateEvent after confirmation', async () => {
    mockedList.mockResolvedValueOnce([
      makeEvent({ id: 'ev-7', title: 'CloseMe', status: 'active' }),
    ])
    mockedUpdate.mockResolvedValue(makeEvent({ id: 'ev-7', status: 'closed' }))
    mockedList.mockResolvedValueOnce([makeEvent({ id: 'ev-7', status: 'closed' })])

    const { container } = render(<EventManagement />)
    await waitFor(() => {
      expect(within(container.querySelector('table')!).getByText('CloseMe')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('event.close'))
    expect(window.confirm).toHaveBeenCalled()
    await waitFor(() =>
      expect(mockedUpdate).toHaveBeenCalledWith('ev-7', { status: 'closed' }),
    )
  })

  it('does NOT call updateEvent if confirmation is denied', async () => {
    vi.spyOn(window, 'confirm').mockReturnValueOnce(false)
    mockedList.mockResolvedValue([makeEvent({ title: 'DenyMe', status: 'active' })])

    const { container } = render(<EventManagement />)
    await waitFor(() => {
      expect(within(container.querySelector('table')!).getByText('DenyMe')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('event.close'))
    expect(mockedUpdate).not.toHaveBeenCalled()
  })

  it('deletes an event via deleteEvent after confirmation', async () => {
    mockedList.mockResolvedValueOnce([makeEvent({ id: 'ev-9', title: 'DelMe' })])
    mockedDelete.mockResolvedValue(undefined as unknown as void)
    mockedList.mockResolvedValueOnce([])

    const { container } = render(<EventManagement />)
    await waitFor(() => {
      expect(within(container.querySelector('table')!).getByText('DelMe')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('event.delete'))
    expect(window.confirm).toHaveBeenCalled()
    await waitFor(() => expect(mockedDelete).toHaveBeenCalledWith('ev-9'))
  })

  it('keeps the modal open and does NOT refetch on createEvent error', async () => {
    mockedList.mockResolvedValueOnce([])
    mockedCreate.mockRejectedValueOnce(new Error('500'))

    render(<EventManagement />)
    await waitFor(() => expect(mockedList).toHaveBeenCalledTimes(1))

    fireEvent.click(screen.getAllByText('event.create')[0])
    const titleInput = document.querySelector('input[required]') as HTMLInputElement
    fireEvent.change(titleInput, { target: { value: 'X' } })
    fireEvent.submit(document.querySelector('form')!)

    await waitFor(() => expect(mockedCreate).toHaveBeenCalled())
    // No refetch on failure.
    expect(mockedList).toHaveBeenCalledTimes(1)
    // Modal still open — facility-selector stub still in DOM.
    expect(screen.getByTestId('facility-selector')).toBeInTheDocument()
  })

  it('shows "All Facilities" label when facility array is empty', async () => {
    mockedList.mockResolvedValue([makeEvent({ title: 'GlobalEvent', facility: [] })])
    const { container } = render(<EventManagement />)
    await waitFor(() => {
      const table = container.querySelector('table')!
      expect(within(table).getByText('GlobalEvent')).toBeInTheDocument()
      expect(within(table).getByText('event.allFacilities')).toBeInTheDocument()
    })
  })
})
