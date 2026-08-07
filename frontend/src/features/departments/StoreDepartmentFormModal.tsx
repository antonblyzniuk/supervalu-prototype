import { useEffect, useState, type FormEvent } from 'react'

import { Button } from '@/components/ui/Button'
import { Field } from '@/components/ui/Field'
import { Modal } from '@/components/ui/Modal'
import { useToast } from '@/components/ui/useToast'
import { useTeam } from '@/features/team/hooks'
import { apiErrorMessage } from '@/lib/apiClient'
import type { StoreDepartment } from '@/types/api'

import { useUpdateStoreDepartment } from './hooks'

interface StoreDepartmentFormModalProps {
  open: boolean
  branch: StoreDepartment
  onClose: () => void
}

interface FormState {
  manager_id: string
  notes: string
}

/** One branch of a department: its head of department and its notes. */
export function StoreDepartmentFormModal({
  open,
  branch,
  onClose,
}: StoreDepartmentFormModalProps) {
  const toast = useToast()
  const [form, setForm] = useState<FormState>({ manager_id: '', notes: '' })
  const [error, setError] = useState<string | null>(null)

  const updateMutation = useUpdateStoreDepartment()

  // The head of a branch has to work in that branch, so the picker is narrowed
  // to its store — the API refuses anyone else. Fetched in a single page (the
  // API caps page_size at 200) so nobody drops off the list.
  const teamQuery = useTeam({
    is_active: 'true',
    store__slug: branch.store.slug,
    page_size: '200',
  })

  useEffect(() => {
    if (!open) return
    setError(null)
    setForm({
      manager_id: branch.manager ? String(branch.manager.id) : '',
      notes: branch.notes,
    })
  }, [open, branch])

  const patch = (changes: Partial<FormState>) => setForm((current) => ({ ...current, ...changes }))

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)

    try {
      await updateMutation.mutateAsync({
        slug: branch.slug,
        manager_id: form.manager_id ? Number(form.manager_id) : null,
        notes: form.notes.trim(),
      })
      toast.push(`${branch.department.name} · ${branch.store.name} updated.`, 'success')
      onClose()
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not save. Check the fields and try again.'))
    }
  }

  return (
    <Modal
      open={open}
      title={`Edit ${branch.department.name} · ${branch.store.name}`}
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="store-department-form" loading={updateMutation.isPending}>
            Save changes
          </Button>
        </>
      }
    >
      <form id="store-department-form" className="u-stack-sm" onSubmit={handleSubmit} noValidate>
        {error && <div className="alert alert--error">{error}</div>}

        <Field
          label="Head of department"
          hint={`Who runs it in ${branch.store.name}. Only people at that store can be picked.`}
        >
          <select
            className="select"
            value={form.manager_id}
            onChange={(e) => patch({ manager_id: e.target.value })}
          >
            <option value="">— Nobody assigned —</option>
            {teamQuery.data?.results.map((member) => (
              <option key={member.id} value={member.id}>
                {member.full_name} · {member.role}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Notes" hint="Anything specific to this store. Shown on its page.">
          <textarea
            className="textarea"
            rows={3}
            value={form.notes}
            onChange={(e) => patch({ notes: e.target.value })}
          />
        </Field>
      </form>
    </Modal>
  )
}
