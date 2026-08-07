import type { Store, StoreDepartmentLabel, UserRole } from '@/types/api'

export interface TeamMember {
  id: number
  email: string
  first_name: string
  last_name: string
  full_name: string
  role: UserRole
  employee_id: string
  phone: string
  store: Store | null
  department: StoreDepartmentLabel | null
  /** Euro per hour. Null means the national minimum wage applies. */
  hourly_rate: string | null
  is_active: boolean
  last_login: string | null
  date_joined: string
}

export interface TeamMemberUpdate {
  first_name?: string
  last_name?: string
  role?: UserRole
  employee_id?: string
  phone?: string
  /** Store slug, or null to unassign. */
  store_slug?: string | null
  /**
   * Slug of a branch of a department ("deli-at-balbriggan"). Implies the store,
   * and cannot be cleared — everyone belongs somewhere.
   */
  department_slug?: string
  is_active?: boolean
}

export interface TeamMemberCreate extends TeamMemberUpdate {
  email: string
  password: string
  /** Required on create: a new colleague always starts in a department. */
  department_slug: string
}

export interface TeamFilters {
  store__slug?: string
  /** One branch of a department. */
  department__slug?: string
  /** A department across every store. */
  department__department__slug?: string
  role?: UserRole
  is_active?: string
  search?: string
  /** Caps at the API's max_page_size of 200. */
  page_size?: string
}
