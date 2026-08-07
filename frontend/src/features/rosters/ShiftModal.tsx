import { useEffect, useState, type FormEvent } from 'react'

import { Button } from '@/components/ui/Button'
import { Field } from '@/components/ui/Field'
import { Modal } from '@/components/ui/Modal'
import { useToast } from '@/components/ui/useToast'
import { formatMoney } from '@/features/dockets/format'
import { apiErrorMessage } from '@/lib/apiClient'
import type { Shift } from '@/types/api'

import { formatClock, formatDuration, longDay, paidMinutesOf } from './format'
import { useCreateShift, useDeleteShift, useUpdateShift } from './hooks'
import type { ShiftDefaults, ShiftTarget } from './types'

interface ShiftModalProps {
  open: boolean
  target: ShiftTarget | null
  /** The shift being edited, if the day already has one. */
  shift?: Shift
  hourlyRate: string
  /** Later days in the week this person has free — offered for "repeat". */
  freeDaysAfter: string[]
  onClose: () => void
  /** Carried to the next shift the manager adds, so a week fills in quickly. */
  onDefaultsChange: (defaults: ShiftDefaults) => void
  defaults: ShiftDefaults
}

const BREAK_OPTIONS = [0, 15, 30, 45, 60, 90]

export function ShiftModal({
  open,
  target,
  shift,
  hourlyRate,
  freeDaysAfter,
  onClose,
  onDefaultsChange,
  defaults,
}: ShiftModalProps) {
  const toast = useToast()
  const [form, setForm] = useState<ShiftDefaults>(defaults)
  const [notes, setNotes] = useState('')
  const [repeat, setRepeat] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const createMutation = useCreateShift()
  const updateMutation = useUpdateShift()
  const deleteMutation = useDeleteShift()
  const saving = createMutation.isPending || updateMutation.isPending

  useEffect(() => {
    if (!open) return
    setError(null)
    setRepeat(false)
    setNotes(shift?.notes ?? '')
    setForm(
      shift
        ? {
            start: formatClock(shift.start_time),
            end: formatClock(shift.end_time),
            breakMinutes: shift.break_minutes,
            breakPaid: shift.break_paid,
          }
        : defaults,
    )
  }, [open, shift, defaults])

  const patch = (changes: Partial<ShiftDefaults>) =>
    setForm((current) => ({ ...current, ...changes }))

  const { duration, paid } = paidMinutesOf(
    form.start,
    form.end,
    form.breakMinutes,
    form.breakPaid,
  )
  const cost = (paid / 60) * Number(hourlyRate)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    if (!target) return

    const body = {
      date: target.date,
      start_time: form.start,
      end_time: form.end,
      break_minutes: form.breakMinutes,
      break_paid: form.breakPaid,
      notes: notes.trim(),
    }

    try {
      if (shift) {
        await updateMutation.mutateAsync({ id: shift.id, ...body })
        toast.push(`${target.personName}'s shift updated.`, 'success')
      } else {
        const days = repeat ? [target.date, ...freeDaysAfter] : [target.date]
        // One at a time: the API validates each day on its own, and a partial
        // failure should leave the days that did save in place.
        for (const date of days) {
          await createMutation.mutateAsync({ ...body, date, user_id: target.personId })
        }
        toast.push(
          days.length > 1
            ? `${target.personName} rostered on ${days.length} days.`
            : `${target.personName} rostered.`,
          'success',
        )
      }
      onDefaultsChange({ ...form })
      onClose()
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not save the shift.'))
    }
  }

  async function handleDelete() {
    if (!shift || !target) return
    try {
      await deleteMutation.mutateAsync(shift.id)
      toast.push(`${target.personName} taken off that day.`, 'success')
      onClose()
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not remove the shift.'))
    }
  }

  return (
    <Modal
      open={open}
      title={target ? `${target.personName} · ${longDay(target.date)}` : 'Shift'}
      onClose={onClose}
      footer={
        <>
          {shift && (
            <Button
              variant="danger"
              loading={deleteMutation.isPending}
              onClick={handleDelete}
              // Pushes Cancel/Save to the right, so the destructive action is
              // not sitting under the thumb that meant to press Save.
              style={{ marginRight: 'auto' }}
            >
              Remove
            </Button>
          )}
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="shift-form" loading={saving}>
            {shift ? 'Save shift' : 'Add shift'}
          </Button>
        </>
      }
    >
      <form id="shift-form" className="u-stack-sm" onSubmit={handleSubmit} noValidate>
        {error && <div className="alert alert--error">{error}</div>}

        <div className="form-grid form-grid--2">
          <Field label="Start" required>
            <input
              className="input"
              type="time"
              value={form.start}
              onChange={(e) => patch({ start: e.target.value })}
              required
            />
          </Field>
          <Field
            label="Finish"
            required
            hint={duration && form.end <= form.start ? 'Runs past midnight.' : undefined}
          >
            <input
              className="input"
              type="time"
              value={form.end}
              onChange={(e) => patch({ end: e.target.value })}
              required
            />
          </Field>
        </div>

        <div className="form-grid form-grid--2">
          <Field label="Break">
            <select
              className="select"
              value={form.breakMinutes}
              onChange={(e) => patch({ breakMinutes: Number(e.target.value) })}
            >
              {BREAK_OPTIONS.map((minutes) => (
                <option key={minutes} value={minutes}>
                  {minutes === 0 ? 'No break' : `${minutes} min`}
                </option>
              ))}
            </select>
          </Field>
          <Field
            label="Break is"
            hint={form.breakPaid ? 'Counted in the paid hours.' : 'Comes off the paid hours.'}
          >
            <select
              className="select"
              value={form.breakPaid ? 'paid' : 'unpaid'}
              disabled={form.breakMinutes === 0}
              onChange={(e) => patch({ breakPaid: e.target.value === 'paid' })}
            >
              <option value="unpaid">Unpaid</option>
              <option value="paid">Paid</option>
            </select>
          </Field>
        </div>

        {/* The server recomputes all of this on save; this is so the effect of
            a break is visible before committing to it. */}
        <div className="stat-grid">
          <div className="stat">
            <div className="stat__label">On site</div>
            <div className="stat__value">{formatDuration(duration)}</div>
          </div>
          <div className="stat">
            <div className="stat__label">Paid hours</div>
            <div className="stat__value">{formatDuration(paid)}</div>
          </div>
          <div className="stat stat--brand">
            <div className="stat__label">Cost</div>
            <div className="stat__value">{formatMoney(cost)}</div>
            <div className="stat__meta">at {formatMoney(hourlyRate)}/hr</div>
          </div>
        </div>

        <Field label="Note" hint="Optional — anything specific to this shift.">
          <input
            className="input"
            value={notes}
            maxLength={200}
            onChange={(e) => setNotes(e.target.value)}
          />
        </Field>

        {!shift && freeDaysAfter.length > 0 && (
          <label className="check">
            <input
              type="checkbox"
              checked={repeat}
              onChange={(e) => setRepeat(e.target.checked)}
            />
            <span>
              Repeat on their {freeDaysAfter.length} free{' '}
              {freeDaysAfter.length === 1 ? 'day' : 'days'} left this week
            </span>
          </label>
        )}
      </form>
    </Modal>
  )
}
