import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ReminderModal from '../../components/ReminderModal'
import type { MyReminder } from '../../api/reminders'

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

function makeReminder(overrides: Partial<MyReminder> = {}): MyReminder {
  return {
    event_id: 'ev-1',
    event_title: 'Earthquake',
    severity: 'high',
    reminder_count: 1,
    last_reminded: '2026-05-26T10:00:00Z',
    ...overrides,
  }
}

describe('ReminderModal', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders nothing when the reminders list is empty', () => {
    const { container } = render(<ReminderModal reminders={[]} onClose={vi.fn()} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders a single-reminder body and no bullet list', () => {
    render(<ReminderModal reminders={[makeReminder()]} onClose={vi.fn()} />)
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.queryByRole('list')).toBeNull()
  })

  it('renders a bullet list when multiple reminders are present', () => {
    const reminders = [
      makeReminder({ event_id: 'a', event_title: 'Earthquake' }),
      makeReminder({ event_id: 'b', event_title: 'Fire' }),
      makeReminder({ event_id: 'c', event_title: 'Flood' }),
    ]
    render(<ReminderModal reminders={reminders} onClose={vi.fn()} />)
    const items = screen.getAllByRole('listitem')
    expect(items).toHaveLength(3)
    expect(items[0].textContent).toContain('Earthquake')
    expect(items[2].textContent).toContain('Flood')
  })

  it('navigates to the first reminder when Report Now is clicked, then closes', () => {
    const onClose = vi.fn()
    render(
      <ReminderModal
        reminders={[makeReminder({ event_id: 'ev-42' })]}
        onClose={onClose}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /report now|go report/i }))
    expect(onClose).toHaveBeenCalledOnce()
    expect(mockNavigate).toHaveBeenCalledWith('/events/ev-42/report')
  })

  it('closes when clicking the X button without navigating', () => {
    const onClose = vi.fn()
    render(<ReminderModal reminders={[makeReminder()]} onClose={onClose} />)
    fireEvent.click(screen.getByLabelText('close'))
    expect(onClose).toHaveBeenCalledOnce()
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('closes when clicking the backdrop without navigating', () => {
    const onClose = vi.fn()
    render(<ReminderModal reminders={[makeReminder()]} onClose={onClose} />)
    fireEvent.click(screen.getByRole('dialog'))
    expect(onClose).toHaveBeenCalledOnce()
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('does NOT close when clicking inside the modal content', () => {
    const onClose = vi.fn()
    render(<ReminderModal reminders={[makeReminder()]} onClose={onClose} />)
    // The inner card has stopPropagation; clicking on the title shouldn't bubble.
    const title = screen.getByRole('heading', { level: 2 })
    fireEvent.click(title)
    expect(onClose).not.toHaveBeenCalled()
  })
})
