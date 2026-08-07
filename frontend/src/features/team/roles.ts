import type { UserRole } from '@/types/api'

/** Badge tone per role, so a colleague looks the same wherever they appear. */
export const ROLE_TONE: Record<UserRole, string> = {
  staff: 'ambient',
  manager: 'chilled',
  admin: 'transfer',
}
