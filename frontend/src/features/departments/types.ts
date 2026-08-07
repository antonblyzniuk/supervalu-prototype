export interface DepartmentInput {
  name: string
  code?: string
  description?: string
  is_active?: boolean
  /** Create only — stores that run it. Omitted means all of them. */
  store_slugs?: string[]
}

export interface StoreDepartmentInput {
  /** User id of the head of department in this branch, or null to clear it. */
  manager_id?: number | null
  notes?: string
}

export interface StoreDepartmentCreate {
  department_slug: string
  store_slug: string
}

export interface DepartmentFilters {
  search?: string
  is_active?: string
}

export interface StoreDepartmentFilters {
  department__slug?: string
  store__slug?: string
  search?: string
}
