import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/lib/apiClient'
import type { Paginated } from '@/types/api'

import type { TeamFilters, TeamMember, TeamMemberCreate, TeamMemberUpdate } from './types'

const KEY = ['team'] as const

function cleanParams(filters: TeamFilters): Record<string, string> {
  return Object.fromEntries(
    Object.entries(filters).filter(([, value]) => value !== undefined && value !== ''),
  ) as Record<string, string>
}

export function useTeam(filters: TeamFilters) {
  return useQuery({
    queryKey: [...KEY, filters],
    queryFn: async () => {
      const { data } = await api.get<Paginated<TeamMember>>('/auth/team/', {
        params: cleanParams(filters),
      })
      return data
    },
  })
}

export function useCreateTeamMember() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: TeamMemberCreate) => {
      const { data } = await api.post<TeamMember>('/auth/team/', payload)
      return data
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEY }),
  })
}

export function useUpdateTeamMember() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...payload }: TeamMemberUpdate & { id: number }) => {
      const { data } = await api.patch<TeamMember>(`/auth/team/${id}/`, payload)
      return data
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEY }),
  })
}

export function useSetTeamPassword() {
  return useMutation({
    mutationFn: async ({ id, password }: { id: number; password: string }) => {
      const { data } = await api.post(`/auth/team/${id}/set-password/`, { password })
      return data
    },
  })
}
