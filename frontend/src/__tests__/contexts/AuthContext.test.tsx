import { renderHook, act, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import type { ReactNode } from 'react'
import { AuthProvider, useAuth } from '../../contexts/AuthContext'
import * as authApi from '../../api/auth'
import type { User } from '../../types'

vi.mock('../../api/auth')

const mockedLogin = vi.mocked(authApi.login)
const mockedGetMe = vi.mocked(authApi.getMe)

const mockUser: User = {
  id: 'uuid-1',
  employee_id: 'E001',
  name: 'Test User',
  email: 'test@example.com',
  role: 'employee',
  department: 'Engineering',
  facility: 'Fab14',
  phone: null,
}

function wrapper({ children }: { children: ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>
}

describe('AuthContext', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  describe('initial load', () => {
    it('starts with loading=true', () => {
      mockedGetMe.mockResolvedValue(mockUser)
      localStorage.setItem('token', 'valid-token')
      const { result } = renderHook(() => useAuth(), { wrapper })
      expect(result.current.loading).toBe(true)
    })

    it('resolves to loading=false with user when token is valid', async () => {
      mockedGetMe.mockResolvedValue(mockUser)
      localStorage.setItem('token', 'valid-token')
      const { result } = renderHook(() => useAuth(), { wrapper })
      await waitFor(() => expect(result.current.loading).toBe(false))
      expect(result.current.user).toEqual(mockUser)
    })

    it('resolves to loading=false with null user when no token', async () => {
      const { result } = renderHook(() => useAuth(), { wrapper })
      await waitFor(() => expect(result.current.loading).toBe(false))
      expect(result.current.user).toBeNull()
      expect(mockedGetMe).not.toHaveBeenCalled()
    })

    it('clears token and sets user null when getMe fails', async () => {
      mockedGetMe.mockRejectedValue(new Error('401 Unauthorized'))
      localStorage.setItem('token', 'expired-token')
      const { result } = renderHook(() => useAuth(), { wrapper })
      await waitFor(() => expect(result.current.loading).toBe(false))
      expect(result.current.user).toBeNull()
      expect(localStorage.getItem('token')).toBeNull()
    })
  })

  describe('login', () => {
    it('stores token in localStorage and sets user', async () => {
      mockedLogin.mockResolvedValue({ access_token: 'new-token', token_type: 'bearer' })
      mockedGetMe.mockResolvedValue(mockUser)
      const { result } = renderHook(() => useAuth(), { wrapper })
      await waitFor(() => expect(result.current.loading).toBe(false))

      await act(async () => {
        await result.current.login('E001', 'password')
      })

      expect(localStorage.getItem('token')).toBe('new-token')
      expect(result.current.user).toEqual(mockUser)
    })

    it('calls login API with correct credentials', async () => {
      mockedLogin.mockResolvedValue({ access_token: 'tok', token_type: 'bearer' })
      mockedGetMe.mockResolvedValue(mockUser)
      const { result } = renderHook(() => useAuth(), { wrapper })
      await waitFor(() => expect(result.current.loading).toBe(false))

      await act(async () => {
        await result.current.login('A001', 'pw')
      })

      expect(mockedLogin).toHaveBeenCalledWith('A001', 'pw')
    })
  })

  describe('logout', () => {
    it('removes token from localStorage', async () => {
      mockedGetMe.mockResolvedValue(mockUser)
      localStorage.setItem('token', 'existing-token')
      const { result } = renderHook(() => useAuth(), { wrapper })
      await waitFor(() => expect(result.current.loading).toBe(false))

      act(() => result.current.logout())

      expect(localStorage.getItem('token')).toBeNull()
    })

    it('sets user to null', async () => {
      mockedGetMe.mockResolvedValue(mockUser)
      localStorage.setItem('token', 'existing-token')
      const { result } = renderHook(() => useAuth(), { wrapper })
      await waitFor(() => expect(result.current.loading).toBe(false))
      expect(result.current.user).toEqual(mockUser)

      act(() => result.current.logout())

      expect(result.current.user).toBeNull()
    })
  })
})
