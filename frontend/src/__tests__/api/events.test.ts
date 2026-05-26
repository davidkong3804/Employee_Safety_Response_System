import { describe, it, expect, vi, beforeEach } from 'vitest'
import { listEvents, getEvent, createEvent, updateEvent, deleteEvent } from '../../api/events'
import client from '../../api/client'
import type { Event } from '../../types'

vi.mock('../../api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

const mockedGet = vi.mocked(client.get)
const mockedPost = vi.mocked(client.post)
const mockedPatch = vi.mocked(client.patch)
const mockedDelete = vi.mocked(client.delete)

const mockEvent: Event = {
  id: 'ev-1',
  title: 'Earthquake M6.2',
  description: 'Tainan area',
  event_type: 'earthquake',
  severity: 'high',
  status: 'active',
  facility: ['Fab14'],
  created_by: 'admin-uuid',
  created_at: '2026-05-25T10:00:00Z',
  closed_at: null,
}

describe('events API', () => {
  beforeEach(() => vi.clearAllMocks())

  describe('listEvents()', () => {
    it('calls GET /api/events', async () => {
      mockedGet.mockResolvedValue({ data: [mockEvent] })
      await listEvents()
      expect(mockedGet).toHaveBeenCalledWith('/api/events', undefined)
    })

    it('returns the event array unchanged', async () => {
      mockedGet.mockResolvedValue({ data: [mockEvent] })
      const result = await listEvents()
      expect(result).toEqual([mockEvent])
    })
  })

  describe('getEvent()', () => {
    it('calls GET /api/events/{id}', async () => {
      mockedGet.mockResolvedValue({ data: mockEvent })
      await getEvent('ev-1')
      expect(mockedGet).toHaveBeenCalledWith('/api/events/ev-1')
    })
  })

  describe('createEvent()', () => {
    it('POSTs the payload to /api/events with the facility array', async () => {
      mockedPost.mockResolvedValue({ data: mockEvent })
      const payload = {
        title: 'Fire alarm',
        event_type: 'fire',
        severity: 'critical',
        facility: ['Fab14', 'Fab18'],
      }
      await createEvent(payload)
      expect(mockedPost).toHaveBeenCalledWith('/api/events', payload)
    })

    it('returns the created event', async () => {
      mockedPost.mockResolvedValue({ data: mockEvent })
      const result = await createEvent({
        title: 'x',
        event_type: 'fire',
        severity: 'high',
      })
      expect(result).toEqual(mockEvent)
    })
  })

  describe('updateEvent()', () => {
    it('PATCHes /api/events/{id} with the partial payload', async () => {
      mockedPatch.mockResolvedValue({ data: { ...mockEvent, status: 'closed' } })
      await updateEvent('ev-1', { status: 'closed' })
      expect(mockedPatch).toHaveBeenCalledWith('/api/events/ev-1', { status: 'closed' })
    })
  })

  describe('deleteEvent()', () => {
    it('DELETEs /api/events/{id}', async () => {
      mockedDelete.mockResolvedValue({})
      await deleteEvent('ev-1')
      expect(mockedDelete).toHaveBeenCalledWith('/api/events/ev-1')
    })
  })
})
