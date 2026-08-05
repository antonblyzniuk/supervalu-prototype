import { formatAmount } from '../format'
import type { DocketLine } from '../types'

interface ItemLineTableProps {
  lines: DocketLine[]
  onChange: (lines: DocketLine[]) => void
}

function toNumber(value: string | null | undefined): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

/**
 * Suggests qty × cost when the quantity is plain numeric ("3"), but leaves a
 * hand-entered total alone — staff often write "3 cases" and price the lot.
 */
function suggestTotal(line: DocketLine): string | undefined {
  const quantity = Number(String(line.quantity ?? '').trim())
  const cost = Number(line.cost_price)
  if (!Number.isFinite(quantity) || !quantity) return undefined
  if (!Number.isFinite(cost) || !cost) return undefined
  return (quantity * cost).toFixed(2)
}

export function ItemLineTable({ lines, onChange }: ItemLineTableProps) {
  const update = (index: number, patch: Partial<DocketLine>, autoTotal = true) => {
    onChange(
      lines.map((line, i) => {
        if (i !== index) return line
        const next = { ...line, ...patch }
        if (autoTotal && !next.totalTouched) {
          const suggestion = suggestTotal(next)
          if (suggestion !== undefined) next.total = suggestion
        }
        return next
      }),
    )
  }

  const addRow = () => onChange([...lines, { position: lines.length, total: '' }])

  const removeRow = (index: number) =>
    onChange(lines.filter((_, i) => i !== index).map((line, i) => ({ ...line, position: i })))

  const grandTotal = lines.reduce((sum, line) => sum + toNumber(line.total), 0)

  return (
    <>
      <div className="table-scroll">
        <table className="table grid-table table--stacked" style={{ minWidth: '720px' }}>
          <thead>
            <tr>
              <th scope="col" className="u-sr-only">
                Row
              </th>
              <th scope="col">Qty / Units</th>
              <th scope="col">Description of goods</th>
              <th scope="col" className="u-right">
                Cost €
              </th>
              <th scope="col" className="u-right">
                Retail €
              </th>
              <th scope="col" className="u-right">
                Total €
              </th>
              <th scope="col">
                <span className="u-sr-only">Remove</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {lines.map((line, index) => (
              <tr key={index}>
                <td className="grid-table__rownum" data-label="Row">
                  {index + 1}
                </td>
                <td data-label="Qty / units">
                  <input
                    className="input"
                    style={{ minWidth: '96px' }}
                    value={line.quantity ?? ''}
                    onChange={(e) => update(index, { quantity: e.target.value })}
                    placeholder="e.g. 3 or 3 cases"
                    aria-label={`Row ${index + 1} quantity`}
                  />
                </td>
                <td data-label="Description">
                  <input
                    className="input"
                    style={{ minWidth: '220px' }}
                    value={line.description ?? ''}
                    onChange={(e) => update(index, { description: e.target.value }, false)}
                    placeholder="Description"
                    aria-label={`Row ${index + 1} description`}
                  />
                </td>
                <td data-label="Cost €">
                  <input
                    className="input input--num"
                    style={{ minWidth: '90px' }}
                    inputMode="decimal"
                    value={line.cost_price ?? ''}
                    onChange={(e) => update(index, { cost_price: e.target.value || null })}
                    placeholder="0.00"
                    aria-label={`Row ${index + 1} cost price`}
                  />
                </td>
                <td data-label="Retail €">
                  <input
                    className="input input--num"
                    style={{ minWidth: '90px' }}
                    inputMode="decimal"
                    value={line.retail_price ?? ''}
                    onChange={(e) => update(index, { retail_price: e.target.value || null }, false)}
                    placeholder="0.00"
                    aria-label={`Row ${index + 1} retail price`}
                  />
                </td>
                <td data-label="Total €">
                  <input
                    className="input input--num"
                    style={{ minWidth: '90px', fontWeight: 700 }}
                    inputMode="decimal"
                    value={line.total ?? ''}
                    onChange={(e) =>
                      update(index, { total: e.target.value, totalTouched: true }, false)
                    }
                    placeholder="0.00"
                    aria-label={`Row ${index + 1} total`}
                  />
                </td>
                <td className="grid-table__remove">
                  <button
                    type="button"
                    className="btn btn--ghost btn--icon"
                    onClick={() => removeRow(index)}
                    disabled={lines.length === 1}
                  >
                    <span aria-hidden="true">✕</span>
                    <span className="u-sr-only">Remove row {index + 1}</span>
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td colSpan={5}>TOTAL</td>
              <td className="u-right u-num" data-label="Docket total">
                {formatAmount(grandTotal)}
              </td>
              <td />
            </tr>
          </tfoot>
        </table>
      </div>

      <button type="button" className="add-row" onClick={addRow}>
        + Add item
      </button>
    </>
  )
}
