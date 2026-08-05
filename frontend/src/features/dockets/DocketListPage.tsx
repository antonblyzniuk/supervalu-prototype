import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { PageError, PageLoading } from '@/components/ui/PageState'
import { useToast } from '@/components/ui/useToast'
import { useAuth } from '@/features/auth/useAuth'
import { useVisibleStores } from '@/features/stores/hooks'
import { apiErrorMessage } from '@/lib/apiClient'

import { downloadExport } from './api'
import { DocketFilterBar } from './components/DocketFilterBar'
import { DOCKET_TYPE_LABELS } from './draft'
import { formatDate, formatMoney } from './format'
import { useDockets } from './hooks'
import type { DocketFilters } from './types'

const PAGE_SIZE = 25

export function DocketListPage() {
  const navigate = useNavigate()
  const toast = useToast()
  const { user } = useAuth()
  const stores = useVisibleStores()

  const [filters, setFilters] = useState<DocketFilters>({ page: 1 })
  const [exporting, setExporting] = useState(false)

  const docketsQuery = useDockets(filters)

  async function handleExport(output: 'json' | 'pdf') {
    setExporting(true)
    try {
      const { page: _page, ...exportFilters } = filters
      await downloadExport(exportFilters, output)
      toast.push(`${output.toUpperCase()} export downloaded.`, 'success')
    } catch (error) {
      toast.push(apiErrorMessage(error, 'Export failed.'), 'error')
    } finally {
      setExporting(false)
    }
  }

  const page = filters.page ?? 1
  const total = docketsQuery.data?.count ?? 0
  const lastPage = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="u-stack">
      <div className="page-head">
        <div>
          <h1 className="page-head__title">Dockets</h1>
          <p className="page-head__sub">
            {user?.is_manager
              ? 'Every register across Balbriggan, Skerries and Palmerstown.'
              : `Every register for ${user?.store?.name ?? 'your store'}, plus transfers coming in.`}
          </p>
        </div>
        <div className="page-head__actions">
          <Button variant="secondary" onClick={() => navigate('/dockets/top-sheet')}>
            Top sheet
          </Button>
          <Button onClick={() => navigate('/dockets/new')}>New docket</Button>
        </div>
      </div>

      <Card title="Filters">
        <DocketFilterBar
          filters={filters}
          stores={stores}
          onChange={setFilters}
          busy={exporting}
          onExport={handleExport}
        />
      </Card>

      {docketsQuery.isLoading ? (
        <PageLoading label="Loading dockets…" />
      ) : docketsQuery.isError ? (
        <PageError
          message={apiErrorMessage(docketsQuery.error, 'Could not load dockets.')}
          action={<Button onClick={() => docketsQuery.refetch()}>Retry</Button>}
        />
      ) : total === 0 ? (
        <Card>
          <EmptyState
            title="No dockets match"
            description="Adjust the filters, or file the first docket for this period."
            action={<Button onClick={() => navigate('/dockets/new')}>New docket</Button>}
          />
        </Card>
      ) : (
        <Card
          title={`${total} docket${total === 1 ? '' : 's'}`}
          flush
          footer={
            lastPage > 1 && (
              <div className="u-spread">
                <span className="u-muted" style={{ fontSize: 'var(--text-sm)' }}>
                  Page {page} of {lastPage}
                </span>
                <div className="u-row">
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() => setFilters({ ...filters, page: page - 1 })}
                  >
                    Previous
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={page >= lastPage}
                    onClick={() => setFilters({ ...filters, page: page + 1 })}
                  >
                    Next
                  </Button>
                </div>
              </div>
            )
          }
        >
          <div className="table-scroll">
            <table className="table table--rows-clickable table--stacked">
              <thead>
                <tr>
                  <th scope="col">Type</th>
                  <th scope="col">Store</th>
                  <th scope="col">Date</th>
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
                {docketsQuery.data?.results.map((docket) => (
                  <tr
                    key={docket.id}
                    onClick={() => navigate(`/dockets/${docket.id}`)}
                    tabIndex={0}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') navigate(`/dockets/${docket.id}`)
                    }}
                  >
                    <td data-label="Type">
                      <Badge tone={docket.docket_type}>
                        {DOCKET_TYPE_LABELS[docket.docket_type]}
                      </Badge>
                    </td>
                    <td className="u-nowrap" data-label="Store">{docket.store_detail.name}</td>
                    <td className="u-nowrap" data-label="Date">{formatDate(docket.effective_date)}</td>
                    <td className="u-mono" data-label="Reference">
                      {docket.reference || docket.docket_number || '—'}
                    </td>
                    <td data-label="Supplier / route">
                      {docket.destination_store_detail
                        ? `${docket.store_detail.name} → ${docket.destination_store_detail.name}`
                        : docket.supplier || docket.manager_name || '—'}
                      {docket.photo_count > 0 && (
                        <span className="u-subtle"> · 📷 {docket.photo_count}</span>
                      )}
                    </td>
                    <td className="u-right u-num" data-label="Rows">{docket.line_count}</td>
                    <td className="u-right u-num" data-label="Total" style={{ fontWeight: 700 }}>
                      {formatMoney(docket.total)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}
