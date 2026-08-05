import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Field } from '@/components/ui/Field'
import { PageError, PageLoading } from '@/components/ui/PageState'
import { Tabs } from '@/components/ui/Tabs'
import { useToast } from '@/components/ui/useToast'
import { useAuth } from '@/features/auth/useAuth'
import { useStores } from '@/features/stores/hooks'
import { apiErrorMessage } from '@/lib/apiClient'

import { CategoryLineTable } from './components/CategoryLineTable'
import { ItemLineTable } from './components/ItemLineTable'
import { PhotoUpload } from './components/PhotoUpload'
import { SignaturePad } from './components/SignaturePad'
import {
  DOCKET_TYPES,
  DOCKET_TYPE_LABELS,
  draftFromDocket,
  draftToPayload,
  emptyDraft,
  isDocketType,
  validateDraft,
} from './draft'
import { formatMoney } from './format'
import { useCreateDocket, useDocket, useDocketMeta, useUpdateDocket } from './hooks'
import type { DocketDraft, DocketSignature, DocketType } from './types'

export function DocketFormPage() {
  const { id } = useParams<{ id: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const toast = useToast()
  const { user } = useAuth()

  const isEditing = Boolean(id)
  const metaQuery = useDocketMeta()
  const storesQuery = useStores()
  const docketQuery = useDocket(id)

  const requestedType = searchParams.get('type') ?? undefined
  const initialType: DocketType = isDocketType(requestedType) ? requestedType : 'ambient'

  const [draft, setDraft] = useState<DocketDraft | null>(null)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [formError, setFormError] = useState<string | null>(null)

  const createMutation = useCreateDocket()
  const updateMutation = useUpdateDocket(id ?? '')
  const saving = createMutation.isPending || updateMutation.isPending

  const defaultStore = user?.store?.slug ?? storesQuery.data?.[0]?.slug ?? ''

  // Seed the draft once the data it depends on has arrived.
  useEffect(() => {
    if (draft) return
    if (isEditing) {
      if (docketQuery.data) setDraft(draftFromDocket(docketQuery.data))
    } else if (defaultStore) {
      setDraft(emptyDraft(initialType, defaultStore))
    }
  }, [draft, isEditing, docketQuery.data, defaultStore, initialType])

  const typeMeta = useMemo(
    () => metaQuery.data?.types.find((entry) => entry.value === draft?.docket_type),
    [metaQuery.data, draft?.docket_type],
  )

  const runningTotal = useMemo(
    () => (draft?.lines ?? []).reduce((sum, line) => sum + (Number(line.total) || 0), 0),
    [draft?.lines],
  )

  if (metaQuery.isLoading || storesQuery.isLoading || (isEditing && docketQuery.isLoading)) {
    return <PageLoading label="Loading docket…" />
  }
  if (metaQuery.isError || storesQuery.isError) {
    return <PageError message="Could not load the docket form. Check your connection." />
  }
  if (isEditing && docketQuery.isError) {
    return <PageError message="That docket could not be found." />
  }
  if (!draft || !typeMeta) return <PageLoading />

  const stores = storesQuery.data ?? []
  // Staff file for their own store only; the API enforces the same rule.
  const canChooseStore = Boolean(user?.is_manager)
  const patch = (changes: Partial<DocketDraft>) => setDraft({ ...draft, ...changes })

  const changeType = (nextType: DocketType) => {
    // Switching type changes the whole column set, so restart from a clean sheet.
    setDraft(emptyDraft(nextType, draft.store))
    setErrors({})
  }

  const setSignature = (role: string, image: string | null) => {
    const others = draft.signatures.filter((signature) => signature.role !== role)
    const existing = draft.signatures.find((signature) => signature.role === role)
    patch({
      signatures: image
        ? [...others, { role, signed_name: existing?.signed_name ?? '', image }]
        : others,
    })
  }

  const setSignatureName = (role: string, signed_name: string) => {
    const existing = draft.signatures.find((signature) => signature.role === role)
    const others = draft.signatures.filter((signature) => signature.role !== role)
    const next: DocketSignature = existing
      ? { ...existing, signed_name }
      : { role, signed_name, image: '' }
    patch({ signatures: next.image ? [...others, next] : draft.signatures })
    if (role === 'manager') patch({ manager_name: signed_name })
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!draft || !typeMeta) return

    const found = validateDraft(draft, typeMeta)
    setErrors(found)
    setFormError(null)
    if (Object.keys(found).length) {
      setFormError('Check the highlighted fields and try again.')
      return
    }

    const payload = draftToPayload(draft, typeMeta)
    try {
      const saved = isEditing
        ? await updateMutation.mutateAsync(payload)
        : await createMutation.mutateAsync(payload)
      toast.push(
        `${DOCKET_TYPE_LABELS[saved.docket_type]} docket ${isEditing ? 'updated' : 'saved'} · ${saved.store_detail.name}`,
        'success',
      )
      navigate(`/dockets/${saved.id}`)
    } catch (error) {
      setFormError(apiErrorMessage(error, 'Could not save the docket.'))
    }
  }

  const isCategory = typeMeta.shape === 'categories'

  return (
    <form className="u-stack" onSubmit={handleSubmit} noValidate>
      <div className="page-head">
        <div>
          <h1 className="page-head__title">
            {isEditing ? 'Edit docket' : 'New docket'}
          </h1>
          <p className="page-head__sub">
            {isEditing
              ? `${DOCKET_TYPE_LABELS[draft.docket_type]} · ${draft.store}`
              : 'Pick the register, fill the rows, sign it off.'}
          </p>
        </div>
        <div className="page-head__actions">
          <Button variant="ghost" onClick={() => navigate(-1)}>
            Cancel
          </Button>
          <Button type="submit" loading={saving}>
            {isEditing ? 'Save changes' : 'Save docket'}
          </Button>
        </div>
      </div>

      {!isEditing && (
        <Tabs
          label="Docket type"
          value={draft.docket_type}
          onChange={changeType}
          options={DOCKET_TYPES.map((value) => ({ value, label: DOCKET_TYPE_LABELS[value] }))}
        />
      )}

      {formError && <div className="alert alert--error">{formError}</div>}

      <Card title={`${typeMeta.label} docket details`}>
        <div className="form-grid form-grid--2">
          <Field
            label="Store"
            required
            error={errors.store}
            hint={canChooseStore ? undefined : 'Your account is assigned to this store.'}
          >
            <select
              className="select"
              value={draft.store}
              disabled={!canChooseStore}
              onChange={(e) => patch({ store: e.target.value })}
            >
              {(canChooseStore ? stores : stores.filter((s) => s.slug === draft.store)).map(
                (store) => (
                  <option key={store.slug} value={store.slug}>
                    {store.name}
                  </option>
                ),
              )}
            </select>
          </Field>

          {draft.docket_type === 'transfer' && (
            <Field label="Receiving store" required error={errors.destination_store}>
              <select
                className="select"
                value={draft.destination_store ?? ''}
                onChange={(e) => patch({ destination_store: e.target.value || null })}
              >
                <option value="">Select store…</option>
                {stores
                  .filter((store) => store.slug !== draft.store)
                  .map((store) => (
                    <option key={store.slug} value={store.slug}>
                      {store.name}
                    </option>
                  ))}
              </select>
            </Field>
          )}

          {isCategory ? (
            <Field label="Week ending" required error={errors.week_ending}>
              <input
                className="input"
                type="date"
                value={draft.week_ending}
                onChange={(e) => patch({ week_ending: e.target.value })}
              />
            </Field>
          ) : (
            <Field label="Date" required error={errors.docket_date}>
              <input
                className="input"
                type="date"
                value={draft.docket_date}
                onChange={(e) => patch({ docket_date: e.target.value })}
              />
            </Field>
          )}

          <Field label="Reference no.">
            <input
              className="input"
              value={draft.reference}
              onChange={(e) => patch({ reference: e.target.value })}
              placeholder="e.g. 1871"
            />
          </Field>

          {!isCategory && (
            <>
              <Field label="Docket no.">
                <input
                  className="input"
                  value={draft.docket_number}
                  onChange={(e) => patch({ docket_number: e.target.value })}
                  placeholder="e.g. 0851"
                />
              </Field>
              <Field label="Department">
                <input
                  className="input"
                  value={draft.department}
                  onChange={(e) => patch({ department: e.target.value })}
                  placeholder="e.g. Deli"
                />
              </Field>
            </>
          )}

          {draft.docket_type === 'returns' && (
            <Field label="Supplier (returning to)" required error={errors.supplier}>
              <input
                className="input"
                value={draft.supplier}
                onChange={(e) => patch({ supplier: e.target.value })}
                placeholder="Supplier name"
              />
            </Field>
          )}

          {draft.docket_type === 'transfer' && (
            <Field label="Outgoing staff member">
              <input
                className="input"
                value={draft.outgoing_staff_name}
                onChange={(e) => patch({ outgoing_staff_name: e.target.value })}
                placeholder="Name"
              />
            </Field>
          )}
        </div>

        {draft.docket_type === 'returns' && (
          <div style={{ marginTop: 'var(--space-3)' }}>
            <Field label="Reason for return">
              <textarea
                className="textarea"
                value={draft.reason}
                onChange={(e) => patch({ reason: e.target.value })}
                placeholder="Describe why the goods are going back…"
              />
            </Field>
          </div>
        )}
      </Card>

      <Card
        title={isCategory ? 'Docket entries' : 'Goods'}
        actions={
          <span className="u-mono u-muted" style={{ fontSize: 'var(--text-sm)' }}>
            {formatMoney(runningTotal)}
          </span>
        }
      >
        {errors.lines && <div className="alert alert--error">{errors.lines}</div>}
        {isCategory ? (
          <CategoryLineTable
            columns={typeMeta.columns}
            lines={draft.lines}
            onChange={(lines) => patch({ lines })}
          />
        ) : (
          <ItemLineTable lines={draft.lines} onChange={(lines) => patch({ lines })} />
        )}
      </Card>

      <Card title="Signatures">
        <div className="form-grid form-grid--2">
          {typeMeta.signature_roles.map((role) => {
            const signature = draft.signatures.find((entry) => entry.role === role.value)
            return (
              <SignaturePad
                key={role.value}
                label={role.label}
                value={signature?.image ?? null}
                onChange={(image) => setSignature(role.value, image)}
                name={
                  role.value === 'manager'
                    ? draft.manager_name
                    : (signature?.signed_name ?? '')
                }
                onNameChange={(value) =>
                  role.value === 'manager'
                    ? patch({ manager_name: value })
                    : setSignatureName(role.value, value)
                }
              />
            )
          })}
        </div>
      </Card>

      <Card title="Photos">
        <PhotoUpload photos={draft.photos} onChange={(photos) => patch({ photos })} />
      </Card>

      <Card title="Notes">
        <textarea
          className="textarea"
          value={draft.notes}
          onChange={(e) => patch({ notes: e.target.value })}
          placeholder="Anything the office should know about this docket…"
          aria-label="Notes"
        />
      </Card>

      <div className="u-spread">
        <span className="u-muted">
          Docket total <strong className="u-mono">{formatMoney(runningTotal)}</strong>
        </span>
        <Button type="submit" size="lg" loading={saving}>
          {isEditing ? 'Save changes' : 'Save docket'}
        </Button>
      </div>
    </form>
  )
}
