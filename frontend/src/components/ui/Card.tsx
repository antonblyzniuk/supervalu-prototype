import type { ReactNode } from 'react'

interface CardProps {
  title?: ReactNode
  actions?: ReactNode
  footer?: ReactNode
  flush?: boolean
  className?: string
  children: ReactNode
}

export function Card({ title, actions, footer, flush, className = '', children }: CardProps) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="card__header">
          {title ? <h2 className="card__title">{title}</h2> : <span />}
          {actions}
        </header>
      )}
      <div className={`card__body ${flush ? 'card__body--flush' : ''}`}>{children}</div>
      {footer && <footer className="card__footer">{footer}</footer>}
    </section>
  )
}
