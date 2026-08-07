import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/lib/apiClient'
import type { RosterBoard, Shift } from '@/types/api'

import type { ShiftInput, ShiftUpdate } from './types'

const KEY = ['roster-board'] as const

/**
 * A store's week: everyone who works there, grouped by department, with their
 * shifts and what the week costs. Reading it creates nothing, so opening a week
 * nobody has rostered yet is free.
 */
export function useRosterBoard(storeSlug: string | undefined, week: string) {
  return useQuery({
    queryKey: [...KEY, storeSlug, week],
    enabled: Boolean(storeSlug),
    queryFn: async () => {
      const { data } = await api.get<RosterBoard>('/rosters/board/', {
        params: { store: storeSlug, week },
      })
      return data
    },
    // Keeps the previous week on screen while the next one loads, so paging
    // through weeks does not flash an empty table.
    placeholderData: (previous) => previous,
  })
}

function useShiftMutation<TVariables, TResult>(
  mutationFn: (variables: TVariables) => Promise<TResult>,
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: KEY }),
  })
}

export function useCreateShift() {
  return useShiftMutation(async (payload: ShiftInput) => {
    const { data } = await api.post<Shift>('/rosters/shifts/', payload)
    return data
  })
}

export function useUpdateShift() {
  return useShiftMutation(async ({ id, ...payload }: ShiftUpdate & { id: number }) => {
    const { data } = await api.patch<Shift>(`/rosters/shifts/${id}/`, payload)
    return data
  })
}

export function useDeleteShift() {
  return useShiftMutation(async (id: number) => {
    await api.delete(`/rosters/shifts/${id}/`)
  })
}
