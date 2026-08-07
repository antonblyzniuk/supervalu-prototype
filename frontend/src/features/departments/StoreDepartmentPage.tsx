import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { Modal } from '@/components/ui/Modal'
import { PageError, PageLoading } from '@/components/ui/PageState'
import { useToast } from '@/components/ui/useToast'
import { useAuth } from '@/features/auth/useAuth'
import { formatDateTime } from '@/features/dockets/format'
import { apiErrorMessage } from '@/lib/apiClient'

import { RoleTiles } from './RoleTiles'
import { StaffTable } from './StaffTable'
import { StoreDepartmentFormModal } from './StoreDepartmentFormModal'
import { useDeleteStoreDepartment, useStoreDepartment, useStoreDepartmentAt } from './hooks'

/**
 * "Deli · Balbriggan" — one department in one store, and its roster.
 *
 * The only department screen a staff user can reach, and only for the branch
 * they are in; the API returns 404 for any other, so no extra guard is needed
 * here beyond rendering what came back.
 */
export function StoreDepartmentPage() {
  const { slug, storeSlug } = useParams<{ slug: string; storeSlug: string }>()
  const navigate = useNavigate()
  const toast = useToast()
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'

  // The URL names the department and the store; the branch's own slug is an
  // API detail, so it is looked up rather than composed here.
  const lookup = useStoreDepartmentAt(slug, storeSlug)
  const branchQuery = useStoreDepartment(lookup.slug)

  const removeMutation = useDeleteStoreDepartment()

  const [editing, setEditing] = useState(false)
  const [confirmingRemove, setConfirmingRemove] = useState(false)

  if (lookup.isLoading || (lookup.slug && branchQuery.isLoading)) {
    return <PageLoading label="Loading department…" />
  }
  if (lookup.isError || (!lookup.slug && !lookup.isLoading)) {
    return (
      <PageError
        message={apiErrorMessage(
          lookup.error,
          'That department could not be loaded — it may not run in that store, or it may not be yours to see.',
        )}
        action={
          user?.is_manager ? (
            <Button onClick={() => navigate('/departments')}>Back to departments</Button>
          ) : undefined
        }
      />
    )
  }
  if (branchQuery.isError || !branchQuery.data) {
    return (
      <PageError
        message={apiErrorMessage(branchQuery.error, 'That department could not be loaded.')}
      />
    )
  }

  const branch = branchQuery.data
  const members = branch.members

  async function handleRemove() {
    try {
      await removeMutation.mutateAsync(branch.slug)
      toast.push(`${branch.department.name} removed from ${branch.store.name}.`, 'success')
      navigate(`/departments/${slug}`)
    } catch (error) {
      // The API refuses while staff are still assigned and says how many.
      toast.push(apiErrorMessage(error, 'Could not remove it from that store.'), 'error')
    } finally {
      setConfirmingRemove(false)
    }
  }

  const meta: [string, string, boolean?][] = [
    ['Department', branch.department.name],
    ['Store', branch.store.name],
    ['Code', branch.department.code || '—', true],
    ['Reference', branch.slug, true],
    ['Head of department', branch.manager?.full_name ?? 'Nobody assigned'],
    ['People assigned', String(branch.member_count)],
    ['Created', formatDateTime(branch.created_at)],
    ['Last updated', formatDateTime(branch.updated_at)],
  ]

  return (
    <div className="u-stack">
      <div className="page-head">
        <div>
          <div className="u-row" style={{ marginBottom: 4 }}>
            <Badge tone="ambient">{branch.store.name}</Badge>
            {branch.department.code && (
              <span className="u-muted u-mono" style={{ fontSize: 'var(--text-sm)' }}>
                {branch.department.code}
              </span>
            )}
          </div>
          <h1 className="page-head__title">
            {branch.department.name} · {branch.store.name}
          </h1>
          <p className="page-head__sub">
            {branch.member_count} {branch.member_count === 1 ? 'person' : 'people'}
            {branch.manager ? ` · led by ${branch.manager.full_name}` : ''}
          </p>
        </div>
        <div className="page-head__actions">
          {/* Only managers have anywhere to go back to — a staff user lands
              here from the nav, and this is the whole tab for them. */}
          {user?.is_manager && (
            <Button variant="ghost" onClick={() => navigate(`/departments/${slug}`)}>
              Across the group
            </Button>
          )}
          {isAdmin && <Button onClick={() => setEditing(true)}>Edit</Button>}
          {isAdmin && (
            <Button variant="danger" onClick={() => setConfirmingRemove(true)}>
              Remove from store
            </Button>
          )}
        </div>
      </div>

      <RoleTiles roles={branch.roles} totalLabel="People" totalMeta={branch.store.name} />

      <Card title="Details">
        <div className="form-grid">
          {meta.map(([label, value, mono]) => (
            <div key={label}>
              <div className="section-label">{label}</div>
              <div className={mono ? 'u-mono' : undefined}>{value}</div>
            </div>
          ))}
        </div>
        {branch.notes && (
          <div style={{ marginTop: 'var(--space-4)' }}>
            <div className="section-label">Notes for this store</div>
            <p>{branch.notes}</p>
          </div>
        )}
      </Card>

      <Card title={`Staff (${members.length})`} flush={members.length > 0}>
        {members.length === 0 ? (
          <EmptyState
            icon="👥"
            title="Nobody works here yet"
            description={
              user?.is_manager
                ? 'Assign colleagues to this department from the Team page.'
                : 'A manager assigns colleagues to a department from the Team page.'
            }
            action={
              user?.is_manager ? (
                <Button variant="secondary" onClick={() => navigate('/team')}>
                  Go to Team
                </Button>
              ) : undefined
            }
          />
        ) : (
          <StaffTable members={members} />
        )}
      </Card>

      {isAdmin && (
        <>
          <StoreDepartmentFormModal
            open={editing}
            branch={branch}
            onClose={() => setEditing(false)}
          />
          <Modal
            open={confirmingRemove}
            title={`Remove ${branch.department.name} from ${branch.store.name}?`}
            onClose={() => setConfirmingRemove(false)}
            footer={
              <>
                <Button variant="ghost" onClick={() => setConfirmingRemove(false)}>
                  Cancel
                </Button>
                <Button
                  variant="danger"
                  loading={removeMutation.isPending}
                  onClick={handleRemove}
                >
                  Remove from store
                </Button>
              </>
            }
          >
            <p>
              {branch.member_count > 0 ? (
                <>
                  <strong>{branch.store.name}</strong> still has {branch.member_count}{' '}
                  {branch.member_count === 1 ? 'person' : 'people'} in {branch.department.name}.
                  Move them to another department in this store first.
                </>
              ) : (
                <>
                  <strong>{branch.store.name}</strong> will stop running{' '}
                  {branch.department.name}. It keeps running in the other stores, and you can open
                  it here again later.
                </>
              )}
            </p>
          </Modal>
        </>
      )}
    </div>
  )
}
