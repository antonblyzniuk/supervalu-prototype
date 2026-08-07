import { useEffect, useState, type FormEvent } from 'react'

import { Button } from '@/components/ui/Button'
import { Field } from '@/components/ui/Field'
import { Modal } from '@/components/ui/Modal'
import { useToast } from '@/components/ui/useToast'
import { useAuth } from '@/features/auth/useAuth'
import { useStoreDepartments } from '@/features/departments/hooks'
import { apiErrorMessage } from '@/lib/apiClient'
import type { Store, UserRole } from '@/types/api'

import { useCreateTeamMember, useSetTeamPassword, useUpdateTeamMember } from './hooks'
import type { TeamMember } from './types'

interface MemberFormModalProps {
  open: boolean
  mode: 'create' | 'edit'
  member?: TeamMember
  stores: Store[]
  onClose: () => void
}

interface FormState {
  hourly_rate: string
  email: string
  first_name: string
  last_name: string
  role: UserRole
  employee_id: string
  phone: string
  store_slug: string
  department_slug: string
  is_active: boolean
  password: string
}

const EMPTY: FormState = {
  hourly_rate: '',
  email: '',
  first_name: '',
  last_name: '',
  role: 'staff',
  employee_id: '',
  phone: '',
  store_slug: '',
  department_slug: '',
  is_active: true,
  password: '',
}

