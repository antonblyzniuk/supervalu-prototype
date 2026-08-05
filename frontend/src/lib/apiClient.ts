import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'

import { tokenStore } from './tokens'

const baseURL = import.meta.env.VITE_API_BASE_URL ?? '/api'

export const api = axios.create({
  baseURL,
  headers: { 'Content-Type': 'application/json' },
  // Dockets carry base64 photos, so allow well over a default request time —
  // but not forever, or a dead connection leaves the save button spinning.
  timeout: 60_000,
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

/**
 * Maps a DRF 400 body onto form fields.
 *
 * DRF returns `{field: ["message"]}`, and this API also uses keys like
 * `lines[0].amounts`; those are folded onto `lines` so the message lands
 * somewhere the user can actually see it.
 */
export function fieldErrorsFrom(error: unknown): Record<string, string> {
  if (!axios.isAxiosError(error)) return {}
  const data = error.response?.data
  if (!data || typeof data !== 'object' || data instanceof Blob) return {}

  const result: Record<string, string> = {}
  for (const [key, value] of Object.entries(data as Record<string, unknown>)) {
    if (key === 'detail') continue
    const message = Array.isArray(value) ? String(value[0]) : String(value)
    const field = key.startsWith('lines') ? 'lines' : key
    if (!result[field]) result[field] = message
  }
  return result
}

/**
 * Pulls a readable message out of a DRF error response.
 *
 * Falls back to explaining the status code, because the raw axios message
 * ("Request failed with status code 503") tells a shop-floor user nothing.
 */
export function apiErrorMessage(error: unknown, fallback = 'Something went wrong'): string {
  if (!axios.isAxiosError(error)) return fallback

  if (error.code === 'ERR_NETWORK') {
    return 'Cannot reach the server. Check your connection and try again.'
  }
  if (error.code === 'ECONNABORTED') {
    return 'The server took too long to respond. Your work has not been saved — try again.'
  }

  const status = error.response?.status
  const data = error.response?.data

  if (data && typeof data === 'object' && !(data instanceof Blob)) {
    const record = data as Record<string, unknown>
    const detail = record.detail
    if (typeof detail === 'string') return detail

    const first = Object.values(record)[0]
    if (Array.isArray(first) && typeof first[0] === 'string') return first[0]
    if (typeof first === 'string') return first
  }

  switch (status) {
    case 400:
      return 'Some details are not valid. Check the highlighted fields.'
    case 401:
      return 'Your session has expired. Sign in again.'
    case 403:
      return 'You do not have permission to do that.'
    case 404:
      return 'That item no longer exists.'
    case 413:
      return 'That upload is too large. Remove a photo and try again.'
    case 429:
      return 'Too many attempts. Wait a moment and try again.'
    case 503:
      return 'The server is temporarily unavailable. Nothing was saved — try again shortly.'
    default:
      if (status && status >= 500) {
        return 'The server hit an error. Nothing was saved — try again, and report it if it persists.'
      }
      return error.message || fallback
  }
}
