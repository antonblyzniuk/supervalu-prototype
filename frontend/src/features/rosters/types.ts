export interface ShiftInput {
  user_id: number
  date: string
  /** "HH:MM" — the API accepts what an `<input type="time">` produces. */
  start_time: string
  end_time: string
  break_minutes?: number
  break_paid?: boolean
  notes?: string
}

export type ShiftUpdate = Partial<Omit<ShiftInput, 'user_id'>>

/** What the shift editor is currently working on — one person, one day. */
export interface ShiftTarget {
  personId: number
  personName: string
  date: string
  /** Present when editing rather than adding. */
  shiftId?: number
}

/** The times the shift editor opens with. */
export interface ShiftDefaults {
  start: string
  end: string
  breakMinutes: number
  breakPaid: boolean
}

/**
 * A standard retail day, until the manager saves something else — after that
 * the last shift they entered becomes the starting point for the next.
 *
 * Lives here rather than beside the modal so that file only exports a
 * component, which is what Fast Refresh needs.
 */
export const INITIAL_DEFAULTS: ShiftDefaults = {
  start: '08:00',
  end: '17:00',
  breakMinutes: 30,
  breakPaid: false,
}
