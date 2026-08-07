import axios from 'axios'
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'

import { tokenStore } from '@/lib/tokens'
import type { User } from '@/types/api'

import { fetchMe, obtainTokens } from './api'
import { AuthContext, type AuthContextValue } from './authContext'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const logout = useCallback(() => {
    tokenStore.clear()
    setUser(null)
  }, [])

  // Restore the session from a stored token on first load.
  useEffect(() => {
    if (!tokenStore.getAccess()) {
      setLoading(false)
      return
    }
    let cancelled = false
    fetchMe()
      .then((me) => {
        if (!cancelled) setUser(me)
      })
      .catch((error) => {
        if (cancelled) return
        // Only a rejection from the server clears the session. A restart or a
        // dropped connection leaves the stored token perfectly good, and
        // throwing it away signs everybody out over a blip — reloading once the
        // server is back should just work.
        if (axios.isAxiosError(error) && !error.response) return
        tokenStore.clear()
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  // The axios interceptor fires this when a refresh fails for good.
  useEffect(() => {
    window.addEventListener('auth:logout', logout)
    return () => window.removeEventListener('auth:logout', logout)
  }, [logout])

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await obtainTokens(email, password)
    tokenStore.set(tokens.access, tokens.refresh)
    setUser(await fetchMe())
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({ user, loading, login, logout }),
    [user, loading, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
