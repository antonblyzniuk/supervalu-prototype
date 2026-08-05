import { createContext } from 'react'

import type { User } from '@/types/api'

export interface AuthContextValue {
  user: User | null
  /** True until the initial "am I already signed in?" check resolves. */
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

// Kept in its own module so the provider file only exports components,
// which is what React Fast Refresh needs to hot-reload it.
export const AuthContext = createContext<AuthContextValue | null>(null)
