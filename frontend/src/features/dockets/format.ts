const euro = new Intl.NumberFormat('en-IE', { style: 'currency', currency: 'EUR' })
const number = new Intl.NumberFormat('en-IE', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

export function formatMoney(value: string | number | null | undefined): string {
  const amount = Number(value ?? 0)
  return euro.format(Number.isFinite(amount) ? amount : 0)
}

export function formatAmount(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return ''
  const amount = Number(value)
  return Number.isFinite(amount) ? number.format(amount) : String(value)
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value.length <= 10 ? `${value}T00:00:00` : value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('en-IE', { day: '2-digit', month: 'short', year: 'numeric' })
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('en-IE', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function toISODate(date: Date): string {
  // Local calendar date — `toISOString()` would shift across the UTC boundary.
  const offset = date.getTimezoneOffset() * 60_000
  return new Date(date.getTime() - offset).toISOString().slice(0, 10)
}

/** Trading week runs Sunday → Saturday, matching the paper top sheets. */
export function weekStart(date: Date): Date {
  const start = new Date(date)
  start.setDate(start.getDate() - start.getDay())
  start.setHours(0, 0, 0, 0)
  return start
}

export function weekEnd(date: Date): Date {
  const end = weekStart(date)
  end.setDate(end.getDate() + 6)
  return end
}

export function weekLabel(date: Date): string {
  const start = weekStart(date)
  const end = weekEnd(date)
  const format = (value: Date) =>
    value.toLocaleDateString('en-IE', { day: 'numeric', month: 'short' })
  return `${format(start)} – ${format(end)} ${end.getFullYear()}`
}
