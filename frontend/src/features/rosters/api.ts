import { api } from '@/lib/apiClient'

/**
 * Downloads a roster through axios so the JWT is attached, then hands the blob
 * to the browser. A plain `<a href>` would hit the API unauthenticated.
 *
 * Passing no departments exports the whole store.
 */
export async function downloadRoster(
  storeSlug: string,
  week: string,
  departmentSlugs: string[] = [],
): Promise<void> {
  const params = new URLSearchParams({ store: storeSlug, week, output: 'pdf' })
  if (departmentSlugs.length) params.set('department', departmentSlugs.join(','))

  const response = await api.get('/rosters/export/', { params, responseType: 'blob' })

  const disposition = String(response.headers['content-disposition'] ?? '')
  const match = disposition.match(/filename="?([^"]+)"?/)
  const filename = match?.[1] ?? `roster-${storeSlug}-${week}.pdf`

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
