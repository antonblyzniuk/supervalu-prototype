import { useMemo } from 'react'

import { ActionCard } from '@/components/ui/ActionCard'
import { Card } from '@/components/ui/Card'
import { useAuth } from '@/features/auth/useAuth'
import { weekLabel } from '@/features/dockets/format'

function timeOfDayGreeting(date: Date): string {
  const hour = date.getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

export function HomePage() {
  const { user } = useAuth()
  const now = useMemo(() => new Date(), [])

  const name = user?.first_name || user?.full_name || user?.email?.split('@')[0] || 'there'
  const storeLabel = user?.store?.name ?? (user?.is_manager ? 'All stores' : 'No store assigned')

  return (
    <div className="u-stack">
      <div className="greeting">
        <h1 className="greeting__hello">
          {timeOfDayGreeting(now)}, {name}
        </h1>
        <p className="greeting__sub">
          {storeLabel} · {weekLabel(now)}
        </p>
      </div>

      {!user?.store && !user?.is_manager && (
        <div className="alert alert--info">
          Your account has no store assigned yet, so you cannot file dockets. Ask a manager to
          assign you to a store.
        </div>
      )}

      <Card title="Dockets">
        <div className="action-grid">
          <ActionCard
            to="/dockets/new"
            icon="📝"
            title="File a docket"
            description="Ambient, chilled, returns or transfer."
          />
          <ActionCard
            to="/dockets"
            icon="📚"
            title="Browse dockets"
            description="Search and filter everything filed."
          />
          <ActionCard
            to="/dockets/top-sheet"
            icon="📊"
            title="Weekly top sheet"
            description="Running totals and PDF sign-off."
          />
        </div>
      </Card>

      {user?.is_manager && (
        <Card title="Management">
          <div className="action-grid">
            <ActionCard
              to="/team"
              icon="👥"
              title="Team"
              description="Assign staff to stores and manage access."
            />
            <ActionCard
              to="/dockets/top-sheet"
              icon="🏬"
              title="Group reporting"
              description="Compare all three stores in one view."
            />
          </div>
        </Card>
      )}
    </div>
  )
}
