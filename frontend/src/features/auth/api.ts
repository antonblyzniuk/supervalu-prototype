import { api } from '@/lib/apiClient'
import type { TokenPair, User } from '@/types/api'

export async function obtainTokens(email: string, password: string): Promise<TokenPair> {
  const { data } = await api.post<TokenPair>('/auth/token/', { email, password })
  return data
}

export async function fetchMe(): Promise<User> {
  const { data } = await api.get<User>('/auth/me/')
  return data
}

export interface AdminBootstrapPayload {
  secret_code: string
  email: string
  password: string
  first_name?: string
  last_name?: string
}

/** Creates an admin account by presenting the shared setup code. */
export async function bootstrapAdmin(payload: AdminBootstrapPayload): Promise<User> {
  const { data } = await api.post<User>('/auth/bootstrap-admin/', payload)
  return data
}
