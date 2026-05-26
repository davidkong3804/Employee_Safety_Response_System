import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  submitReport,
  getMyReport,
  getEventStats,
  getStatsByDepartment,
  getTeamStatus,
  getAllStatus,
  triggerReminders,
} from '../../api/reports'
import client from '../../api/client'

vi.mock('../../api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}))

const mockedGet = vi.mocked(client.get)
const mockedPost = vi.mocked(client.post)

describe('reports API', () => {
  beforeEach(() => vi.clearAllMocks())

  describe('submitReport()', () => {
    it('POSTs status + message to /api/events/{id}/report', async () => {
      mockedPost.mockResolvedValue({ data: { id: 'r-1', status: 'safe' } })
      await submitReport('ev-1', { status: 'safe', message: 'all clear' })
      expect(mockedPost).toHaveBeenCalledWith('/api/events/ev-1/report', {
        status: 'safe',
        message: 'all clear',
      })
    })
  })

  describe('getMyReport()', () => {
    it('GETs /api/events/{id}/my-report', async () => {
      mockedGet.mockResolvedValue({ data: null })
      await getMyReport('ev-1')
      expect(mockedGet).toHaveBeenCalledWith('/api/events/ev-1/my-report', undefined)
    })

    it('passes through null when not yet reported', async () => {
      mockedGet.mockResolvedValue({ data: null })
      expect(await getMyReport('ev-1')).toBeNull()
    })
  })

  describe('getEventStats()', () => {
    it('GETs /api/events/{id}/stats', async () => {
      const stats = { total: 10, safe: 7, need_help: 1, unreported: 2, report_rate: 80 }
      mockedGet.mockResolvedValue({ data: stats })
      const result = await getEventStats('ev-1')
      expect(mockedGet).toHaveBeenCalledWith('/api/events/ev-1/stats')
      expect(result).toEqual(stats)
    })
  })

  describe('getStatsByDepartment()', () => {
    it('GETs /api/events/{id}/stats/by-department', async () => {
      mockedGet.mockResolvedValue({ data: [] })
      await getStatsByDepartment('ev-1')
      expect(mockedGet).toHaveBeenCalledWith('/api/events/ev-1/stats/by-department')
    })
  })

  describe('getTeamStatus()', () => {
    it('GETs /api/events/{id}/team-status with empty params object', async () => {
      mockedGet.mockResolvedValue({ data: { items: [], total: 0, limit: 100, offset: 0 } })
      await getTeamStatus('ev-1')
      expect(mockedGet).toHaveBeenCalledWith('/api/events/ev-1/team-status', { params: {} })
    })

    it('forwards limit/offset/department/status/search query params', async () => {
      mockedGet.mockResolvedValue({ data: { items: [], total: 0, limit: 100, offset: 0 } })
      await getTeamStatus('ev-1', { limit: 50, offset: 100, department: 'Eng', status: 'need_help', search: 'alice' })
      expect(mockedGet).toHaveBeenCalledWith('/api/events/ev-1/team-status', {
        params: { limit: 50, offset: 100, department: 'Eng', status: 'need_help', search: 'alice' },
      })
    })
  })

  describe('getAllStatus()', () => {
    it('GETs /api/events/{id}/all-status with empty params when filters are absent', async () => {
      mockedGet.mockResolvedValue({ data: { items: [], total: 0, limit: 100, offset: 0 } })
      await getAllStatus('ev-1')
      expect(mockedGet).toHaveBeenCalledWith('/api/events/ev-1/all-status', { params: {} })
    })

    it('forwards facility filter', async () => {
      mockedGet.mockResolvedValue({ data: { items: [], total: 0, limit: 100, offset: 0 } })
      await getAllStatus('ev-1', { facility: 'Fab14' })
      expect(mockedGet).toHaveBeenCalledWith('/api/events/ev-1/all-status', { params: { facility: 'Fab14' } })
    })

    it('forwards facility + department filters', async () => {
      mockedGet.mockResolvedValue({ data: { items: [], total: 0, limit: 100, offset: 0 } })
      await getAllStatus('ev-1', { facility: 'Fab14', department: 'Engineering' })
      expect(mockedGet).toHaveBeenCalledWith('/api/events/ev-1/all-status', {
        params: { facility: 'Fab14', department: 'Engineering' },
      })
    })
  })

  describe('triggerReminders()', () => {
    it('POSTs /api/events/{id}/remind and returns reminded_count', async () => {
      mockedPost.mockResolvedValue({ data: { reminded_count: 5, message: 'ok' } })
      const result = await triggerReminders('ev-1')
      expect(mockedPost).toHaveBeenCalledWith('/api/events/ev-1/remind')
      expect(result.reminded_count).toBe(5)
    })
  })
})
