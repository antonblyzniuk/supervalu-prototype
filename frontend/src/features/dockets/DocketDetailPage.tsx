import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { Modal } from '@/components/ui/Modal'
import { PageError, PageLoading } from '@/components/ui/PageState'
import { useToast } from '@/components/ui/useToast'
import { useAuth } from '@/features/auth/useAuth'
import { apiErrorMessage } from '@/lib/apiClient'

import { downloadExport } from './api'
import { DOCKET_TYPE_LABELS } from './draft'
import { formatAmount, formatDate, formatDateTime, formatMoney } from './format'
import { useDeleteDocket, useDocket, useDocketMeta } from './hooks'

export function DocketDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const toast = useToast()
  const { user } = useAuth()

  const docketQuery = useDocket(id)
  const metaQuery = useDocketMeta()
  const deleteMutation = useDeleteDocket()

  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const [lightbox, setLightbox] = useState<string | null>(null)
  const [exporting, setExporting] = useState(false)

  if (docketQuery.isLoading || metaQuery.isLoading) return <PageLoading label="Loading docket…" />
  if (docketQuery.isError || !docketQuery.data) {
    return (
      <PageError
        message="That docket could not be loaded."
        action={<Button onClick={() => navigate('/dockets')}>Back to dockets</Button>}
      />
    )
  }

  const docket = docketQuery.data
  const typeMeta = metaQuery.data?.types.find((entry) => entry.value === docket.docket_type)
  const isCategory = typeMeta?.shape === 'categories'

  async function handleExport(output: 'json' | 'pdf') {
    setExporting(true)
    try {
      // The export endpoint filters by store and week; narrowing to the docket's
      // own day keeps a single-docket download close to one sheet.
      await downloadExport(
        {
          store: [docket.store_detail.slug],
          docket_type: [docket.docket_type],
          date_from: docket.effective_date,
          date_to: docket.effective_date,
        },
        output,
      )
      toast.push(`${output.toUpperCase()} downloaded.`, 'success')
    } catch (error) {
      toast.push(apiErrorMessage(error, 'Export failed.'), 'error')
    } finally {
      setExporting(false)
    }
  }

  async function handleDelete() {
    try {
      await deleteMutation.mutateAsync(docket.id)
      toast.push('Docket deleted.', 'success')
      navigate('/dockets')
    } catch (error) {
      toast.push(apiErrorMessage(error, 'Could not delete the docket.'), 'error')
    } finally {
      setConfirmingDelete(false)
    }
  }

  const meta: [string, string][] = [
    ['Store', docket.store_detail.name],
    ...(docket.destination_store_detail
      ? ([['Receiving store', docket.destination_store_detail.name]] as [string, string][])
      : []),
    [isCategory ? 'Week ending' : 'Date', formatDate(docket.effective_date)],
    ...(docket.reference ? ([['Reference', docket.reference]] as [string, string][]) : []),
    ...(docket.docket_number ? ([['Docket #', docket.docket_number]] as [string, string][]) : []),
    ...(docket.department ? ([['Department', docket.department]] as [string, string][]) : []),
    ...(docket.supplier ? ([['Supplier', docket.supplier]] as [string, string][]) : []),
    ...(docket.manager_name ? ([['Manager', docket.manager_name]] as [string, string][]) : []),
    ...(docket.outgoing_staff_name
      ? ([['Outgoing staff', docket.outgoing_staff_name]] as [string, string][])
      : []),
    ['Filed', formatDateTime(docket.created_at)],
    ...(docket.created_by_email ? ([['Filed by', docket.created_by_email]] as [string, string][]) : []),
  ]

  return (
    <div className="u-stack">
      <div className="page-head">
        <div>
          <div className="u-row" style={{ marginBottom: 4 }}>
            <Badge tone={docket.docket_type}>{DOCKET_TYPE_LABELS[docket.docket_type]}</Badge>
            <span className="u-muted" style={{ fontSize: 'var(--text-sm)' }}>
              {docket.store_detail.name}
              {docket.destination_store_detail
                ? ` → ${docket.destination_store_detail.name}`
                : ''}
            </span>
          </div>
          <h1 className="page-head__title">{formatMoney(docket.total)}</h1>
          <p className="page-head__sub">
            {formatDate(docket.effective_date)} · {docket.lines.length} row
            {docket.lines.length === 1 ? '' : 's'}
          </p>
        </div>
        <div className="page-head__actions">
          <Button variant="ghost" onClick={() => navigate('/dockets')}>
            Back
          </Button>
          <Button variant="secondary" loading={exporting} onClick={() => handleExport('pdf')}>
            PDF
          </Button>
          <Button variant="secondary" loading={exporting} onClick={() => handleExport('json')}>
            JSON
          </Button>
          <Button onClick={() => navigate(`/dockets/${docket.id}/edit`)}>Edit</Button>
          {user?.is_manager && (
            <Button variant="danger" onClick={() => setConfirmingDelete(true)}>
              Delete
            </Button>
          )}
        </div>
      </div>

      <Card title="Details">
        <div className="form-grid">
          {meta.map(([label, value]) => (
            <div key={label}>
              <div className="section-label">{label}</div>
              <div>{value}</div>
            </div>
          ))}
        </div>
        {docket.reason && (
          <div style={{ marginTop: 'var(--space-4)' }}>
            <div className="section-label">Reason for return</div>
            <p>{docket.reason}</p>
          </div>
        )}
        {docket.notes && (
          <div style={{ marginTop: 'var(--space-4)' }}>
            <div className="section-label">Notes</div>
            <p>{docket.notes}</p>
          </div>
        )}
      </Card>

      <Card title={isCategory ? 'Docket entries' : 'Goods'} flush>
        <div className="table-scroll">
          {isCategory && typeMeta ? (
            <table className="table table--stacked">
              <thead>
                <tr>
                  <th scope="col">Date</th>
                  <th scope="col">Supplier</th>
                  <th scope="col">Docket #</th>
                  {typeMeta.columns.map((column) => (
                    <th scope="col" key={column.key} className="u-right">
                      {column.label}
                    </th>
                  ))}
                  <th scope="col" className="u-right">
                    Total
                  </th>
                  <th scope="col">Comments</th>
                </tr>
              </thead>
              <tbody>
                {docket.lines.map((line, index) => (
                  <tr key={line.id ?? index}>
                    <td className="u-nowrap" data-label="Date">{formatDate(line.line_date)}</td>
                    <td data-label="Supplier">{line.supplier || '—'}</td>
                    <td className="u-mono" data-label="Docket #">{line.docket_number || '—'}</td>
                    {typeMeta.columns.map((column) => (
                      <td key={column.key} className="u-right u-num" data-label={column.label}>
                        {formatAmount(line.amounts?.[column.key]) || ''}
                      </td>
                    ))}
                    <td className="u-right u-num" data-label="Row total" style={{ fontWeight: 700 }}>
                      {formatAmount(line.total)}
                    </td>
                    <td data-label="Comments">{line.comments || ''}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td colSpan={3}>TOTALS</td>
                  {typeMeta.columns.map((column) => (
                    <td key={column.key} className="u-right u-num" data-label={column.label}>
                      {formatAmount(docket.category_totals[column.key]) || ''}
                    </td>
                  ))}
                  <td className="u-right u-num" data-label="Docket total">{formatAmount(docket.total)}</td>
                  <td />
                </tr>
              </tfoot>
            </table>
          ) : (
            <table className="table table--stacked">
              <thead>
                <tr>
                  <th scope="col">Qty / Units</th>
                  <th scope="col">Description</th>
                  <th scope="col" className="u-right">
                    Cost €
                  </th>
                  <th scope="col" className="u-right">
                    Retail €
                  </th>
                  <th scope="col" className="u-right">
                    Total €
                  </th>
                </tr>
              </thead>
              <tbody>
                {docket.lines.map((line, index) => (
                  <tr key={line.id ?? index}>
                    <td data-label="Qty / units">{line.quantity || '—'}</td>
                    <td data-label="Description">{line.description || '—'}</td>
                    <td className="u-right u-num" data-label="Cost €">{formatAmount(line.cost_price)}</td>
                    <td className="u-right u-num" data-label="Retail €">{formatAmount(line.retail_price)}</td>
                    <td className="u-right u-num" data-label="Total €" style={{ fontWeight: 700 }}>
                      {formatAmount(line.total)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td colSpan={4}>TOTAL</td>
                  <td className="u-right u-num" data-label="Docket total">{formatAmount(docket.total)}</td>
                </tr>
              </tfoot>
            </table>
          )}
        </div>
      </Card>

      {docket.signatures.length > 0 && (
        <Card title="Signatures">
          <div className="sig-preview">
            {docket.signatures.map((signature) => (
              <figure className="sig-preview__item" key={signature.id ?? signature.role}>
                <img src={signature.image} alt={`${signature.role} signature`} />
                <figcaption className="u-subtle" style={{ fontSize: 'var(--text-2xs)' }}>
                  {signature.role.replace(/_/g, ' ')}
                  {signature.signed_name ? ` · ${signature.signed_name}` : ''}
                </figcaption>
              </figure>
            ))}
          </div>
        </Card>
      )}

      {docket.photos.length > 0 && (
        <Card title={`Photos (${docket.photos.length})`}>
          <div className="photo-grid">
            {docket.photos.map((photo, index) => (
              <button
                type="button"
                className="photo-tile"
                key={photo.id ?? index}
                onClick={() => setLightbox(photo.image)}
              >
                <img src={photo.image} alt={photo.caption || `Docket photo ${index + 1}`} />
              </button>
            ))}
          </div>
        </Card>
      )}

      <Modal open={Boolean(lightbox)} title="Photo" onClose={() => setLightbox(null)}>
        {lightbox && <img src={lightbox} alt="Docket photo" style={{ width: '100%' }} />}
      </Modal>

      <Modal
        open={confirmingDelete}
        title="Delete this docket?"
        onClose={() => setConfirmingDelete(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirmingDelete(false)}>
              Cancel
            </Button>
            <Button variant="danger" loading={deleteMutation.isPending} onClick={handleDelete}>
              Delete docket
            </Button>
          </>
        }
      >
        <p>
          This removes the {DOCKET_TYPE_LABELS[docket.docket_type].toLowerCase()} docket for{' '}
          <strong>{docket.store_detail.name}</strong> dated{' '}
          <strong>{formatDate(docket.effective_date)}</strong>, along with its rows, signatures and
          photos. It cannot be undone.
        </p>
      </Modal>
    </div>
  )
}
