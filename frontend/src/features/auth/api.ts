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
