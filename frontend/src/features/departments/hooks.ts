import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { useAuth } from '@/features/auth/useAuth'
import { api } from '@/lib/apiClient'
import type {
  Department,
  DepartmentDetail,
  StoreDepartment,
  StoreDepartmentDetail,
} from '@/types/api'

import type {
  DepartmentInput,
  StoreDepartmentCreate,
  StoreDepartmentFilters,
  StoreDepartmentInput,
} from './types'

const KEY = ['departments'] as const
const BRANCH_KEY = ['store-departments'] as const

function cleanParams(filters: StoreDepartmentFilters): Record<string, string> {
  return Object.fromEntries(
    Object.entries(filters).filter(([, value]) => value !== undefined && value !== ''),
  ) as Record<string, string>
}

/**
 * Department kinds with their group totals. Manager/admin only — the API
 * refuses a staff user outright, so the query stays disabled for them rather
 * than firing a 403 on every render.
 */
export function useDepartments() {
  const { user } = useAuth()
  return useQuery({
    queryKey: KEY,
    enabled: Boolean(user?.is_manager),
    queryFn: async () => {
      const { data } = await api.get<Department[]>('/departments/')
      return data
    },
  })
}

/** "Deli in general" — the per-store breakdown and the combined roster. */
export function useDepartment(slug: string | undefined) {
  return useQuery({
    queryKey: [...KEY, slug],
    enabled: Boolean(slug),
    queryFn: async () => {
      const { data } = await api.get<DepartmentDetail>(`/departments/${slug}/`)
      return data
    },
  })
}

/**
 * Branches, scoped by the API: a manager gets every one, a staff user gets only
 * the department they are in.
 */
export function useStoreDepartments(filters: StoreDepartmentFilters = {}) {
  return useQuery({
    queryKey: [...BRANCH_KEY, filters],
    queryFn: async () => {
      const { data } = await api.get<StoreDepartment[]>('/departments/in-stores/', {
        params: cleanParams(filters),
      })
      return data
    },
  })
}

/** "Deli · Balbriggan" — one branch and its roster. */
export function useStoreDepartment(slug: string | undefined) {
  return useQuery({
    queryKey: [...BRANCH_KEY, slug],
    enabled: Boolean(slug),
    queryFn: async () => {
      const { data } = await api.get<StoreDepartmentDetail>(`/departments/in-stores/${slug}/`)
      return data
    },
  })
}

/**
 * Resolves a department + store pair to its branch.
 *
 * The URL is built from the two slugs people recognise rather than the branch's
 * own slug, so nothing outside the API depends on how that slug is composed.
 */
export function useStoreDepartmentAt(
  departmentSlug: string | undefined,
  storeSlug: string | undefined,
) {
  const query = useStoreDepartments(
    departmentSlug && storeSlug
      ? { department__slug: departmentSlug, store__slug: storeSlug }
      : {},
  )
  const match = departmentSlug && storeSlug ? query.data?.[0] : undefined
  return { ...query, slug: match?.slug }
}

function useDepartmentMutation<TVariables, TResult>(
  mutationFn: (variables: TVariables) => Promise<TResult>,
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: () => {
      // Both levels and the team rows all embed a department.
      queryClient.invalidateQueries({ queryKey: KEY })
      queryClient.invalidateQueries({ queryKey: BRANCH_KEY })
      queryClient.invalidateQueries({ queryKey: ['team'] })
    },
  })
}

export function useCreateDepartment() {
  return useDepartmentMutation(async (payload: DepartmentInput) => {
    const { data } = await api.post<Department>('/departments/', payload)
    return data
  })
}

export function useUpdateDepartment() {
  return useDepartmentMutation(async ({ slug, ...payload }: DepartmentInput & { slug: string }) => {
    const { data } = await api.patch<Department>(`/departments/${slug}/`, payload)
    return data
  })
}

export function useDeleteDepartment() {
  return useDepartmentMutation(async (slug: string) => {
    await api.delete(`/departments/${slug}/`)
  })
}

/** Opens a department in a store that did not run it. */
export function useCreateStoreDepartment() {
  return useDepartmentMutation(async (payload: StoreDepartmentCreate) => {
    const { data } = await api.post<StoreDepartment>('/departments/in-stores/', payload)
    return data
  })
}

/** Closes it there. The API refuses while anybody is still assigned. */
export function useDeleteStoreDepartment() {
  return useDepartmentMutation(async (slug: string) => {
    await api.delete(`/departments/in-stores/${slug}/`)
  })
}

export function useUpdateStoreDepartment() {
  return useDepartmentMutation(
    async ({ slug, ...payload }: StoreDepartmentInput & { slug: string }) => {
      const { data } = await api.patch<StoreDepartment>(
        `/departments/in-stores/${slug}/`,
        payload,
      )
      return data
    },
  )
}
