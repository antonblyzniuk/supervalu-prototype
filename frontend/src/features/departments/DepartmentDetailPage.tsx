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
import { useStores } from '@/features/stores/hooks'
import { apiErrorMessage } from '@/lib/apiClient'
import type { StoreDepartmentRow } from '@/types/api'

import { DepartmentFormModal } from './DepartmentFormModal'
import { RoleTiles } from './RoleTiles'
import { StaffTable } from './StaffTable'
import {
  useCreateStoreDepartment,
  useDeleteDepartment,
  useDeleteStoreDepartment,
  useDepartment,
} from './hooks'

/** "Deli in general" — every branch pooled, and split back out by store. */
export function DepartmentDetailPage() {
  const { slug } = useParams<{ slug: string }>()
  const navigate = useNavigate()
  const toast = useToast()
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'

  const departmentQuery = useDepartment(slug)
  const storesQuery = useStores()
  const deleteMutation = useDeleteDepartment()
  const openMutation = useCreateStoreDepartment()
  const closeMutation = useDeleteStoreDepartment()

  const [editing, setEditing] = useState(false)
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const [closing, setClosing] = useState<StoreDepartmentRow | null>(null)

  if (departmentQuery.isLoading) return <PageLoading label="Loading department…" />
  if (departmentQuery.isError || !departmentQuery.data) {
    return (
      <PageError
        message={apiErrorMessage(departmentQuery.error, 'That department could not be loaded.')}
        action={<Button onClick={() => navigate('/departments')}>Back to departments</Button>}
      />
    )
  }

  const department = departmentQuery.data
  const branches = department.stores
  const vacantHeads = branches.filter((branch) => !branch.manager).length

  // Every store gets a row, whether or not it runs this department — the ones
  // that do not are where an admin opens it.
  const rows = (storesQuery.data ?? []).map((store) => ({
    store,
    branch: branches.find((entry) => entry.store.slug === store.slug),
  }))

  async function openInStore(storeSlug: string, storeName: string) {
    try {
      await openMutation.mutateAsync({
        department_slug: department.slug,
        store_slug: storeSlug,
      })
      toast.push(`${department.name} opened in ${storeName}.`, 'success')
    } catch (error) {
      toast.push(apiErrorMessage(error, 'Could not open it in that store.'), 'error')
    }
  }

  async function closeInStore(branch: StoreDepartmentRow) {
    try {
      await closeMutation.mutateAsync(branch.slug)
      toast.push(`${department.name} removed from ${branch.store.name}.`, 'success')
    } catch (error) {
      // The API refuses while staff are still assigned and says how many.
      toast.push(apiErrorMessage(error, 'Could not remove it from that store.'), 'error')
    } finally {
      setClosing(null)
    }
  }

  async function handleDelete() {
    try {
      await deleteMutation.mutateAsync(department.slug)
      toast.push(`${department.name} deleted.`, 'success')
      navigate('/departments')
    } catch (error) {
      // The API refuses while staff are assigned anywhere and says how many.
      toast.push(apiErrorMessage(error, 'Could not delete the department.'), 'error')
    } finally {
      setConfirmingDelete(false)
    }
  }

  // Everything the API knows about the department kind, in display order. A new
  // serializer field becomes one more line here — nothing else changes.
  // Third slot switches the value to the monospace treatment.
  const meta: [string, string, boolean?][] = [
    ['Name', department.name],
    ['Code', department.code || '—', true],
    ['Reference', department.slug, true],
    ['Status', department.is_active ? 'Active' : 'Archived'],
    ['Stores running it', `${branches.length} of ${storesQuery.data?.length ?? branches.length}`],
    ['Created', formatDateTime(department.created_at)],
    ['Last updated', formatDateTime(department.updated_at)],
  ]

  return (
    <div className="u-stack">
      <div className="page-head">
        <div>
          <div className="u-row" style={{ marginBottom: 4 }}>
            {department.is_active ? <Badge tone="ambient">Active</Badge> : <Badge>Archived</Badge>}
            <span className="u-muted" style={{ fontSize: 'var(--text-sm)' }}>
              Across the group
              {department.code ? ` · ${department.code}` : ''}
            </span>
          </div>
          <h1 className="page-head__title">{department.name}</h1>
          <p className="page-head__sub">
            {department.member_count} {department.member_count === 1 ? 'person' : 'people'} in{' '}
            {branches.length} {branches.length === 1 ? 'store' : 'stores'}
          </p>
        </div>
        <div className="page-head__actions">
          <Button variant="ghost" onClick={() => navigate('/departments')}>
            Back
          </Button>
          {isAdmin && <Button onClick={() => setEditing(true)}>Edit</Button>}
          {isAdmin && (
            <Button variant="danger" onClick={() => setConfirmingDelete(true)}>
              Delete
            </Button>
          )}
        </div>
      </div>

      {!department.is_active && (
        <div className="alert alert--info">
          This department is archived. Staff already in it stay put, but it cannot be picked for
          anyone new in any store.
        </div>
      )}

      <RoleTiles
        roles={department.roles}
        totalLabel="Total people"
        totalMeta={`across ${branches.length} ${branches.length === 1 ? 'store' : 'stores'}`}
      >
        <div className="stat">
          <div className="stat__label">Stores</div>
          <div className="stat__value">{branches.length}</div>
          {vacantHeads > 0 && (
            <div className="stat__meta">
              {vacantHeads} without a head
            </div>
          )}
        </div>
      </RoleTiles>

      <Card title="By store" flush>
        <div className="table-scroll">
          <table className="table table--stacked">
            <thead>
              <tr>
                <th scope="col">Store</th>
                <th scope="col">Head of department</th>
                <th scope="col" className="u-right">
                  Staff
                </th>
                <th scope="col" className="u-right">
                  Managers
                </th>
                <th scope="col" className="u-right">
                  People
                </th>
                <th scope="col">
                  <span className="u-sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ store, branch }) =>
                branch ? (
                  <tr key={store.slug}>
                    <td data-label="Store" style={{ fontWeight: 600 }}>
                      <button
                        type="button"
                        className="btn-link"
                        onClick={() => navigate(`/departments/${department.slug}/${store.slug}`)}
                      >
                        {store.name}
                      </button>
                    </td>
                    <td data-label="Head of department">{branch.manager?.full_name ?? '—'}</td>
                    <td className="u-right u-num" data-label="Staff">
                      {branch.roles.staff}
                    </td>
                    <td className="u-right u-num" data-label="Managers">
                      {branch.roles.manager}
                    </td>
                    <td className="u-right u-num" data-label="People" style={{ fontWeight: 700 }}>
                      {branch.member_count}
                    </td>
                    <td className="u-right">
                      {isAdmin && (
                        <Button
                          variant="ghost"
                          size="sm"
                          block
                          onClick={() => setClosing(branch)}
                          disabled={closeMutation.isPending}
                        >
                          Remove
                        </Button>
                      )}
                    </td>
                  </tr>
                ) : (
                  <tr key={store.slug} style={{ opacity: 0.55 }}>
                    <td data-label="Store" style={{ fontWeight: 600 }}>
                      {store.name}
                    </td>
                    {/* No data-label: stacked on a phone this is the card's
                        only line, and "Head of department: does not run this
                        department" would read as nonsense. */}
                    <td colSpan={4}>
                      <span className="u-muted">Does not run this department</span>
                    </td>
                    <td className="u-right">
                      {isAdmin && (
                        <Button
                          variant="secondary"
                          size="sm"
                          block
                          loading={openMutation.isPending}
                          onClick={() => openInStore(store.slug, store.name)}
                        >
                          Open here
                        </Button>
                      )}
                    </td>
                  </tr>
                ),
              )}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={2}>GROUP</td>
                <td className="u-right u-num" data-label="Staff">
                  {department.roles.staff}
                </td>
                <td className="u-right u-num" data-label="Managers">
                  {department.roles.manager}
                </td>
                <td className="u-right u-num" data-label="People">
                  {department.roles.total}
                </td>
                <td />
              </tr>
            </tfoot>
          </table>
        </div>
      </Card>

      <Card title="Details">
        <div className="form-grid">
          {meta.map(([label, value, mono]) => (
            <div key={label}>
              <div className="section-label">{label}</div>
              <div className={mono ? 'u-mono' : undefined}>{value}</div>
            </div>
          ))}
        </div>
        {department.description && (
          <div style={{ marginTop: 'var(--space-4)' }}>
            <div className="section-label">Description</div>
            <p>{department.description}</p>
          </div>
        )}
      </Card>

      <Card title={`Everyone in ${department.name} (${department.members.length})`} flush={department.members.length > 0}>
        {department.members.length === 0 ? (
          <EmptyState
            icon="👥"
            title="Nobody works in this department yet"
            description="Assign colleagues to it from the Team page."
            action={
              <Button variant="secondary" onClick={() => navigate('/team')}>
                Go to Team
              </Button>
            }
          />
        ) : (
          <StaffTable members={department.members} showStore />
        )}
      </Card>

      {isAdmin && (
        <>
          <DepartmentFormModal
            open={editing}
            mode="edit"
            department={department}
            onClose={() => setEditing(false)}
          />
          <Modal
            open={Boolean(closing)}
            title={`Remove ${department.name} from ${closing?.store.name ?? ''}?`}
            onClose={() => setClosing(null)}
            footer={
              <>
                <Button variant="ghost" onClick={() => setClosing(null)}>
                  Cancel
                </Button>
                <Button
                  variant="danger"
                  loading={closeMutation.isPending}
                  onClick={() => closing && closeInStore(closing)}
                >
                  Remove from store
                </Button>
              </>
            }
          >
            <p>
              {closing && closing.member_count > 0 ? (
                <>
                  <strong>{closing.store.name}</strong> still has {closing.member_count}{' '}
                  {closing.member_count === 1 ? 'person' : 'people'} in {department.name}. Move them
                  to another department in that store first.
                </>
              ) : (
                <>
                  <strong>{closing?.store.name}</strong> will stop running {department.name}. It
                  keeps running in the other stores, and you can open it here again later.
                </>
              )}
            </p>
          </Modal>
          <Modal
            open={confirmingDelete}
            title={`Delete ${department.name}?`}
            onClose={() => setConfirmingDelete(false)}
            footer={
              <>
                <Button variant="ghost" onClick={() => setConfirmingDelete(false)}>
                  Cancel
                </Button>
                <Button variant="danger" loading={deleteMutation.isPending} onClick={handleDelete}>
                  Delete department
                </Button>
              </>
            }
          >
            <p>
              {department.member_count > 0 ? (
                <>
                  <strong>{department.name}</strong> still has {department.member_count}{' '}
                  {department.member_count === 1 ? 'person' : 'people'} assigned across the group.
                  Move them to another department first, or archive this one instead of deleting
                  it.
                </>
              ) : (
                <>
                  This removes <strong>{department.name}</strong> from every store, for good. It
                  cannot be undone.
                </>
              )}
            </p>
          </Modal>
        </>
      )}
    </div>
  )
}
