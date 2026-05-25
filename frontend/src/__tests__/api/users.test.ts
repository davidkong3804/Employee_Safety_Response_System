import { describe, it, expect, vi, beforeEach } from 'vitest'
import { listUsers, createUser, updateUser, deleteUser } from '../../api/users'
import client from '../../api/client'
import type { UserFull } from '../../types'

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

const mockUser: UserFull = {
  id: 'u-1',
  employee_id: 'E099',
  name: 'New Hire',
  email: 'new.hire@example.com',
  role: 'employee',
  department: 'Engineering',
  facility: 'Fab14',
  phone: '0900-000-099',
  manager_id: null,
  is_active: true,
}

describe('users API', () => {
  beforeEach(() => vi.clearAllMocks())

  describe('listUsers()', () => {
    it('calls GET /api/users with no params when called without args', async () => {
      mockedGet.mockResolvedValue({ data: [mockUser] })
      await listUsers()
      expect(mockedGet).toHaveBeenCalledWith('/api/users', { params: undefined })
    })

    it('forwards role filter as query param', async () => {
      mockedGet.mockResolvedValue({ data: [mockUser] })
      await listUsers({ role: 'manager' })
      expect(mockedGet).toHaveBeenCalledWith('/api/users', { params: { role: 'manager' } })
    })

    it('forwards facility and department filters', async () => {
      mockedGet.mockResolvedValue({ data: [mockUser] })
      await listUsers({ facility: 'Fab14', department: 'Engineering' })
      expect(mockedGet).toHaveBeenCalledWith('/api/users', {
        params: { facility: 'Fab14', department: 'Engineering' },
      })
    })

    it('returns the user array', async () => {
      mockedGet.mockResolvedValue({ data: [mockUser] })
      expect(await listUsers()).toEqual([mockUser])
    })
  })

  describe('createUser()', () => {
    it('POSTs the payload to /api/users', async () => {
      mockedPost.mockResolvedValue({ data: mockUser })
      const payload = { employee_id: 'E099', name: 'New Hire', email: 'x@y.com' }
      await createUser(payload)
      expect(mockedPost).toHaveBeenCalledWith('/api/users', payload)
    })

    it('returns the created user', async () => {
      mockedPost.mockResolvedValue({ data: mockUser })
      const result = await createUser({})
      expect(result).toEqual(mockUser)
    })
  })

  describe('updateUser()', () => {
    it('PATCHes /api/users/{id}', async () => {
      mockedPatch.mockResolvedValue({ data: mockUser })
      await updateUser('u-1', { facility: 'Fab18' })
      expect(mockedPatch).toHaveBeenCalledWith('/api/users/u-1', { facility: 'Fab18' })
    })
  })

  describe('deleteUser()', () => {
    it('DELETEs /api/users/{id}', async () => {
      mockedDelete.mockResolvedValue({})
      await deleteUser('u-1')
      expect(mockedDelete).toHaveBeenCalledWith('/api/users/u-1')
    })
  })
})
