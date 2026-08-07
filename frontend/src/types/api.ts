export type UserRole = 'staff' | 'manager' | 'admin'

export interface Store {
  id: number
  code: string
  slug: string
  name: string
  is_active: boolean
}

/** Compact staff row as the department endpoints return it. */
export interface DepartmentPerson {
  id: number
  email: string
  full_name: string
  role: UserRole
  employee_id: string
  store: Store | null
  is_active: boolean
}

/** Active headcount split by role. `total` is the sum. */
export type RoleCounts = Record<UserRole | 'total', number>

/** A kind of department — "the Deli", group-wide. Nobody is assigned to one. */
export interface DepartmentBrief {
  id: number
  name: string
  slug: string
  code: string
  is_active: boolean
}

export interface Department extends DepartmentBrief {
  description: string
  /** Active people in this department across every branch. */
  member_count: number
  /** Stores that run it — not every branch runs every department. */
  store_count: number
  created_at: string
  updated_at: string
}

/**
 * A department in one branch — "Deli · Balbriggan". This is what staff are
 * assigned to, so every roster is store specific.
 */
export interface StoreDepartmentLabel {
  id: number
  slug: string
  department: DepartmentBrief
  store: Store
}

/** A branch with its numbers — one line of the group-wide breakdown. */
export interface StoreDepartmentRow extends StoreDepartmentLabel {
  manager: DepartmentPerson | null
  member_count: number
  roles: RoleCounts
}

export interface StoreDepartment extends StoreDepartmentRow {
  notes: string
  created_at: string
  updated_at: string
}

/** What `/departments/in-stores/:slug/` adds on top of the row. */
export interface StoreDepartmentDetail extends StoreDepartment {
  members: DepartmentPerson[]
}

/** What `/departments/:slug/` adds: the same numbers, pooled and split. */
export interface DepartmentDetail extends Department {
  stores: StoreDepartmentRow[]
  roles: RoleCounts
  members: DepartmentPerson[]
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
  /** Their branch of a department. Implies `store`; the two always agree. */
  department: StoreDepartmentLabel | null
  phone: string
  /** Euro per hour. Null means the national minimum wage applies. */
  hourly_rate: string | null
  is_staff: boolean
  date_joined: string
}

/** Hours and cost, reported the same way for a person, a department, a store. */
export interface RosterTotals {
  shift_count: number
  paid_minutes: number
  /** Decimal string, two places. */
  hours: string
  /** Euro, decimal string. */
  cost: string
}

export interface Shift {
  id: number
  date: string
  /** "HH:MM:SS" as Django renders a TimeField. */
  start_time: string
  end_time: string
  break_minutes: number
  break_paid: boolean
  notes: string
  /** Clock-in to clock-out, breaks included. */
  duration_minutes: number
  /** The span less any unpaid break — what gets paid. */
  paid_minutes: number
  hours: string
  cost: string
  hourly_rate: string
}

export interface RosterPerson {
  id: number
  full_name: string
  email: string
  role: UserRole
  hourly_rate: string
  /** True when no rate is set and the minimum wage is standing in. */
  rate_is_default: boolean
  /**
   * False for somebody deactivated who still holds shifts this week — they stay
   * on the board so the store total matches the rows under it.
   */
  is_active: boolean
}

export interface RosterPersonRow {
  person: RosterPerson
  shifts: Shift[]
  totals: RosterTotals
}

export interface RosterDepartment {
  /** Null for the trailing "No department" group. */
  id: number | null
  slug: string | null
  name: string
  code: string
  department_slug: string | null
  people: RosterPersonRow[]
  totals: RosterTotals
}

/** A store's trading week: everyone who works there, and what the week costs. */
export interface RosterBoard {
  store: { id: number; slug: string; name: string; code: string }
  week_start: string
  week_end: string
  days: string[]
  minimum_hourly_rate: string
  departments: RosterDepartment[]
  totals: RosterTotals & { people_total: number; people_rostered: number }
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
