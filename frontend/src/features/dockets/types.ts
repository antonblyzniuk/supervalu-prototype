import type { Store } from '@/types/api'

export type DocketType = 'ambient' | 'chilled' | 'returns' | 'transfer'
export type DocketShape = 'categories' | 'items'

export interface DocketColumn {
  key: string
  label: string
}

export interface SignatureRole {
  value: string
  label: string
}

export interface DocketTypeMeta {
  value: DocketType
  label: string
  shape: DocketShape
  columns: DocketColumn[]
  signature_roles: SignatureRole[]
}

export interface DocketMeta {
  types: DocketTypeMeta[]
  current_week: { start: string; end: string }
}

export interface DocketLine {
  id?: number
  position: number
  line_date?: string | null
  supplier?: string
  docket_number?: string
  amounts?: Record<string, string>
  comments?: string
  quantity?: string
  description?: string
  cost_price?: string | null
  retail_price?: string | null
  total?: string
  /** Client-only: the user typed a total, so stop auto-filling it. Stripped on submit. */
  totalTouched?: boolean
}

export interface DocketSignature {
  id?: number
  role: string
  signed_name?: string
  /** A URL when read back from the API, a data URL when being submitted. */
  image: string
}

export interface DocketPhoto {
  id?: number
  image: string
  caption?: string
  captured_at?: string | null
}

export interface Docket {
  id: string
  docket_type: DocketType
  docket_type_display: string
  store: string
  store_detail: Store
  destination_store: string | null
  destination_store_detail: Store | null
  week_ending: string | null
  docket_date: string | null
  effective_date: string
  reference: string
  docket_number: string
  department: string
  supplier: string
  reason: string
  outgoing_staff_name: string
  manager_name: string
  notes: string
  total: string
  category_totals: Record<string, string>
  lines: DocketLine[]
  signatures: DocketSignature[]
  photos: DocketPhoto[]
  created_by_email?: string
  created_at: string
  updated_at: string
}

export interface DocketListItem {
  id: string
  docket_type: DocketType
  docket_type_display: string
  store_detail: Store
  destination_store_detail: Store | null
  week_ending: string | null
  docket_date: string | null
  effective_date: string
  reference: string
  docket_number: string
  supplier: string
  manager_name: string
  total: string
  line_count: number
  photo_count: number
  created_at: string
}

export interface DocketFilters {
  store?: string[]
  docket_type?: DocketType[]
  date_from?: string
  date_to?: string
  week_of?: string
  q?: string
  ordering?: string
  page?: number
}

export interface TypeSummary {
  docket_type: DocketType
  label: string
  columns: DocketColumn[]
  docket_count: number
  line_count: number
  total: string
  category_totals: Record<string, string>
}

export interface StoreSummary {
  store: { slug: string; name: string; code: string }
  docket_count: number
  total: string
  by_type: Record<DocketType, string>
}

export interface DocketSummary {
  docket_count: number
  grand_total: string
  by_type: TypeSummary[]
  by_store: StoreSummary[]
}

/** The shape the form works with before it is posted. */
export interface DocketDraft {
  docket_type: DocketType
  store: string
  destination_store: string | null
  week_ending: string
  docket_date: string
  reference: string
  docket_number: string
  department: string
  supplier: string
  reason: string
  outgoing_staff_name: string
  manager_name: string
  notes: string
  lines: DocketLine[]
  signatures: DocketSignature[]
  photos: DocketPhoto[]
}
