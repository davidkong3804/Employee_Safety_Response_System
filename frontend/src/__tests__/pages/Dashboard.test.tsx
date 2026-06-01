import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import Dashboard from '../../pages/manager/Dashboard'
import * as eventsApi from '../../api/events'
import * as reportsApi from '../../api/reports'
import type { Event, EventStats, DepartmentStats, PaginatedReports } from '../../types'

vi.mock('../../api/events')
vi.mock('../../api/reports')
vi.mock('react-hot-toast', () => ({ default: { success: vi.fn(), error: vi.fn() } }))
// Manager session — Dashboard reads `user.role`.
vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ user: { id: 'm1', role: 'manager', name: 'Mgr', employee_id: 'M001' } }),
}))
// Stub charts + virtualized list. BUG-0 is about data loading, not chart layout,
// and recharts' ResponsiveContainer needs a ResizeObserver that jsdom lacks.
vi.mock('recharts', () => {
  const Stub = (p: { children?: unknown }) => <div>{p.children as never}</div>
  return {
    ResponsiveContainer: Stub, PieChart: Stub, Pie: Stub, Cell: Stub,
    BarChart: Stub, Bar: Stub, XAxis: Stub, YAxis: Stub, Tooltip: Stub, Legend: Stub,
  }
})
vi.mock('react-window', () => ({ List: () => <div data-testid="vlist" /> }))

const closed = (id: string, title: string): Event => ({
  id,
  title,
  description: null,
  event_type: 'earthquake',
  severity: 'high',
  status: 'closed',
  facility: null,
  created_by: 'a',
  created_at: '2026-05-25T10:00:00Z',
  closed_at: '2026-05-26T00:00:00Z',
})

const STATS: EventStats = { total: 6002, safe: 2971, need_help: 3014, unreported: 17, report_rate: 99.7 }
const DEPT: DepartmentStats[] = [{ department: 'Mfg', total: 6002, safe: 2971, need_help: 3014, unreported: 17 }]
const PAGE: PaginatedReports = { items: [], total: 6002, limit: 100, offset: 0 }

const listEvents = vi.mocked(eventsApi.listEvents)
const getEventStats = vi.mocked(reportsApi.getEventStats)
const getStatsByDepartment = vi.mocked(reportsApi.getStatsByDepartment)
const getTeamStatus = vi.mocked(reportsApi.getTeamStatus)

const renderDash = () => render(<MemoryRouter><Dashboard /></MemoryRouter>)

describe('Dashboard — BUG-0: renders even when no event is active', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getEventStats.mockResolvedValue(STATS)
    getStatsByDepartment.mockResolvedValue(DEPT)
    getTeamStatus.mockResolvedValue(PAGE)
  })

  it('falls back to the first event and loads its data when none is active', async () => {
    // Regression: previously `selectedEventId` stayed '' with no active event →
    // reloadAll early-returned → blank dashboard ("死白一片").
    listEvents.mockResolvedValue([closed('ev-1', 'Quake'), closed('ev-2', 'Fire')])
    renderDash()
    await waitFor(() => expect(getEventStats).toHaveBeenCalledWith('ev-1'))
    expect(getStatsByDepartment).toHaveBeenCalledWith('ev-1')
    // Stats reach component state → KPI numbers render (not blank).
    expect(await screen.findByText('6002')).toBeInTheDocument()
    expect(screen.getByText('2971')).toBeInTheDocument()
  })

  it('prefers an active event when one is present', async () => {
    listEvents.mockResolvedValue([
      closed('ev-old', 'Old'),
      { ...closed('ev-active', 'Now'), status: 'active', closed_at: null },
    ])
    renderDash()
    await waitFor(() => expect(getEventStats).toHaveBeenCalledWith('ev-active'))
  })

  it('does not fetch stats when there are zero events', async () => {
    listEvents.mockResolvedValue([])
    renderDash()
    await waitFor(() => expect(listEvents).toHaveBeenCalled())
    expect(getEventStats).not.toHaveBeenCalled()
  })
})
