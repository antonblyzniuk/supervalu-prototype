import type { ReactNode } from 'react'

export function PageLoading({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="page-state">
      <span className="spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  )
}

export function PageError({ message, action }: { message: ReactNode; action?: ReactNode }) {
  return (
    <div className="page-state">
      <div className="alert alert--error">{message}</div>
      {action}
    </div>
  )
}
