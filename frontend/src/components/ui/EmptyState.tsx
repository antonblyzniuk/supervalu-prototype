import type { ReactNode } from 'react'

interface EmptyStateProps {
  icon?: string
  title: string
  description?: ReactNode
  action?: ReactNode
}

export function EmptyState({ icon = '📋', title, description, action }: EmptyStateProps) {
  return (
    <div className="empty">
      <div className="empty__icon" aria-hidden="true">
        {icon}
      </div>
      <div className="empty__title">{title}</div>
      {description && <p className="u-muted">{description}</p>}
      {action && <div style={{ marginTop: 'var(--space-4)' }}>{action}</div>}
    </div>
  )
}
