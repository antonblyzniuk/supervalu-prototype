import { Link } from 'react-router-dom'
import type { ReactNode } from 'react'

interface ActionCardProps {
  to: string
  icon: ReactNode
  title: string
  description: string
}

export function ActionCard({ to, icon, title, description }: ActionCardProps) {
  return (
    <Link className="action-card" to={to}>
      <span className="action-card__icon" aria-hidden="true">
        {icon}
      </span>
      <span className="action-card__body">
        <span className="action-card__title">{title}</span>
        <span className="action-card__desc">{description}</span>
      </span>
      <span className="action-card__chevron" aria-hidden="true">
        ›
      </span>
    </Link>
  )
}
