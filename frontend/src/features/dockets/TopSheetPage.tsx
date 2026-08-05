import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { Field } from '@/components/ui/Field'
import { PageError, PageLoading } from '@/components/ui/PageState'
import { Tabs } from '@/components/ui/Tabs'
import { useToast } from '@/components/ui/useToast'
import { useAuth } from '@/features/auth/useAuth'
import { useVisibleStores } from '@/features/stores/hooks'
import { apiErrorMessage } from '@/lib/apiClient'

import { downloadExport } from './api'
import { DOCKET_TYPES, DOCKET_TYPE_LABELS } from './draft'
import { formatAmount, formatDate, formatMoney, toISODate, weekLabel } from './format'
import { useDocketSummary, useDockets } from './hooks'
import type { DocketFilters, DocketType } from './types'

const ALL_STORES = '__all__'

export function TopSheetPage() {
  const navigate = useNavigate()
  const toast = useToast()
  const { user } = useAuth()
  const stores = useVisibleStores()
  // Only managers can look at the group; staff are pinned to their own store.
  const canSeeGroup = Boolean(user?.is_manager)

  const [weekAnchor, setWeekAnchor] = useState(() => toISODate(new Date()))
  const [storeSlug, setStoreSlug] = useState<string>(
    canSeeGroup ? ALL_STORES : (user?.store?.slug ?? ALL_STORES),
  )
  const [activeType, setActiveType] = useState<DocketType>('ambient')
  const [exporting, setExporting] = useState(false)

  const filters: DocketFilters = useMemo(
    () => ({
      week_of: weekAnchor,
      ...(storeSlug === ALL_STORES ? {} : { store: [storeSlug] }),
    }),
    [weekAnchor, storeSlug],
  )

  const summaryQuery = useDocketSummary(filters)
  const listQuery = useDockets({ ...filters, docket_type: [activeType] })

  const shiftWeek = (deltaDays: number) => {
    const date = new Date(`${weekAnchor}T00:00:00`)
    date.setDate(date.getDate() + deltaDays)
    setWeekAnchor(toISODate(date))
  }

  async function handleExport(output: 'json' | 'pdf') {
    setExporting(true)
    try {
      await downloadExport(filters, output)
      toast.push(`Week ${output.toUpperCase()} downloaded.`, 'success')
    } catch (error) {
      toast.push(apiErrorMessage(error, 'Export failed.'), 'error')
    } finally {
      setExporting(false)
    }
  }

  if (summaryQuery.isLoading) return <PageLoading label="Building the top sheet…" />
  if (summaryQuery.isError) {
    return (
      <PageError
        message={apiErrorMessage(summaryQuery.error, 'Could not load the top sheet.')}
        action={<Button onClick={() => summaryQuery.refetch()}>Retry</Button>}
      />
    )
  }

  const summary = summaryQuery.data
  const anchorDate = new Date(`${weekAnchor}T00:00:00`)
  const typeSummary = summary?.by_type.find((entry) => entry.docket_type === activeType)
  const scopeLabel =
    storeSlug === ALL_STORES
      ? 'All stores'
      : (stores.find((store) => store.slug === storeSlug)?.name ?? storeSlug)

  return (
    <div className="u-stack">
      <div className="page-head">
        <div>
          <h1 className="page-head__title">Weekly top sheet</h1>
          <p className="page-head__sub">
            {scopeLabel} · {weekLabel(anchorDate)}
          </p>
        </div>
        <div className="page-head__actions">
          <Button variant="ghost" onClick={() => navigate('/dockets')}>
            All dockets
          </Button>
          <Button variant="secondary" loading={exporting} onClick={() => handleExport('json')}>
            JSON
          </Button>
          <Button loading={exporting} onClick={() => handleExport('pdf')}>
            Download PDF
          </Button>
        </div>
      </div>

      <Card title="Period">
        <div className="form-grid">
          <Field
            label="Store"
            hint={canSeeGroup ? undefined : 'Your account covers this store.'}
          >
            <select
              className="select"
              value={storeSlug}
              disabled={!canSeeGroup}
              onChange={(event) => setStoreSlug(event.target.value)}
            >
              {canSeeGroup && <option value={ALL_STORES}>All stores (group)</option>}
              {stores.map((store) => (
                <option key={store.slug} value={store.slug}>
                  {store.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Week containing" hint="Trading week runs Sunday to Saturday.">
            <input
              className="input"
              type="date"
              value={weekAnchor}
              onChange={(event) => setWeekAnchor(event.target.value || toISODate(new Date()))}
            />
          </Field>
          <div className="u-row" style={{ alignItems: 'flex-end' }}>
            <Button variant="ghost" onClick={() => shiftWeek(-7)}>
              ← Previous
            </Button>
            <Button variant="ghost" onClick={() => setWeekAnchor(toISODate(new Date()))}>
              This week
            </Button>
            <Button variant="ghost" onClick={() => shiftWeek(7)}>
              Next →
            </Button>
          </div>
        </div>
      </Card>

      <div className="stat-grid">
        <div className="stat stat--brand">
          <div className="stat__label">Week total</div>
          <div className="stat__value">{formatMoney(summary?.grand_total)}</div>
          <div className="stat__meta">
            {summary?.docket_count ?? 0} docket{summary?.docket_count === 1 ? '' : 's'}
          </div>
        </div>
        {summary?.by_type.map((bucket) => (
          <div className="stat" key={bucket.docket_type}>
            <div className="stat__label">{bucket.label}</div>
            <div className="stat__value">{formatMoney(bucket.total)}</div>
            <div className="stat__meta">
              {bucket.docket_count} docket{bucket.docket_count === 1 ? '' : 's'} ·{' '}
              {bucket.line_count} rows
            </div>
          </div>
        ))}
      </div>

      {storeSlug === ALL_STORES && (summary?.by_store.length ?? 0) > 0 && (
        <Card title="By store" flush>
          <div className="table-scroll">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Store</th>
                  <th scope="col" className="u-right">
                    Dockets
                  </th>
                  {DOCKET_TYPES.map((type) => (
                    <th scope="col" key={type} className="u-right">
                      {DOCKET_TYPE_LABELS[type]}
                    </th>
                  ))}
                  <th scope="col" className="u-right">
                    Total
                  </th>
                </tr>
              </thead>
              <tbody>
                {summary?.by_store.map((entry) => (
                  <tr key={entry.store.slug}>
                    <td>{entry.store.name}</td>
                    <td className="u-right u-num">{entry.docket_count}</td>
                    {DOCKET_TYPES.map((type) => (
                      <td key={type} className="u-right u-num">
                        {formatMoney(entry.by_type[type])}
                      </td>
                    ))}
                    <td className="u-right u-num" style={{ fontWeight: 700 }}>
                      {formatMoney(entry.total)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td>All stores</td>
                  <td className="u-right u-num">{summary?.docket_count}</td>
                  <td colSpan={DOCKET_TYPES.length} />
                  <td className="u-right u-num">{formatMoney(summary?.grand_total)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </Card>
      )}

      <Tabs
        label="Register"
        value={activeType}
        onChange={setActiveType}
        options={DOCKET_TYPES.map((value) => ({ value, label: DOCKET_TYPE_LABELS[value] }))}
      />

      {typeSummary && typeSummary.columns.length > 0 && typeSummary.docket_count > 0 && (
        <Card title={`${typeSummary.label} running totals`} flush>
          <div className="table-scroll">
            <table className="table">
              <thead>
                <tr>
                  {typeSummary.columns.map((column) => (
                    <th scope="col" key={column.key} className="u-right">
                      {column.label}
                    </th>
                  ))}
                  <th scope="col" className="u-right">
                    Week total
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  {typeSummary.columns.map((column) => (
                    <td key={column.key} className="u-right u-num">
                      {formatAmount(typeSummary.category_totals[column.key]) || '—'}
                    </td>
                  ))}
                  <td className="u-right u-num" style={{ fontWeight: 700 }}>
                    {formatMoney(typeSummary.total)}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Card
        title={`${DOCKET_TYPE_LABELS[activeType]} dockets this week`}
        flush
        actions={
          <Button size="sm" onClick={() => navigate(`/dockets/new?type=${activeType}`)}>
            Add
          </Button>
        }
      >
        {listQuery.isLoading ? (
          <PageLoading />
        ) : (listQuery.data?.results.length ?? 0) === 0 ? (
          <EmptyState
            icon="🗓"
            title={`No ${DOCKET_TYPE_LABELS[activeType].toLowerCase()} dockets this week`}
            description={`Nothing filed for ${scopeLabel} in ${weekLabel(anchorDate)}.`}
          />
        ) : (
          <div className="table-scroll">
            <table className="table table--rows-clickable">
              <thead>
                <tr>
                  <th scope="col">Date</th>
                  <th scope="col">Store</th>
                  <th scope="col">Reference</th>
                  <th scope="col">Supplier / route</th>
                  <th scope="col" className="u-right">
                    Rows
                  </th>
                  <th scope="col" className="u-right">
                    Total
                  </th>
                </tr>
              </thead>
              <tbody>
                {listQuery.data?.results.map((docket) => (
                  <tr key={docket.id} onClick={() => navigate(`/dockets/${docket.id}`)}>
                    <td className="u-nowrap">{formatDate(docket.effective_date)}</td>
                    <td className="u-nowrap">
                      {docket.store_detail.name}
                      {docket.destination_store_detail && (
                        <span className="u-subtle"> → {docket.destination_store_detail.name}</span>
                      )}
                    </td>
                    <td className="u-mono">{docket.reference || docket.docket_number || '—'}</td>
                    <td>{docket.supplier || docket.manager_name || '—'}</td>
                    <td className="u-right u-num">{docket.line_count}</td>
                    <td className="u-right u-num" style={{ fontWeight: 700 }}>
                      {formatMoney(docket.total)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <p className="u-subtle" style={{ fontSize: 'var(--text-xs)' }}>
        <Badge>PDF</Badge> The download carries this exact scope — store, week and all four
        registers — with signatures and photos embedded.
      </p>
    </div>
  )
}
