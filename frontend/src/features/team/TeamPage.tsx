import { useState } from 'react'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { Field } from '@/components/ui/Field'
import { PageError, PageLoading } from '@/components/ui/PageState'
import { useToast } from '@/components/ui/useToast'
import { useAuth } from '@/features/auth/useAuth'
import { useStores } from '@/features/stores/hooks'
import { formatDate } from '@/features/dockets/format'
import { apiErrorMessage } from '@/lib/apiClient'

import { MemberFormModal } from './MemberFormModal'
import { useTeam, useUpdateTeamMember } from './hooks'
import type { TeamFilters, TeamMember } from './types'

const ROLE_TONE: Record<string, string> = {
  staff: 'ambient',
  manager: 'chilled',
  admin: 'transfer',
}

export function TeamPage() {
  const { user } = useAuth()
  const toast = useToast()
  const storesQuery = useStores()

  const [filters, setFilters] = useState<TeamFilters>({})
  const [editing, setEditing] = useState<TeamMember | null>(null)
  const [creating, setCreating] = useState(false)

  const teamQuery = useTeam(filters)
  const updateMutation = useUpdateTeamMember()

  /** Store assignment is the whole point of this page, so it edits in place. */
  async function assignStore(member: TeamMember, slug: string) {
    try {
      await updateMutation.mutateAsync({ id: member.id, store_slug: slug || null })
      toast.push(
        slug
          ? `${member.full_name} assigned to ${storesQuery.data?.find((s) => s.slug === slug)?.name}`
          : `${member.full_name} unassigned`,
        'success',
      )
    } catch (error) {
      toast.push(apiErrorMessage(error, 'Could not update the assignment.'), 'error')
    }
  }

  const members = teamQuery.data?.results ?? []

  return (
    <div className="u-stack">
      <div className="page-head">
        <div>
          <h1 className="page-head__title">Team</h1>
          <p className="page-head__sub">
            Assign colleagues to a store. Staff only see dockets for the store set here.
          </p>
        </div>
        <div className="page-head__actions">
          <Button onClick={() => setCreating(true)}>Add colleague</Button>
        </div>
      </div>

      <Card title="Filters">
        <div className="form-grid">
          <Field label="Store">
            <select
              className="select"
              value={filters.store__slug ?? ''}
              onChange={(e) => setFilters({ ...filters, store__slug: e.target.value || undefined })}
            >
              <option value="">All stores</option>
              {storesQuery.data?.map((store) => (
                <option key={store.slug} value={store.slug}>
                  {store.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Role">
            <select
              className="select"
              value={filters.role ?? ''}
              onChange={(e) =>
                setFilters({ ...filters, role: (e.target.value || undefined) as TeamFilters['role'] })
              }
            >
              <option value="">All roles</option>
              <option value="staff">Staff</option>
              <option value="manager">Manager</option>
              <option value="admin">Admin</option>
            </select>
          </Field>
          <Field label="Status">
            <select
              className="select"
              value={filters.is_active ?? ''}
              onChange={(e) => setFilters({ ...filters, is_active: e.target.value || undefined })}
            >
              <option value="">All</option>
              <option value="true">Active</option>
              <option value="false">Deactivated</option>
            </select>
          </Field>
          <Field label="Search">
            <input
              className="input"
              type="search"
              value={filters.search ?? ''}
              onChange={(e) => setFilters({ ...filters, search: e.target.value || undefined })}
              placeholder="Name, email, employee no…"
            />
          </Field>
        </div>
      </Card>

      {teamQuery.isLoading ? (
        <PageLoading label="Loading the team…" />
      ) : teamQuery.isError ? (
        <PageError message={apiErrorMessage(teamQuery.error, 'Could not load the team.')} />
      ) : members.length === 0 ? (
        <Card>
          <EmptyState icon="👥" title="Nobody matches those filters" />
        </Card>
      ) : (
        <Card title={`${teamQuery.data?.count ?? 0} people`} flush>
          <div className="table-scroll">
            <table className="table table--stacked">
              <thead>
                <tr>
                  <th scope="col">Name</th>
                  <th scope="col">Role</th>
                  <th scope="col">Store</th>
                  <th scope="col">Last seen</th>
                  <th scope="col">
                    <span className="u-sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {members.map((member) => (
                  <tr key={member.id} style={{ opacity: member.is_active ? 1 : 0.55 }}>
                    <td data-label="Name">
                      {/* One wrapper so the stacked mobile layout treats the
                          name and email as a single value, not two columns. */}
                      <div>
                        <div style={{ fontWeight: 600 }}>{member.full_name}</div>
                        <div className="u-subtle" style={{ fontSize: 'var(--text-xs)' }}>
                          {member.email}
                          {member.id === user?.id && ' · you'}
                          {!member.is_active && ' · deactivated'}
                        </div>
                      </div>
                    </td>
                    <td data-label="Role">
                      <Badge tone={ROLE_TONE[member.role]}>{member.role}</Badge>
                    </td>
                    <td data-label="Store" style={{ minWidth: '190px' }}>
                      <select
                        className="select"
                        aria-label={`Store for ${member.full_name}`}
                        value={member.store?.slug ?? ''}
                        disabled={updateMutation.isPending}
                        onChange={(e) => assignStore(member, e.target.value)}
                      >
                        <option value="">— Not assigned —</option>
                        {storesQuery.data?.map((store) => (
                          <option key={store.slug} value={store.slug}>
                            {store.name}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="u-nowrap u-muted" data-label="Last seen">
                      {member.last_login ? formatDate(member.last_login) : 'Never'}
                    </td>
                    <td className="u-right">
                      <Button variant="ghost" size="sm" block onClick={() => setEditing(member)}>
                        Edit
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <MemberFormModal
        open={creating}
        mode="create"
        stores={storesQuery.data ?? []}
        onClose={() => setCreating(false)}
      />
      <MemberFormModal
        open={Boolean(editing)}
        mode="edit"
        member={editing ?? undefined}
        stores={storesQuery.data ?? []}
        onClose={() => setEditing(null)}
      />
    </div>
  )
}
