import { useMemo, useState } from 'react'

import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { Field } from '@/components/ui/Field'
import { PageError, PageLoading } from '@/components/ui/PageState'
import { useToast } from '@/components/ui/useToast'
import { useAuth } from '@/features/auth/useAuth'
import { formatMoney, toISODate, weekLabel } from '@/features/dockets/format'
import { useStores } from '@/features/stores/hooks'
import { apiErrorMessage } from '@/lib/apiClient'
import type { RosterDepartment, RosterPersonRow } from '@/types/api'

import { ShiftModal } from './ShiftModal'
import { downloadRoster } from './api'
import { dayHeading, formatClock, formatDuration } from './format'
import { useRosterBoard } from './hooks'
import { INITIAL_DEFAULTS, type ShiftDefaults, type ShiftTarget } from './types'

/** Weekly staff roster for one store: who is on, for how long, at what cost. */
export function RosterPage() {
  const { user } = useAuth()
  const toast = useToast()
  const storesQuery = useStores()
  const stores = useMemo(() => storesQuery.data ?? [], [storesQuery.data])

  const [chosenStore, setChosenStore] = useState<string | null>(null)
  const [weekAnchor, setWeekAnchor] = useState(() => toISODate(new Date()))
  const [target, setTarget] = useState<ShiftTarget | null>(null)
  // Carried from the last shift added, so filling a week is a few clicks.
  const [defaults, setDefaults] = useState<ShiftDefaults>(INITIAL_DEFAULTS)
  // Slug of the department currently downloading, or '' for the whole store.
  const [exporting, setExporting] = useState<string | null>(null)

  // Derived rather than an effect: the store list arrives asynchronously, and
  // a manager's own branch is the one they nearly always want.
  const storeSlug = chosenStore ?? user?.store?.slug ?? stores[0]?.slug

  const boardQuery = useRosterBoard(storeSlug, weekAnchor)
  const board = boardQuery.data

  const shiftWeek = (deltaDays: number) => {
    const date = new Date(`${weekAnchor}T00:00:00`)
    date.setDate(date.getDate() + deltaDays)
    setWeekAnchor(toISODate(date))
  }

  /** `departmentSlug` omitted downloads the whole store. */
  async function handleExport(departmentSlug?: string) {
    if (!storeSlug) return
    setExporting(departmentSlug ?? '')
    try {
      await downloadRoster(storeSlug, weekAnchor, departmentSlug ? [departmentSlug] : [])
      toast.push('Roster PDF downloaded.', 'success')
    } catch (error) {
      toast.push(apiErrorMessage(error, 'Could not export the roster.'), 'error')
    } finally {
      setExporting(null)
    }
  }

  const openShift = (row: RosterPersonRow, date: string) => {
    const existing = row.shifts.find((shift) => shift.date === date)
    setTarget({
      personId: row.person.id,
      personName: row.person.full_name,
      date,
      shiftId: existing?.id,
    })
  }

  const activeRow = useMemo(() => {
    if (!target || !board) return undefined
    for (const group of board.departments) {
      const found = group.people.find((row) => row.person.id === target.personId)
      if (found) return found
    }
    return undefined
  }, [target, board])

  const activeShift = activeRow?.shifts.find((shift) => shift.date === target?.date)

  /** Days after the one being edited that this person has no shift on. */
  const freeDaysAfter = useMemo(() => {
    if (!target || !board || !activeRow) return []
    const taken = new Set(activeRow.shifts.map((shift) => shift.date))
    return board.days.filter((day) => day > target.date && !taken.has(day))
  }, [target, board, activeRow])

  if (storesQuery.isLoading || (boardQuery.isLoading && !board)) {
    return <PageLoading label="Building the roster…" />
  }
  if (boardQuery.isError) {
    return (
      <PageError
        message={apiErrorMessage(boardQuery.error, 'Could not load the roster.')}
        action={<Button onClick={() => boardQuery.refetch()}>Retry</Button>}
      />
    )
  }

  const anchorDate = new Date(`${weekAnchor}T00:00:00`)
  const dayCount = board?.days.length ?? 7

  return (
    <div className="u-stack">
      <div className="page-head">
        <div>
          <h1 className="page-head__title">Roster</h1>
          <p className="page-head__sub">
            {board?.store.name ?? '—'} · {weekLabel(anchorDate)}
          </p>
        </div>
        <div className="page-head__actions">
          <Button
            variant="secondary"
            loading={exporting === ''}
            disabled={!board}
            onClick={() => handleExport()}
          >
            Download PDF
          </Button>
        </div>
      </div>

      <Card title="Week">
        <div className="form-grid">
          <Field label="Store">
            <select
              className="select"
              value={storeSlug ?? ''}
              onChange={(event) => setChosenStore(event.target.value)}
            >
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
          {/* Not a `Field`: a row of buttons is not one labelled control. The
              empty label is what keeps it level with the inputs beside it. */}
          <div className="field field--actions" role="group" aria-label="Move week">
            <span className="field__label field__label--spacer" aria-hidden="true">
              &nbsp;
            </span>
            <div className="u-row">
              <Button variant="secondary" onClick={() => shiftWeek(-7)}>
                ← Previous
              </Button>
              <Button variant="secondary" onClick={() => setWeekAnchor(toISODate(new Date()))}>
                This week
              </Button>
              <Button variant="secondary" onClick={() => shiftWeek(7)}>
                Next →
              </Button>
            </div>
          </div>
        </div>
      </Card>

      {board && (
        <div className="stat-grid">
          <div className="stat stat--brand">
            <div className="stat__label">Wage bill</div>
            <div className="stat__value">{formatMoney(board.totals.cost)}</div>
            <div className="stat__meta">{board.store.name} · this week</div>
          </div>
          <div className="stat">
            <div className="stat__label">Hours rostered</div>
            <div className="stat__value">{formatDuration(board.totals.paid_minutes)}</div>
            <div className="stat__meta">paid hours</div>
          </div>
          <div className="stat">
            <div className="stat__label">People on</div>
            <div className="stat__value">
              {board.totals.people_rostered}
              <span className="u-subtle" style={{ fontSize: 'var(--text-sm)' }}>
                {' '}
                / {board.totals.people_total}
              </span>
            </div>
            <div className="stat__meta">at this store</div>
          </div>
          <div className="stat">
            <div className="stat__label">Shifts</div>
            <div className="stat__value">{board.totals.shift_count}</div>
          </div>
        </div>
      )}

      {board?.departments.length === 0 && (
        <Card>
          <EmptyState
            icon="🗓️"
            title={`Nobody works at ${board.store.name} yet`}
            description="Assign colleagues to this store on the team page and they will appear here."
          />
        </Card>
      )}

      {board?.departments.map((group) => (
        <DepartmentBoard
          key={group.slug ?? 'unassigned'}
          group={group}
          days={board.days}
          dayCount={dayCount}
          onPick={openShift}
          onExport={handleExport}
          exporting={exporting}
        />
      ))}

      <ShiftModal
        open={Boolean(target)}
        target={target}
        shift={activeShift}
        hourlyRate={activeRow?.person.hourly_rate ?? board?.minimum_hourly_rate ?? '0'}
        freeDaysAfter={freeDaysAfter}
        defaults={defaults}
        onDefaultsChange={setDefaults}
        onClose={() => setTarget(null)}
      />
    </div>
  )
}

