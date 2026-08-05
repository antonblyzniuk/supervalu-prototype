import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'

import { tokenStore } from './tokens'

const baseURL = import.meta.env.VITE_API_BASE_URL ?? '/api'

export const api = axios.create({
  baseURL,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const token = tokenStore.getAccess()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

type RetriableConfig = InternalAxiosRequestConfig & { _retried?: boolean }

/** Refreshes are shared so a burst of 401s triggers exactly one refresh call. */
let refreshInFlight: Promise<string> | null = null

async function refreshAccessToken(): Promise<string> {
  const refresh = tokenStore.getRefresh()
  if (!refresh) throw new Error('No refresh token')

  // Bare axios: the instance interceptors would attach the dead access token.
  const { data } = await axios.post<{ access: string; refresh?: string }>(
    `${baseURL}/auth/token/refresh/`,
    { refresh },
  )
  tokenStore.set(data.access, data.refresh)
  return data.access
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as RetriableConfig | undefined
    const isAuthCall = config?.url?.includes('/auth/token')

    if (error.response?.status !== 401 || !config || config._retried || isAuthCall) {
      return Promise.reject(error)
    }

    config._retried = true
    try {
      refreshInFlight ??= refreshAccessToken().finally(() => {
        refreshInFlight = null
      })
      const access = await refreshInFlight
      config.headers.Authorization = `Bearer ${access}`
      return api.request(config)
    } catch {
      tokenStore.clear()
      window.dispatchEvent(new Event('auth:logout'))
      return Promise.reject(error)
    }
  },
)

/** Pulls a readable message out of a DRF error response. */
export function apiErrorMessage(error: unknown, fallback = 'Something went wrong'): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as Record<string, unknown> | undefined
    const detail = data?.detail
    if (typeof detail === 'string') return detail
    if (data) {
      const first = Object.values(data)[0]
      if (Array.isArray(first) && typeof first[0] === 'string') return first[0]
      if (typeof first === 'string') return first
    }
    return error.message || fallback
  }
  return fallback
}
