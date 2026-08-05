export type UserRole = 'staff' | 'manager' | 'admin'

export interface Store {
  id: number
  code: string
  slug: string
  name: string
  is_active: boolean
}

export interface User {
  id: number
  email: string
  first_name: string
  last_name: string
  full_name: string
  role: UserRole
  is_manager: boolean
  employee_id: string
  /** Home store — pre-selected on new dockets. Null until an admin assigns one. */
  store: Store | null
  phone: string
  is_staff: boolean
  date_joined: string
}

export interface TokenPair {
  access: string
  refresh: string
}

/** Shape returned by DefaultPagination on list endpoints. */
export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}
