import type { Store, UserRole } from '@/types/api'

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
  is_active?: boolean
}

export interface TeamMemberCreate extends TeamMemberUpdate {
  email: string
  password: string
}

export interface TeamFilters {
  store__slug?: string
  role?: UserRole
  is_active?: string
  search?: string
}
