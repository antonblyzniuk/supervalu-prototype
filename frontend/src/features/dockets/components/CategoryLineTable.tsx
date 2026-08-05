import { formatAmount } from '../format'
import type { DocketColumn, DocketLine } from '../types'

interface CategoryLineTableProps {
  columns: DocketColumn[]
  lines: DocketLine[]
  onChange: (lines: DocketLine[]) => void
}

function toNumber(value: string | null | undefined): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

/** Row total is always the sum of its category columns — never hand-typed. */
function rowTotal(line: DocketLine, columns: DocketColumn[]): number {
  return columns.reduce((sum, column) => sum + toNumber(line.amounts?.[column.key]), 0)
}

export function CategoryLineTable({ columns, lines, onChange }: CategoryLineTableProps) {
  const update = (index: number, patch: Partial<DocketLine>) => {
    onChange(
      lines.map((line, i) => {
        if (i !== index) return line
        const next = { ...line, ...patch }
        return { ...next, total: rowTotal(next, columns).toFixed(2) }
      }),
    )
  }

  const updateAmount = (index: number, key: string, raw: string) => {
    const line = lines[index]
    if (!line) return
    const amounts = { ...(line.amounts ?? {}) }
    if (raw.trim() === '') delete amounts[key]
    else amounts[key] = raw
    update(index, { amounts })
  }

  const addRow = () =>
    onChange([...lines, { position: lines.length, amounts: {}, total: '0.00' }])

  const removeRow = (index: number) =>
    onChange(lines.filter((_, i) => i !== index).map((line, i) => ({ ...line, position: i })))

  const columnTotals = columns.map((column) =>
    lines.reduce((sum, line) => sum + toNumber(line.amounts?.[column.key]), 0),
  )
  const grandTotal = lines.reduce((sum, line) => sum + rowTotal(line, columns), 0)

  return (
    <>
      <div className="table-scroll">
        <table className="table grid-table" style={{ minWidth: `${520 + columns.length * 78}px` }}>
          <thead>
            <tr>
              <th scope="col" className="u-sr-only">
                Row
              </th>
              <th scope="col">Date</th>
              <th scope="col">Supplier</th>
              <th scope="col">Docket #</th>
              {columns.map((column) => (
                <th scope="col" key={column.key} className="u-right">
                  {column.label}
                </th>
              ))}
              <th scope="col" className="u-right">
                Total
              </th>
              <th scope="col">Comments</th>
              <th scope="col">
                <span className="u-sr-only">Remove</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {lines.map((line, index) => (
              <tr key={index}>
                <td className="grid-table__rownum">{index + 1}</td>
                <td>
                  <input
                    className="input"
                    type="date"
                    value={line.line_date ?? ''}
                    onChange={(e) => update(index, { line_date: e.target.value || null })}
                    aria-label={`Row ${index + 1} date`}
                  />
                </td>
                <td>
                  <input
                    className="input"
                    style={{ minWidth: '130px' }}
                    value={line.supplier ?? ''}
                    onChange={(e) => update(index, { supplier: e.target.value })}
                    placeholder="Supplier"
                    aria-label={`Row ${index + 1} supplier`}
                  />
                </td>
                <td>
                  <input
                    className="input"
                    style={{ minWidth: '84px' }}
                    value={line.docket_number ?? ''}
                    onChange={(e) => update(index, { docket_number: e.target.value })}
                    placeholder="—"
                    aria-label={`Row ${index + 1} docket number`}
                  />
                </td>
                {columns.map((column) => (
                  <td key={column.key}>
                    <input
                      className="input input--num"
                      style={{ minWidth: '74px' }}
                      type="text"
                      inputMode="decimal"
                      value={line.amounts?.[column.key] ?? ''}
                      onChange={(e) => updateAmount(index, column.key, e.target.value)}
                      placeholder="0.00"
                      aria-label={`Row ${index + 1} ${column.label}`}
                    />
                  </td>
                ))}
                <td className="u-right u-num" style={{ fontWeight: 700, whiteSpace: 'nowrap' }}>
                  {formatAmount(rowTotal(line, columns)) || '0.00'}
                </td>
                <td>
                  <input
                    className="input"
                    style={{ minWidth: '130px' }}
                    value={line.comments ?? ''}
                    onChange={(e) => update(index, { comments: e.target.value })}
                    placeholder="—"
                    aria-label={`Row ${index + 1} comments`}
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
              <td colSpan={4}>TOTALS</td>
              {columnTotals.map((total, index) => (
                <td key={columns[index]?.key} className="u-right u-num">
                  {total ? formatAmount(total) : ''}
                </td>
              ))}
              <td className="u-right u-num">{formatAmount(grandTotal)}</td>
              <td colSpan={2} />
            </tr>
          </tfoot>
        </table>
      </div>

      <button type="button" className="add-row" onClick={addRow}>
        + Add row
      </button>
    </>
  )
}
