import { Button } from '@/components/ui/Button'
import { Field } from '@/components/ui/Field'
import type { Store } from '@/types/api'

import { DOCKET_TYPES, DOCKET_TYPE_LABELS } from '../draft'
import type { DocketFilters, DocketType } from '../types'

interface DocketFilterBarProps {
  filters: DocketFilters
  stores: Store[]
  onChange: (filters: DocketFilters) => void
  busy?: boolean
  onExport?: (output: 'json' | 'pdf') => void
}

const ALL = '__all__'

export function DocketFilterBar({
  filters,
  stores,
  onChange,
  busy,
  onExport,
}: DocketFilterBarProps) {
  const selectedStore = filters.store?.[0] ?? ALL
  const selectedType = filters.docket_type?.[0] ?? ALL

  const set = (patch: Partial<DocketFilters>) => onChange({ ...filters, ...patch, page: 1 })
  const isFiltered =
    Boolean(filters.store?.length) ||
    Boolean(filters.docket_type?.length) ||
    Boolean(filters.date_from || filters.date_to || filters.q)

  return (
    <div className="u-stack-sm">
      <div className="form-grid">
        {/* With one visible store there is nothing to choose — show it, locked,
            rather than offering an "All stores" that means the same thing. */}
        <Field
          label="Store"
          hint={stores.length === 1 ? 'Your account covers this store.' : undefined}
        >
          <select
            className="select"
            value={stores.length === 1 ? stores[0]!.slug : selectedStore}
            disabled={stores.length <= 1}
            onChange={(e) => set({ store: e.target.value === ALL ? undefined : [e.target.value] })}
          >
            {stores.length !== 1 && <option value={ALL}>All stores</option>}
            {stores.map((store) => (
              <option key={store.slug} value={store.slug}>
                {store.name}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Docket type">
          <select
            className="select"
            value={selectedType}
            onChange={(e) =>
              set({
                docket_type: e.target.value === ALL ? undefined : [e.target.value as DocketType],
              })
            }
          >
            <option value={ALL}>All types</option>
            {DOCKET_TYPES.map((type) => (
              <option key={type} value={type}>
                {DOCKET_TYPE_LABELS[type]}
              </option>
            ))}
          </select>
        </Field>

        <Field label="From">
          <input
            className="input"
            type="date"
            value={filters.date_from ?? ''}
            onChange={(e) => set({ date_from: e.target.value || undefined })}
          />
        </Field>

        <Field label="To">
          <input
            className="input"
            type="date"
            value={filters.date_to ?? ''}
            onChange={(e) => set({ date_to: e.target.value || undefined })}
          />
        </Field>

        <Field label="Search">
          <input
            className="input"
            type="search"
            value={filters.q ?? ''}
            onChange={(e) => set({ q: e.target.value || undefined })}
            placeholder="Reference, supplier, manager…"
          />
        </Field>
      </div>

      <div className="u-spread">
        <div>
          {isFiltered && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onChange({ ordering: filters.ordering, page: 1 })}
            >
              Clear filters
            </Button>
          )}
        </div>
        {onExport && (
          <div className="u-row">
            <span className="u-subtle" style={{ fontSize: 'var(--text-xs)' }}>
              Export what you see
            </span>
            <Button variant="secondary" size="sm" loading={busy} onClick={() => onExport('json')}>
              JSON
            </Button>
            <Button variant="secondary" size="sm" loading={busy} onClick={() => onExport('pdf')}>
              PDF
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
