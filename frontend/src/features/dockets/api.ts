import { api } from '@/lib/apiClient'
import type { Paginated } from '@/types/api'

import type {
  Docket,
  DocketDraft,
  DocketFilters,
  DocketListItem,
  DocketMeta,
  DocketSummary,
} from './types'

/** Turns the filter object into query params, dropping empty values. */
export function toParams(filters: DocketFilters): URLSearchParams {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value === undefined || value === null || value === '') continue
    if (Array.isArray(value)) {
      if (!value.length) continue
      params.set(key, value.join(','))
    } else {
      params.set(key, String(value))
    }
  }
  return params
}

export async function fetchDocketMeta(): Promise<DocketMeta> {
  const { data } = await api.get<DocketMeta>('/dockets/meta/')
  return data
}

export async function fetchDockets(filters: DocketFilters): Promise<Paginated<DocketListItem>> {
  const { data } = await api.get<Paginated<DocketListItem>>('/dockets/', {
    params: toParams(filters),
  })
  return data
}

export async function fetchDocket(id: string): Promise<Docket> {
  const { data } = await api.get<Docket>(`/dockets/${id}/`)
  return data
}

export async function fetchSummary(filters: DocketFilters): Promise<DocketSummary> {
  const { data } = await api.get<DocketSummary>('/dockets/summary/', { params: toParams(filters) })
  return data
}

export async function createDocket(draft: Partial<DocketDraft>): Promise<Docket> {
  const { data } = await api.post<Docket>('/dockets/', draft)
  return data
}

export async function updateDocket(id: string, draft: Partial<DocketDraft>): Promise<Docket> {
  const { data } = await api.patch<Docket>(`/dockets/${id}/`, draft)
  return data
}

export async function deleteDocket(id: string): Promise<void> {
  await api.delete(`/dockets/${id}/`)
}

/**
 * Downloads an export through axios so the JWT is attached, then hands the
 * blob to the browser. A plain `<a href>` would hit the API unauthenticated.
 */
export async function downloadExport(
  filters: DocketFilters,
  output: 'json' | 'pdf',
): Promise<void> {
  const params = toParams(filters)
  params.set('output', output)

  const response = await api.get('/dockets/export/', { params, responseType: 'blob' })

  const disposition = String(response.headers['content-disposition'] ?? '')
  const match = disposition.match(/filename="?([^"]+)"?/)
  const filename = match?.[1] ?? `dockets.${output}`

  const url = URL.createObjectURL(response.data as Blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  // Revoking immediately can cancel the download in Safari.
  window.setTimeout(() => URL.revokeObjectURL(url), 4000)
}
