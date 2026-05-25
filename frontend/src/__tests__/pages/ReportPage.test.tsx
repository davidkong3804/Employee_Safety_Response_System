import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import toast from 'react-hot-toast'
import ReportPage from '../../pages/employee/ReportPage'
import * as eventsApi from '../../api/events'
import * as reportsApi from '../../api/reports'
import type { Event, SafetyReport } from '../../types'

vi.mock('../../api/events')
vi.mock('../../api/reports')
vi.mock('react-hot-toast', () => ({
  default: { success: vi.fn(), error: vi.fn() },
}))

const mockedGetEvent = vi.mocked(eventsApi.getEvent)
const mockedGetMyReport = vi.mocked(reportsApi.getMyReport)
const mockedSubmitReport = vi.mocked(reportsApi.submitReport)

const mockEvent: Event = {
  id: 'ev-1',
  title: 'Earthquake M6.2',
  description: 'Tainan',
  event_type: 'earthquake',
  severity: 'high',
  status: 'active',
  facility: null,
  created_by: 'admin-uuid',
  created_at: '2026-05-25T10:00:00Z',
  closed_at: null,
}

const reportedSafe: SafetyReport = {
  id: 'r-1',
  event_id: 'ev-1',
  user_id: 'u-1',
  user_name: 'Test',
  employee_id: 'E001',
  department: 'Engineering',
  facility: 'Fab14',
  phone: null,
  status: 'safe',
  message: 'all clear',
  reported_at: '2026-05-25T10:05:00Z',
}

const unreportedPlaceholder: SafetyReport = {
  ...reportedSafe,
  id: 'r-empty',
  status: null,
  message: null,
  reported_at: null,
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/events/ev-1/report']}>
      <Routes>
        <Route path="/events/:eventId/report" element={<ReportPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ReportPage', () => {
  beforeEach(() => vi.clearAllMocks())

  describe('not yet reported', () => {
    beforeEach(() => {
      mockedGetEvent.mockResolvedValue(mockEvent)
      mockedGetMyReport.mockResolvedValue(unreportedPlaceholder)
    })

    it('renders "I\'m Safe" and "Need Help" buttons after loading', async () => {
      renderPage()
      await waitFor(() => expect(screen.getByText("I'm Safe")).toBeInTheDocument())
      expect(screen.getByText('Need Help')).toBeInTheDocument()
    })

    it('shows the event title', async () => {
      renderPage()
      await waitFor(() => expect(screen.getByText('Earthquake M6.2')).toBeInTheDocument())
    })

    it('clicking "I\'m Safe" submits status=safe and toasts success', async () => {
      mockedSubmitReport.mockResolvedValue(reportedSafe)
      renderPage()
      await waitFor(() => screen.getByText("I'm Safe"))
      fireEvent.click(screen.getByText("I'm Safe"))
      await waitFor(() =>
        expect(mockedSubmitReport).toHaveBeenCalledWith('ev-1', {
          status: 'safe',
          message: undefined,
        }),
      )
      expect(toast.success).toHaveBeenCalledWith('Report submitted!')
    })

    it('clicking "Need Help" submits status=need_help', async () => {
      mockedSubmitReport.mockResolvedValue({ ...reportedSafe, status: 'need_help' })
      renderPage()
      await waitFor(() => screen.getByText('Need Help'))
      fireEvent.click(screen.getByText('Need Help'))
      await waitFor(() =>
        expect(mockedSubmitReport).toHaveBeenCalledWith('ev-1', {
          status: 'need_help',
          message: undefined,
        }),
      )
    })

    it('forwards the typed message with the submission', async () => {
      mockedSubmitReport.mockResolvedValue(reportedSafe)
      renderPage()
      await waitFor(() => screen.getByText("I'm Safe"))
      const textarea = screen.getByPlaceholderText('Additional message (optional)')
      fireEvent.change(textarea, { target: { value: 'on the 3rd floor' } })
      fireEvent.click(screen.getByText("I'm Safe"))
      await waitFor(() =>
        expect(mockedSubmitReport).toHaveBeenCalledWith('ev-1', {
          status: 'safe',
          message: 'on the 3rd floor',
        }),
      )
    })

    it('toasts an error message when submission fails', async () => {
      mockedSubmitReport.mockRejectedValue(new Error('500'))
      renderPage()
      await waitFor(() => screen.getByText("I'm Safe"))
      fireEvent.click(screen.getByText("I'm Safe"))
      await waitFor(() =>
        expect(toast.error).toHaveBeenCalledWith('Report failed, please retry'),
      )
    })
  })

  describe('already reported', () => {
    it('shows the already-reported confirmation instead of buttons', async () => {
      mockedGetEvent.mockResolvedValue(mockEvent)
      mockedGetMyReport.mockResolvedValue(reportedSafe)
      renderPage()
      await waitFor(() =>
        expect(screen.getByText('You have already reported')).toBeInTheDocument(),
      )
      expect(screen.queryByText("I'm Safe")).not.toBeInTheDocument()
      expect(screen.queryByText('Need Help')).not.toBeInTheDocument()
    })

    it('renders the prior message text when present', async () => {
      mockedGetEvent.mockResolvedValue(mockEvent)
      mockedGetMyReport.mockResolvedValue(reportedSafe)
      renderPage()
      await waitFor(() => expect(screen.getByText('all clear')).toBeInTheDocument())
    })
  })
})
