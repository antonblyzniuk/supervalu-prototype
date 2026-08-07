import { Badge } from '@/components/ui/Badge'
import { useAuth } from '@/features/auth/useAuth'
import { ROLE_TONE } from '@/features/team/roles'
import type { DepartmentPerson } from '@/types/api'

interface StaffTableProps {
  members: DepartmentPerson[]
  /** On for the pooled group view, where people come from different branches. */
  showStore?: boolean
}

/** A department roster. Deactivated colleagues stay listed, dimmed and flagged. */
export function StaffTable({ members, showStore = false }: StaffTableProps) {
  const { user } = useAuth()

  return (
    <div className="table-scroll">
      <table className="table table--stacked">
        <thead>
          <tr>
            <th scope="col">Name</th>
            <th scope="col">Role</th>
            {showStore && <th scope="col">Store</th>}
            <th scope="col">Employee no.</th>
          </tr>
        </thead>
        <tbody>
          {members.map((member) => (
            <tr key={member.id} style={{ opacity: member.is_active ? 1 : 0.55 }}>
              <td data-label="Name">
                {/* One wrapper so the stacked mobile layout treats the name and
                    email as a single value, not two columns. */}
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
              {showStore && <td data-label="Store">{member.store?.name ?? '—'}</td>}
              <td className="u-mono" data-label="Employee no.">
                {member.employee_id || '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
