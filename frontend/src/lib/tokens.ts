const ACCESS_KEY = 'sv.access'
const REFRESH_KEY = 'sv.refresh'

/**
 * JWTs live in localStorage: simple, survives reload, and this is an internal
 * tool behind SSO-less login. If we ever serve untrusted content, move to
 * httpOnly cookies instead.
 */
export const tokenStore = {
  getAccess: () => localStorage.getItem(ACCESS_KEY),
  getRefresh: () => localStorage.getItem(REFRESH_KEY),
  set(access: string, refresh?: string) {
    localStorage.setItem(ACCESS_KEY, access)
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh)
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}
