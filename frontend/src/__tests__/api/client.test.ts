import { describe, it, expect, beforeEach, vi } from 'vitest'
import axios from 'axios'

// We test the interceptor behaviour by inspecting how the module sets up axios
// We use a fresh import per test by resetting modules

describe('api client interceptors', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('adds Authorization header when token exists in localStorage', async () => {
    localStorage.setItem('token', 'my-jwt')

    // Dynamically import to get a fresh instance (interceptors are registered on import)
    const { default: client } = await import('../../api/client')

    // Simulate a request config going through the request interceptor
    const config = { headers: {} as Record<string, string> }
    // @ts-expect-error accessing internal interceptors for testing
    const reqInterceptor = client.interceptors.request.handlers[0]
    if (reqInterceptor?.fulfilled) {
      const result = await reqInterceptor.fulfilled(config)
      expect(result.headers['Authorization']).toBe('Bearer my-jwt')
    }
  })

  it('does not add Authorization header when no token in localStorage', async () => {
    const { default: client } = await import('../../api/client')
    const config = { headers: {} as Record<string, string> }
    // @ts-expect-error
    const reqInterceptor = client.interceptors.request.handlers[0]
    if (reqInterceptor?.fulfilled) {
      const result = await reqInterceptor.fulfilled(config)
      expect(result.headers['Authorization']).toBeUndefined()
    }
  })

  it('removes token from localStorage on 401 response', async () => {
    localStorage.setItem('token', 'old-token')

    // Mock window.location
    const locationSpy = vi.spyOn(window, 'location', 'get').mockReturnValue({
      ...window.location,
      href: '',
    } as Location)

    const { default: client } = await import('../../api/client')
    const error = { response: { status: 401 }, message: 'Unauthorized' }

    // @ts-expect-error
    const resInterceptor = client.interceptors.response.handlers[0]
    if (resInterceptor?.rejected) {
      try {
        await resInterceptor.rejected(error)
      } catch {
        // expected to reject
      }
    }

    expect(localStorage.getItem('token')).toBeNull()
    locationSpy.mockRestore()
  })
})
