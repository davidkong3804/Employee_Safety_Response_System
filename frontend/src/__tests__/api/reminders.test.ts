import { describe, it, expect, vi, beforeEach } from 'vitest'
import { getMyReminders } from '../../api/reminders'
import client from '../../api/client'

vi.mock('../../api/client', () => ({
  default: {
    get: vi.fn(),
  },
}))

const mockedGet = vi.mocked(client.get)

describe('reminders API', () => {
  beforeEach(() => vi.clearAllMocks())

  it('GETs /api/me/reminders and returns the array', async () => {
    const fixture = [
      {
        event_id: 'ev-1',
        event_title: 'Earthquake',
        severity: 'high',
        reminder_count: 2,
        last_reminded: '2026-05-26T10:00:00Z',
      },
    ]
    mockedGet.mockResolvedValue({ data: fixture })

    const result = await getMyReminders()
    expect(mockedGet).toHaveBeenCalledWith('/api/me/reminders')
    expect(result).toEqual(fixture)
  })

  it('returns an empty array when the server has no pending reminders', async () => {
    mockedGet.mockResolvedValue({ data: [] })
    const result = await getMyReminders()
    expect(result).toEqual([])
  })

  it('propagates network errors', async () => {
    mockedGet.mockRejectedValue(new Error('Network down'))
    await expect(getMyReminders()).rejects.toThrow('Network down')
  })
})