export function MemberFormModal({ open, mode, member, stores, onClose }: MemberFormModalProps) {
  const toast = useToast()
  const { user } = useAuth()
  const [form, setForm] = useState<FormState>(EMPTY)
  const [error, setError] = useState<string | null>(null)

  // A department belongs to one store, so the picker follows the store field
  // rather than the colleague's saved store — and it only lists the departments
  // that store actually runs.
  const branches = useStoreDepartments().data ?? []
  const departments = branches.filter((branch) => branch.store.slug === form.store_slug)

  const createMutation = useCreateTeamMember()
  const updateMutation = useUpdateTeamMember()
  const passwordMutation = useSetTeamPassword()
  const saving = createMutation.isPending || updateMutation.isPending

  useEffect(() => {
    if (!open) return
    setError(null)
    setForm(
      mode === 'edit' && member
        ? {
            email: member.email,
            first_name: member.first_name,
            last_name: member.last_name,
            role: member.role,
            employee_id: member.employee_id,
            phone: member.phone,
            store_slug: member.store?.slug ?? '',
            department_slug: member.department?.slug ?? '',
            hourly_rate: member.hourly_rate ?? '',
            is_active: member.is_active,
            password: '',
          }
        : EMPTY,
    )
  }, [open, mode, member])

  /** Moving them to another store invalidates the department they were in. */
  function changeStore(storeSlug: string) {
    const stillValid = branches.some(
      (branch) => branch.slug === form.department_slug && branch.store.slug === storeSlug,
    )
    patch({ store_slug: storeSlug, department_slug: stillValid ? form.department_slug : '' })
  }

  const isSelf = mode === 'edit' && member?.id === user?.id
  const canGrantAdmin = user?.role === 'admin'
  const canSetPay = user?.role === 'admin'
  const patch = (changes: Partial<FormState>) => setForm((current) => ({ ...current, ...changes }))

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)

    try {
      if (mode === 'create') {
        await createMutation.mutateAsync({
          email: form.email.trim(),
          first_name: form.first_name,
          last_name: form.last_name,
          role: form.role,
          employee_id: form.employee_id,
          phone: form.phone,
          store_slug: form.store_slug || null,
          department_slug: form.department_slug,
          // Pay is an admin's field; the API refuses it from a manager, so it
          // is only ever sent when one is actually filling the form in.
          ...(canSetPay ? { hourly_rate: form.hourly_rate || null } : {}),
          password: form.password,
        })
        toast.push(`${form.email.trim()} added.`, 'success')
      } else if (member) {
        await updateMutation.mutateAsync({
          id: member.id,
          first_name: form.first_name,
          last_name: form.last_name,
          role: form.role,
          employee_id: form.employee_id,
          phone: form.phone,
          store_slug: form.store_slug || null,
          // Omitted when blank: the API refuses to clear a department, and an
          // account from before departments existed may not have one yet.
          ...(form.department_slug ? { department_slug: form.department_slug } : {}),
          ...(canSetPay ? { hourly_rate: form.hourly_rate || null } : {}),
          is_active: form.is_active,
        })
        if (form.password) {
          await passwordMutation.mutateAsync({ id: member.id, password: form.password })
          toast.push('Details and password updated.', 'success')
        } else {
          toast.push('Details updated.', 'success')
        }
      }
      onClose()
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not save. Check the fields and try again.'))
    }
  }

  return (
    <Modal
      open={open}
      title={mode === 'create' ? 'Add colleague' : `Edit ${member?.full_name ?? ''}`}
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="member-form" loading={saving}>
            {mode === 'create' ? 'Add colleague' : 'Save changes'}
          </Button>
        </>
      }
    >
      <form id="member-form" className="u-stack-sm" onSubmit={handleSubmit} noValidate>
        {error && <div className="alert alert--error">{error}</div>}

        {mode === 'create' && (
          <Field label="Work email" required hint="This is what they sign in with.">
            <input
              className="input"
              type="email"
              autoCapitalize="none"
              spellCheck={false}
              value={form.email}
              onChange={(e) => patch({ email: e.target.value })}
              required
            />
          </Field>
        )}

        <div className="form-grid form-grid--2">
          <Field label="First name">
            <input
              className="input"
              value={form.first_name}
              onChange={(e) => patch({ first_name: e.target.value })}
            />
          </Field>
          <Field label="Last name">
            <input
              className="input"
              value={form.last_name}
              onChange={(e) => patch({ last_name: e.target.value })}
            />
          </Field>
        </div>

        <div className="form-grid form-grid--2">
          <Field
            label="Store"
            hint={
              form.role === 'staff'
                ? 'Staff only see dockets for this store.'
                : 'Managers see every store; this is their home branch.'
            }
            required={mode === 'create'}
          >
            <select
              className="select"
              value={form.store_slug}
              onChange={(e) => changeStore(e.target.value)}
            >
              <option value="">— Not assigned —</option>
              {stores.map((store) => (
                <option key={store.slug} value={store.slug}>
                  {store.name}
                </option>
              ))}
            </select>
          </Field>

          <Field
            label="Role"
            hint={isSelf ? 'You cannot change your own role.' : undefined}
          >
            <select
              className="select"
              value={form.role}
              disabled={isSelf}
              onChange={(e) => patch({ role: e.target.value as UserRole })}
            >
              <option value="staff">Staff — own store only</option>
              <option value="manager">Manager — all stores</option>
              {(canGrantAdmin || form.role === 'admin') && (
                <option value="admin" disabled={!canGrantAdmin}>
                  Admin — all stores and settings
                </option>
              )}
            </select>
          </Field>
        </div>

        <Field
          label="Department"
          required={mode === 'create'}
          hint={
            form.store_slug
              ? 'Where they work in that store. Everyone belongs to one.'
              : 'Pick a store first — departments are per store.'
          }
        >
          <select
            className="select"
            value={form.department_slug}
            disabled={!form.store_slug}
            onChange={(e) => patch({ department_slug: e.target.value })}
            required={mode === 'create'}
          >
            <option value="">— Choose a department —</option>
            {departments.map((branch) => (
              <option key={branch.slug} value={branch.slug}>
                {branch.department.name}
              </option>
            ))}
          </select>
        </Field>

        {canSetPay && (
          <Field
            label="Hourly rate"
            hint="Euro per hour, used to price the roster. Leave blank for the minimum wage."
          >
            <input
              className="input"
              type="number"
              inputMode="decimal"
              step="0.01"
              min="0"
              placeholder="Minimum wage"
              value={form.hourly_rate}
              onChange={(e) => patch({ hourly_rate: e.target.value })}
            />
          </Field>
        )}

        <div className="form-grid form-grid--2">
          <Field label="Employee no.">
            <input
              className="input"
              value={form.employee_id}
              onChange={(e) => patch({ employee_id: e.target.value })}
            />
          </Field>
          <Field label="Phone">
            <input
              className="input"
              type="tel"
              value={form.phone}
              onChange={(e) => patch({ phone: e.target.value })}
            />
          </Field>
        </div>

        <Field
          label={mode === 'create' ? 'Starting password' : 'Reset password'}
          required={mode === 'create'}
          hint={
            mode === 'create'
              ? 'Hand this to them in person; they should change it after signing in.'
              : 'Leave blank to keep their current password.'
          }
        >
          <input
            className="input"
            type="text"
            autoComplete="off"
            value={form.password}
            onChange={(e) => patch({ password: e.target.value })}
            required={mode === 'create'}
          />
        </Field>

        {mode === 'edit' && (
          <Field
            label="Account status"
            hint={isSelf ? 'You cannot deactivate your own account.' : undefined}
          >
            <select
              className="select"
              value={form.is_active ? 'true' : 'false'}
              disabled={isSelf}
              onChange={(e) => patch({ is_active: e.target.value === 'true' })}
            >
              <option value="true">Active — can sign in</option>
              <option value="false">Deactivated — cannot sign in</option>
            </select>
          </Field>
        )}
      </form>
    </Modal>
  )
}
