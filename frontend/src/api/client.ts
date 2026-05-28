import axios, { AxiosError, AxiosRequestConfig } from 'axios'

const API_URL = import.meta.env.VITE_API_URL || ''

const MAX_RETRIES = 2
const RETRY_BASE_DELAY_MS = 300
const RETRYABLE_STATUS = new Set([502, 503, 504])
const RETRYABLE_POST_PATHS = [/^\/api\/events\/[^/]+\/report$/]

type RetryableConfig = AxiosRequestConfig & { __retryCount?: number }

const client = axios.create({
  baseURL: API_URL,
  timeout: 10000,
})

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

function isRetryable(error: AxiosError, config: RetryableConfig): boolean {
  if (axios.isCancel(error)) return false
  const method = (config.method || 'get').toLowerCase()
  const url = config.url || ''
  if (method === 'post') {
    const path = url.startsWith('http') ? new URL(url).pathname : url
    if (!RETRYABLE_POST_PATHS.some((re) => re.test(path))) return false
  } else if (method !== 'get') {
    return false
  }
  if (!error.response) return true
  return RETRYABLE_STATUS.has(error.response.status)
}

const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms))

client.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as RetryableConfig | undefined

    if (config && isRetryable(error, config)) {
      const attempt = (config.__retryCount ?? 0) + 1
      if (attempt <= MAX_RETRIES) {
        config.__retryCount = attempt
        await delay(RETRY_BASE_DELAY_MS * Math.pow(3, attempt - 1))
        return client.request(config)
      }
    }

    // Surface rate-limit to callers with a clear message for toast display.
    if (error.response?.status === 429) {
      const detail = (error.response.data as Record<string, string>)?.detail || 'Too many requests'
      error.message = detail
      return Promise.reject(error)
    }

    if (error.response?.status === 401 && !error.config?.url?.includes('/auth/login')) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default client
