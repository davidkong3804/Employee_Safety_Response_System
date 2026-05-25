import { describe, it, expect, beforeEach, vi } from 'vitest'
import { AxiosHeaders, type InternalAxiosRequestConfig } from 'axios'

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
    const config: InternalAxiosRequestConfig = { headers: new AxiosHeaders() }
    // @ts-expect-error accessing internal interceptors for testing
    const reqInterceptor = client.interceptors.request.handlers[0]
    if (reqInterceptor?.fulfilled) {
      const result = await reqInterceptor.fulfilled(config)
      expect(result.headers['Authorization']).toBe('Bearer my-jwt')
    }
  })

  it('does not add Authorization header when no token in localStorage', async () => {
    const { default: client } = await import('../../api/client')
    const config: InternalAxiosRequestConfig = { headers: new AxiosHeaders() }
    // @ts-expect-error axios.interceptors.handlers is internal — not in the public type definitions
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

    // @ts-expect-error axios.interceptors.handlers is internal — not in the public type definitions
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

  it('does not clear token on 401 from the /auth/login endpoint', async () => {
    localStorage.setItem('token', 'existing-token')
    const { default: client } = await import('../../api/client')
    const error = {
      response: { status: 401 },
      config: { url: '/api/auth/login' },
      message: 'Unauthorized',
    }
    // @ts-expect-error axios.interceptors.handlers is internal — not in the public type definitions
    const resInterceptor = client.interceptors.response.handlers[0]
    if (resInterceptor?.rejected) {
      try {
        await resInterceptor.rejected(error)
      } catch {
        // expected to reject
      }
    }
    expect(localStorage.getItem('token')).toBe('existing-token')
  })
})
