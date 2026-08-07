import { Navigate } from 'react-router-dom'

import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { useAuth } from '@/features/auth/useAuth'

import { DepartmentListPage } from './DepartmentListPage'

/**
 * What `/departments` means depends on who is asking.
 *
 * Managers and admins get the group-wide list, which pools every store. A staff
 * user is scoped to one branch of one department, so they go straight to it —
 * the pooled endpoint would refuse them anyway.
 */
export function DepartmentsIndex() {
  const { user } = useAuth()

  if (user?.is_manager) return <DepartmentListPage />

  if (user?.department) {
    const { department, store } = user.department
    return <Navigate to={`/departments/${department.slug}/${store.slug}`} replace />
  }

  return (
    <Card>
      <EmptyState
        icon="🏷️"
        title="You are not in a department yet"
        description="Ask a manager to assign you to one on the Team page. Until then there is nothing here to show."
      />
    </Card>
  )
}
