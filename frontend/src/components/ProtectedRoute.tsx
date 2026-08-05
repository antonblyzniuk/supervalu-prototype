import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { PageLoading } from '@/components/ui/PageState'
import { useAuth } from '@/features/auth/useAuth'

export function ProtectedRoute() {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) return <PageLoading />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />

  return <Outlet />
}

/** Manager/admin-only branch. The API enforces this too — this is just the UI. */
export function ManagerRoute() {
  const { user } = useAuth()

  if (!user?.is_manager) {
    return (
      <Card>
        <EmptyState
          icon="🔒"
          title="Managers only"
          description="This area is limited to managers and admins."
        />
      </Card>
    )
  }

  return <Outlet />
}
