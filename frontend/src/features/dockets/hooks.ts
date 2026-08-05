import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createDocket,
  deleteDocket,
  fetchDocket,
  fetchDocketMeta,
  fetchDockets,
  fetchSummary,
  updateDocket,
} from './api'
import type { DocketDraft, DocketFilters } from './types'

const keys = {
  all: ['dockets'] as const,
  meta: ['dockets', 'meta'] as const,
  list: (filters: DocketFilters) => ['dockets', 'list', filters] as const,
  detail: (id: string) => ['dockets', 'detail', id] as const,
  summary: (filters: DocketFilters) => ['dockets', 'summary', filters] as const,
}

export function useDocketMeta() {
  return useQuery({
    queryKey: keys.meta,
    queryFn: fetchDocketMeta,
    staleTime: Infinity, // Column definitions only change with a deploy.
  })
}

export function useDockets(filters: DocketFilters) {
  return useQuery({ queryKey: keys.list(filters), queryFn: () => fetchDockets(filters) })
}

export function useDocket(id: string | undefined) {
  return useQuery({
    queryKey: keys.detail(id ?? ''),
    queryFn: () => fetchDocket(id as string),
    enabled: Boolean(id),
  })
}

export function useDocketSummary(filters: DocketFilters) {
  return useQuery({ queryKey: keys.summary(filters), queryFn: () => fetchSummary(filters) })
}

export function useCreateDocket() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (draft: Partial<DocketDraft>) => createDocket(draft),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.all }),
  })
}

export function useUpdateDocket(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (draft: Partial<DocketDraft>) => updateDocket(id, draft),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.all }),
  })
}

export function useDeleteDocket() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deleteDocket(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.all }),
  })
}
