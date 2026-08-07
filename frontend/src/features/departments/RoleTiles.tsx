import type { ReactNode } from 'react'

import type { RoleCounts } from '@/types/api'

interface RoleTilesProps {
  roles: RoleCounts
  /** Label for the headline tile — "People" for a branch, "Total people" pooled. */
  totalLabel: string
  totalMeta?: string
  /** Extra tiles rendered before the role split, e.g. a store count. */
  children?: ReactNode
}

/**
 * The headcount split by role, as stat tiles.
 *
 * One component for a single branch and for the group total, because the API
 * reports both under the same shape.
 */
export function RoleTiles({ roles, totalLabel, totalMeta, children }: RoleTilesProps) {
  return (
    <div className="stat-grid">
      <div className="stat stat--brand">
        <div className="stat__label">{totalLabel}</div>
        <div className="stat__value">{roles.total}</div>
        {totalMeta && <div className="stat__meta">{totalMeta}</div>}
      </div>
      {children}
      <div className="stat">
        <div className="stat__label">Staff</div>
        <div className="stat__value">{roles.staff}</div>
      </div>
      <div className="stat">
        <div className="stat__label">Managers</div>
        <div className="stat__value">{roles.manager}</div>
      </div>
      {roles.admin > 0 && (
        <div className="stat">
          <div className="stat__label">Admins</div>
          <div className="stat__value">{roles.admin}</div>
        </div>
      )}
    </div>
  )
}
