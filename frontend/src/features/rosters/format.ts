/** Roster-specific formatting. Money and dates come from the dockets helpers. */

/** "08:00:00" → "08:00". The API renders a TimeField with seconds. */
export function formatClock(time: string): string {
  return time.slice(0, 5)
}

/** 510 → "8h 30m". Whole hours drop the minutes, zero stays "0h". */
export function formatDuration(minutes: number): string {
  if (!minutes) return '0h'
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  if (!hours) return `${rest}m`
  return rest ? `${hours}h ${rest}m` : `${hours}h`
}

/** An ISO date as the column heading: "Sun 2 Aug". */
export function dayHeading(iso: string): { weekday: string; date: string } {
  const date = new Date(`${iso}T00:00:00`)
  return {
    weekday: date.toLocaleDateString('en-IE', { weekday: 'short' }),
    date: date.toLocaleDateString('en-IE', { day: 'numeric', month: 'short' }),
  }
}

/** "Sunday 2 August" — for the shift editor's title. */
export function longDay(iso: string): string {
  const date = new Date(`${iso}T00:00:00`)
  return date.toLocaleDateString('en-IE', { weekday: 'long', day: 'numeric', month: 'long' })
}

/**
 * The same arithmetic the API applies, for the editor's live preview.
 *
 * An end at or before the start means the shift runs past midnight. The server
 * recomputes all of this on save — this only exists so the manager can see the
 * effect of a change before committing it.
 */
export function paidMinutesOf(
  start: string,
  end: string,
  breakMinutes: number,
  breakPaid: boolean,
): { duration: number; paid: number } {
  const toMinutes = (value: string) => {
    const [hours, mins] = value.split(':')
    const h = Number(hours)
    const m = Number(mins)
    if (!Number.isFinite(h) || !Number.isFinite(m)) return Number.NaN
    return h * 60 + m
  }

  const from = toMinutes(start)
  const to = toMinutes(end)
  if (Number.isNaN(from) || Number.isNaN(to)) return { duration: 0, paid: 0 }

  const duration = to > from ? to - from : to + 24 * 60 - from
  const paid = Math.max(duration - (breakPaid ? 0 : breakMinutes), 0)
  return { duration, paid }
}