interface DepartmentBoardProps {
  group: RosterDepartment
  days: string[]
  dayCount: number
  onPick: (row: RosterPersonRow, date: string) => void
  onExport: (departmentSlug?: string) => void
  exporting: string | null
}

function DepartmentBoard({
  group,
  days,
  dayCount,
  onPick,
  onExport,
  exporting,
}: DepartmentBoardProps) {
  if (group.people.length === 0) {
    return (
      <Card title={group.name}>
        <p className="u-muted">Nobody is assigned to this department at this store.</p>
      </Card>
    )
  }

  return (
    <Card
      title={
        <>
          {group.name}
          <span className="u-subtle" style={{ fontWeight: 600, letterSpacing: 0 }}>
            {formatDuration(group.totals.paid_minutes)} · {formatMoney(group.totals.cost)}
          </span>
        </>
      }
      actions={
        // The trailing group is not a real department, so there is nothing the
        // API could narrow an export to.
        group.department_slug ? (
          <Button
            variant="ghost"
            size="sm"
            loading={exporting === group.department_slug}
            onClick={() => onExport(group.department_slug ?? undefined)}
          >
            PDF
          </Button>
        ) : undefined
      }
      flush
    >
      <div className="table-scroll">
        <table className="table table--stacked roster-table" style={{ minWidth: '900px' }}>
          <thead>
            <tr>
              <th scope="col">Person</th>
              {days.map((day) => {
                const { weekday, date } = dayHeading(day)
                return (
                  <th scope="col" key={day} className="u-center">
                    {weekday}
                    <span className="roster-table__date">{date}</span>
                  </th>
                )
              })}
              <th scope="col" className="u-right">
                Hours
              </th>
              <th scope="col" className="u-right">
                Cost
              </th>
            </tr>
          </thead>
          <tbody>
            {group.people.map((row) => (
              <tr key={row.person.id}>
                <td data-label="Person">
                  <div>
                    <div style={{ fontWeight: 600 }}>{row.person.full_name}</div>
                    {/* A wrapping row rather than text separators — a "·" left
                        dangling at the end of a line reads as a mistake. */}
                    <div
                      className="u-row"
                      style={{ gap: '6px', fontSize: 'var(--text-xs)', rowGap: '2px' }}
                    >
                      <span className="u-subtle">
                        {formatMoney(row.person.hourly_rate)}/hr
                        {row.person.rate_is_default && ' · minimum wage'}
                      </span>
                      {row.person.role !== 'staff' && (
                        <Badge tone={row.person.role === 'admin' ? 'transfer' : 'chilled'}>
                          {row.person.role}
                        </Badge>
                      )}
                      {!row.person.is_active && <Badge>left</Badge>}
                    </div>
                  </div>
                </td>
                {days.map((day) => {
                  const shift = row.shifts.find((entry) => entry.date === day)
                  const { weekday, date } = dayHeading(day)
                  return (
                    <td key={day} data-label={`${weekday} ${date}`} className="roster-table__cell">
                      <button
                        type="button"
                        className={`shift-cell ${shift ? 'shift-cell--on' : ''}`}
                        onClick={() => onPick(row, day)}
                        aria-label={
                          shift
                            ? `Edit ${row.person.full_name}'s shift on ${weekday} ${date}`
                            : `Roster ${row.person.full_name} on ${weekday} ${date}`
                        }
                      >
                        {shift ? (
                          <>
                            <span className="shift-cell__time">
                              {formatClock(shift.start_time)}–{formatClock(shift.end_time)}
                            </span>
                            <span className="shift-cell__meta">
                              {formatDuration(shift.paid_minutes)}
                              {shift.break_minutes > 0 &&
                                ` · ${shift.break_minutes}m ${shift.break_paid ? 'paid' : 'unpaid'}`}
                            </span>
                          </>
                        ) : (
                          <span className="shift-cell__add" aria-hidden="true">
                            +
                          </span>
                        )}
                      </button>
                    </td>
                  )
                })}
                <td className="u-right u-num" data-label="Hours" style={{ fontWeight: 700 }}>
                  {formatDuration(row.totals.paid_minutes)}
                </td>
                <td className="u-right u-num" data-label="Cost" style={{ fontWeight: 700 }}>
                  {formatMoney(row.totals.cost)}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td colSpan={dayCount + 1}>{group.name.toUpperCase()} TOTAL</td>
              <td className="u-right u-num" data-label="Hours">
                {formatDuration(group.totals.paid_minutes)}
              </td>
              <td className="u-right u-num" data-label="Cost">
                {formatMoney(group.totals.cost)}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </Card>
  )
}
