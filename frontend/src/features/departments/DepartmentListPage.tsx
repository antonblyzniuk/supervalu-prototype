import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { Field } from '@/components/ui/Field'
import { PageError, PageLoading } from '@/components/ui/PageState'
import { useAuth } from '@/features/auth/useAuth'
import { apiErrorMessage } from '@/lib/apiClient'

import { DepartmentFormModal } from './DepartmentFormModal'
import { useDepartments } from './hooks'
import type { DepartmentFilters } from './types'

/**
 * Department kinds, pooled across the group. Manager/admin only — a staff user
 * is routed to their own branch instead (see `DepartmentsIndex`).
 */
export function DepartmentListPage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'

  const [filters, setFilters] = useState<DepartmentFilters>({})
  const [creating, setCreating] = useState(false)

  const departmentsQuery = useDepartments()

  // The list is small and unpaginated, so filtering client-side keeps typing
  // instant and saves a request per keystroke.
  const departments = useMemo(() => {
    const term = filters.search?.trim().toLowerCase() ?? ''
    return (departmentsQuery.data ?? []).filter((department) => {
      if (filters.is_active && String(department.is_active) !== filters.is_active) return false
      if (!term) return true
      return [department.name, department.code, department.description].some((value) =>
        value.toLowerCase().includes(term),
      )
    })
  }, [departmentsQuery.data, filters])

  const totalPeople = departments.reduce((sum, department) => sum + department.member_count, 0)

  return (
    <div className="u-stack">
      <div className="page-head">
        <div>
          <h1 className="page-head__title">Departments</h1>
          <p className="page-head__sub">
            Every department runs in each store. Open one for the group picture, or a store for
            its own roster.
          </p>
        </div>
        {isAdmin && (
          <div className="page-head__actions">
            <Button onClick={() => setCreating(true)}>New department</Button>
          </div>
        )}
      </div>

      <Card title="Filters">
        <div className="form-grid form-grid--2">
          <Field label="Search">
            <input
              className="input"
              type="search"
              value={filters.search ?? ''}
              onChange={(e) => setFilters({ ...filters, search: e.target.value || undefined })}
              placeholder="Name, code…"
            />
          </Field>
          <Field label="Status">
            <select
              className="select"
              value={filters.is_active ?? ''}
              onChange={(e) => setFilters({ ...filters, is_active: e.target.value || undefined })}
            >
              <option value="">All</option>
              <option value="true">Active</option>
              <option value="false">Archived</option>
            </select>
          </Field>
        </div>
      </Card>

      {departmentsQuery.isLoading ? (
        <PageLoading label="Loading departments…" />
      ) : departmentsQuery.isError ? (
        <PageError
          message={apiErrorMessage(departmentsQuery.error, 'Could not load the departments.')}
        />
      ) : departments.length === 0 ? (
        <Card>
          <EmptyState
            icon="🏷️"
            title="No departments match"
            description={
              isAdmin
                ? 'Change the filters, or create one.'
                : 'Change the filters, or ask an admin to create one.'
            }
            action={
              isAdmin ? <Button onClick={() => setCreating(true)}>New department</Button> : undefined
            }
          />
        </Card>
      ) : (
        <Card
          title={`${departments.length} department${departments.length === 1 ? '' : 's'} · ${totalPeople} ${totalPeople === 1 ? 'person' : 'people'} across the group`}
          flush
        >
          <div className="table-scroll">
            <table className="table table--rows-clickable table--stacked">
              <thead>
                <tr>
                  <th scope="col">Department</th>
                  <th scope="col">Code</th>
                  <th scope="col" className="u-right">
                    Stores
                  </th>
                  <th scope="col" className="u-right">
                    People
                  </th>
                  <th scope="col">Status</th>
                </tr>
              </thead>
              <tbody>
                {departments.map((department) => (
                  <tr
                    key={department.slug}
                    style={{ opacity: department.is_active ? 1 : 0.55 }}
                    onClick={() => navigate(`/departments/${department.slug}`)}
                    tabIndex={0}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') navigate(`/departments/${department.slug}`)
                    }}
                  >
                    <td data-label="Department">
                      <div>
                        <div style={{ fontWeight: 600 }}>{department.name}</div>
                        {department.description && (
                          <div className="u-subtle" style={{ fontSize: 'var(--text-xs)' }}>
                            {department.description}
                          </div>
                        )}
                      </div>
                    </td>
                    <td className="u-mono" data-label="Code">
                      {department.code || '—'}
                    </td>
                    <td className="u-right u-num" data-label="Stores">
                      {department.store_count}
                    </td>
                    <td className="u-right u-num" data-label="People">
                      {department.member_count}
                    </td>
                    <td data-label="Status">
                      {department.is_active ? (
                        <Badge tone="ambient">Active</Badge>
                      ) : (
                        <Badge>Archived</Badge>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Admin-only: the form writes, which the API gates. */}
      {isAdmin && (
        <DepartmentFormModal
          open={creating}
          mode="create"
          onClose={() => setCreating(false)}
          onCreated={(department) => navigate(`/departments/${department.slug}`)}
        />
      )}
    </div>
  )
}
