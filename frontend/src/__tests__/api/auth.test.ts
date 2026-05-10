import { describe, it, expect, vi, beforeEach } from 'vitest'
import { login, getMe } from '../../api/auth'
import client from '../../api/client'
import type { User } from '../../types'

vi.mock('../../api/client', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}))

const mockedPost = vi.mocked(client.post)
const mockedGet = vi.mocked(client.get)

const mockUser: User = {
  id: 'uuid-1',
  employee_id: 'E001',
  name: 'Test',
  email: 'test@example.com',
  role: 'employee',
  department: null,
  facility: null,
  phone: null,
}

describe('auth API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('login()', () => {
    it('posts to /api/auth/login with employee_id and password', async () => {
      mockedPost.mockResolvedValue({ data: { access_token: 'tok', token_type: 'bearer' } })
      await login('E001', 'pw')
      expect(mockedPost).toHaveBeenCalledWith('/api/auth/login', {
        employee_id: 'E001',
        password: 'pw',
      })
    })

    it('returns the token data', async () => {
      mockedPost.mockResolvedValue({ data: { access_token: 'abc123', token_type: 'bearer' } })
      const result = await login('E001', 'pw')
      expect(result.access_token).toBe('abc123')
      expect(result.token_type).toBe('bearer')
    })
  })

  describe('getMe()', () => {
    it('calls GET /api/auth/me', async () => {
      mockedGet.mockResolvedValue({ data: mockUser })
      await getMe()
      expect(mockedGet).toHaveBeenCalledWith('/api/auth/me')
    })

    it('returns the user object', async () => {
      mockedGet.mockResolvedValue({ data: mockUser })
      const result = await getMe()
      expect(result).toEqual(mockUser)
    })
  })
})
