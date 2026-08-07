import { useEffect, useMemo, useState, type FormEvent } from 'react'

import { Button } from '@/components/ui/Button'
import { Field } from '@/components/ui/Field'
import { Modal } from '@/components/ui/Modal'
import { useToast } from '@/components/ui/useToast'
import { useStores } from '@/features/stores/hooks'
import { apiErrorMessage } from '@/lib/apiClient'
import type { Department } from '@/types/api'

import { useCreateDepartment, useUpdateDepartment } from './hooks'

interface DepartmentFormModalProps {
  open: boolean
  mode: 'create' | 'edit'
  department?: Department
  onClose: () => void
  /** Create only — lets the list page jump to whatever was just made. */
  onCreated?: (department: Department) => void
}

interface FormState {
  name: string
  code: string
  description: string
  is_active: boolean
  /** Create only — which stores run it. Empty means every store. */
  store_slugs: string[]
}

const EMPTY: FormState = {
  name: '',
  code: '',
  description: '',
  is_active: true,
  store_slugs: [],
}

/**
 * The department kind. Heads of department and per-store status live on the
 * branch instead — see `StoreDepartmentFormModal`.
 */
export function DepartmentFormModal({
  open,
  mode,
  department,
  onClose,
  onCreated,
}: DepartmentFormModalProps) {
  const toast = useToast()
  const [form, setForm] = useState<FormState>(EMPTY)
  const [error, setError] = useState<string | null>(null)

  const storesQuery = useStores()
  const stores = useMemo(() => storesQuery.data ?? [], [storesQuery.data])
  // Every store ticked by default: that is the usual case, and the identity has
  // to be stable or resetting the form would fight the user's own un-ticking.
  const storeSlugs = useMemo(() => stores.map((store) => store.slug), [stores])

  const createMutation = useCreateDepartment()
  const updateMutation = useUpdateDepartment()
  const saving = createMutation.isPending || updateMutation.isPending

  useEffect(() => {
    if (!open) return
    setError(null)
    setForm(
      mode === 'edit' && department
        ? {
            name: department.name,
            code: department.code,
            description: department.description,
            is_active: department.is_active,
            store_slugs: [],
          }
        : { ...EMPTY, store_slugs: storeSlugs },
    )
  }, [open, mode, department, storeSlugs])

  const patch = (changes: Partial<FormState>) => setForm((current) => ({ ...current, ...changes }))

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)

    const payload = {
      name: form.name.trim(),
      code: form.code.trim(),
      description: form.description.trim(),
    }

    if (mode === 'create' && form.store_slugs.length === 0) {
      setError('Pick at least one store — a department nobody can be assigned to is no use.')
      return
    }

    try {
      if (mode === 'create') {
        const created = await createMutation.mutateAsync({
          ...payload,
          store_slugs: form.store_slugs,
        })
        toast.push(
          `${created.name} created in ${created.store_count} ${created.store_count === 1 ? 'store' : 'stores'}.`,
          'success',
        )
        onCreated?.(created)
      } else if (department) {
        await updateMutation.mutateAsync({
          slug: department.slug,
          ...payload,
          is_active: form.is_active,
        })
        toast.push('Department updated.', 'success')
      }
      onClose()
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not save. Check the fields and try again.'))
    }
  }

  return (
    <Modal
      open={open}
      title={mode === 'create' ? 'New department' : `Edit ${department?.name ?? ''}`}
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="department-form" loading={saving}>
            {mode === 'create' ? 'Create department' : 'Save changes'}
          </Button>
        </>
      }
    >
      <form id="department-form" className="u-stack-sm" onSubmit={handleSubmit} noValidate>
        {error && <div className="alert alert--error">{error}</div>}


        <div className="form-grid form-grid--2">
          <Field label="Name" required>
            <input
              className="input"
              value={form.name}
              onChange={(e) => patch({ name: e.target.value })}
              required
            />
          </Field>
          <Field label="Code" hint="Optional short code used on paperwork.">
            <input
              className="input"
              value={form.code}
              maxLength={16}
              onChange={(e) => patch({ code: e.target.value })}
            />
          </Field>
        </div>

        <Field label="Description" hint="What this department covers. Shown on its page.">
          <textarea
            className="textarea"
            rows={3}
            value={form.description}
            onChange={(e) => patch({ description: e.target.value })}
          />
        </Field>

        {mode === 'create' && (
          /* A checkbox group is not one labelable control, so it gets a plain
             heading rather than a `Field` — each box carries its own label. */
          <fieldset className="field">
            <legend className="field__label">
              Stores that run it
              <span className="field__required" aria-hidden="true">
                *
              </span>
            </legend>
            <div className="check-grid">
              {stores.map((store) => (
                <label className="check" key={store.slug}>
                  <input
                    type="checkbox"
                    checked={form.store_slugs.includes(store.slug)}
                    onChange={(e) =>
                      patch({
                        store_slugs: e.target.checked
                          ? [...form.store_slugs, store.slug]
                          : form.store_slugs.filter((slug) => slug !== store.slug),
                      })
                    }
                  />
                  <span>{store.name}</span>
                </label>
              ))}
            </div>
            <span className="field__hint">
              Not every store runs every department. You can add and remove stores later.
            </span>
          </fieldset>
        )}

        {mode === 'edit' && (
          <Field
            label="Status"
            hint="Archiving it takes it out of every store's pickers. Staff already in it stay."
          >
            <select
              className="select"
              value={form.is_active ? 'true' : 'false'}
              onChange={(e) => patch({ is_active: e.target.value === 'true' })}
            >
              <option value="true">Active</option>
              <option value="false">Archived</option>
            </select>
          </Field>
        )}
      </form>
    </Modal>
  )
}
