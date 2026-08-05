import { useQuery } from '@tanstack/react-query'

import { useAuth } from '@/features/auth/useAuth'
import { api } from '@/lib/apiClient'
import type { Store } from '@/types/api'

async function fetchStores(): Promise<Store[]> {
  const { data } = await api.get<Store[]>('/stores/')
  return data
}

export function useStores() {
  return useQuery({
    queryKey: ['stores'],
    queryFn: fetchStores,
    staleTime: Infinity, // Reference data — three branches, seeded by migration.
  })
}

/**
 * Stores the user may browse reports for. Managers get the group; staff get
 * only their own branch, so filters never offer a scope the API would refuse.
 * The full list stays available via `useStores` for transfer destinations.
 */
export function useVisibleStores(): Store[] {
  const { user } = useAuth()
  const { data } = useStores()
  const stores = data ?? []

  if (user?.is_manager) return stores
  return stores.filter((store) => store.slug === user?.store?.slug)
}
