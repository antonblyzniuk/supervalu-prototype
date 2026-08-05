import { toISODate } from './format'
import type { Docket, DocketDraft, DocketLine, DocketType, DocketTypeMeta } from './types'

export const DOCKET_TYPE_LABELS: Record<DocketType, string> = {
  ambient: 'Ambient',
  chilled: 'Chilled',
  returns: 'Returns',
  transfer: 'Transfer',
}

export const DOCKET_TYPES: DocketType[] = ['ambient', 'chilled', 'returns', 'transfer']

export function isDocketType(value: string | undefined): value is DocketType {
  return DOCKET_TYPES.includes(value as DocketType)
}

/** The Saturday that closes the current trading week — the usual week ending. */
function currentWeekEnding(): string {
  const date = new Date()
  date.setDate(date.getDate() + (6 - date.getDay()))
  return toISODate(date)
}

export function emptyDraft(docketType: DocketType, storeSlug: string): DocketDraft {
  const isCategory = docketType === 'ambient' || docketType === 'chilled'
  return {
    docket_type: docketType,
    store: storeSlug,
    destination_store: null,
    week_ending: isCategory ? currentWeekEnding() : '',
    docket_date: isCategory ? '' : toISODate(new Date()),
    reference: '',
    docket_number: '',
    department: '',
    supplier: '',
    reason: '',
    outgoing_staff_name: '',
    manager_name: '',
    notes: '',
    lines: startingLines(isCategory),
    signatures: [],
    photos: [],
  }
}

function startingLines(isCategory: boolean): DocketLine[] {
  const count = isCategory ? 3 : 2
  return Array.from({ length: count }, (_, position) =>
    isCategory ? { position, amounts: {}, total: '0.00' } : { position, total: '' },
  )
}

export function draftFromDocket(docket: Docket): DocketDraft {
  return {
    docket_type: docket.docket_type,
    store: docket.store_detail.slug,
    destination_store: docket.destination_store_detail?.slug ?? null,
    week_ending: docket.week_ending ?? '',
    docket_date: docket.docket_date ?? '',
    reference: docket.reference,
    docket_number: docket.docket_number,
    department: docket.department,
    supplier: docket.supplier,
    reason: docket.reason,
    outgoing_staff_name: docket.outgoing_staff_name,
    manager_name: docket.manager_name,
    notes: docket.notes,
    lines: docket.lines.map((line, index) => ({ ...line, position: index })),
    signatures: docket.signatures.map((signature) => ({ ...signature })),
    photos: docket.photos.map((photo) => ({ ...photo })),
  }
}

function hasContent(line: DocketLine): boolean {
  const amountFilled = Object.values(line.amounts ?? {}).some((value) => value !== '')
  return Boolean(
    amountFilled ||
      line.supplier ||
      line.docket_number ||
      line.comments ||
      line.quantity ||
      line.description ||
      line.cost_price ||
      line.retail_price ||
      (line.total && Number(line.total) !== 0),
  )
}

/**
 * Turns the working draft into an API payload: blank rows dropped, blank dates
 * nulled, client-only flags removed, and only the fields the type actually uses.
 */
export function draftToPayload(draft: DocketDraft, meta: DocketTypeMeta): Partial<DocketDraft> {
  const isCategory = meta.shape === 'categories'

  const lines = draft.lines
    .filter(hasContent)
    .map(({ totalTouched: _ignored, id: _id, ...line }, position) => ({
      ...line,
      position,
      line_date: line.line_date || null,
      cost_price: line.cost_price || null,
      retail_price: line.retail_price || null,
      total: line.total && line.total !== '' ? line.total : '0.00',
    }))

  const payload: Partial<DocketDraft> = {
    docket_type: draft.docket_type,
    store: draft.store,
    reference: draft.reference,
    docket_number: draft.docket_number,
    department: draft.department,
    notes: draft.notes,
    manager_name: draft.manager_name,
    lines,
    // Only re-post signatures the user drew this session; stored ones come back
    // as URLs, which the API would reject as an image payload.
    signatures: draft.signatures.filter((signature) => signature.image.startsWith('data:')),
    photos: draft.photos.map((photo) => ({
      image: photo.image,
      caption: photo.caption ?? '',
      captured_at: photo.captured_at ?? null,
    })),
  }

  if (isCategory) {
    payload.week_ending = draft.week_ending || undefined
  } else {
    payload.docket_date = draft.docket_date || undefined
  }

  if (draft.docket_type === 'returns') {
    payload.supplier = draft.supplier
    payload.reason = draft.reason
  }

  if (draft.docket_type === 'transfer') {
    payload.destination_store = draft.destination_store
    payload.outgoing_staff_name = draft.outgoing_staff_name
  }

  return payload
}

/** Client-side checks that mirror the serializer, so errors surface instantly. */
export function validateDraft(draft: DocketDraft, meta: DocketTypeMeta): Record<string, string> {
  const errors: Record<string, string> = {}

  if (!draft.store) errors.store = 'Choose a store.'

  if (meta.shape === 'categories') {
    if (!draft.week_ending) errors.week_ending = 'Week ending is required.'
  } else if (!draft.docket_date) {
    errors.docket_date = 'Date is required.'
  }

  if (draft.docket_type === 'returns' && !draft.supplier.trim()) {
    errors.supplier = 'Supplier is required.'
  }

  if (draft.docket_type === 'transfer') {
    if (!draft.destination_store) errors.destination_store = 'Choose the receiving store.'
    else if (draft.destination_store === draft.store) {
      errors.destination_store = 'Receiving store must be different.'
    }
  }

  if (!draft.lines.some(hasContent)) {
    errors.lines = 'Fill in at least one row before saving.'
  }

  return errors
}
