/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { apiFetch } from '../../api/client'

export const API_BASE = '/api/modules/table_reservations'
export const RESERVATIONS_PATH = '/reservations'
export const MANAGE_PATH = '/reservations/manage'

export type Kind = 'table' | 'whole_venue'
export type Status = 'confirmed' | 'cancelled'

/** The regular hours of one weekday (Monday = 0); times are "HH:MM:SS" or null when closed. */
export interface WeekdayHours {
  weekday: number
  is_closed: boolean
  opens: string | null
  closes: string | null
}

/** A one-off change of one date; `reason` is shown to visitors. */
export interface ExceptionDay {
  day: string
  is_closed: boolean
  opens: string | null
  closes: string | null
  reason: string | null
}

/** What the reservation form needs to know before the guest picks a day. */
export interface Info {
  weekly: WeekdayHours[]
  exceptions: ExceptionDay[]
  /** The most people one table seats (0 = no active table) and the most the whole pub is reserved for. */
  max_party_size: number
  max_whole_venue_party: number
  max_days_ahead: number
  lead_minutes: number
  default_duration: number
  duration_options: number[]
  min_duration: number
  step_minutes: number
  privacy_url: string | null
  can_reserve: boolean
}

export interface DayInfo {
  day: string
  is_open: boolean
  opens: string | null
  closes: string | null
  reason: string | null
  /** Whether a guest may reserve on this day (open, not past, not too far ahead). */
  bookable: boolean
}

export interface Availability {
  day: string
  is_open: boolean
  bookable: boolean
  opens: string | null
  closes: string | null
  reason: string | null
  /** Every start at which a table is free for the party and the duration asked. */
  starts: string[]
  /** Why there is none: party_too_large, venue_reserved, no_table, too_soon. */
  table_reason: string | null
  whole_venue_from: string | null
  /** Why the whole pub cannot be reserved: venue_reserved, tables_reserved, too_soon. */
  whole_venue_reason: string | null
}

export interface Created {
  cancel_token: string
  kind: Kind
  day: string
  start_time: string
  end_time: string
}

export interface ReservationPublic {
  kind: Kind
  day: string
  start_time: string
  end_time: string
  party_size: number
  name: string
  status: Status
  cancelled_at: string | null
}

export interface ReservationAdmin {
  id: string
  kind: Kind
  table_id: string | null
  table_name: string | null
  day: string
  start_time: string
  end_time: string
  party_size: number
  name: string
  email: string
  phone: string | null
  note: string | null
  language: string
  consent_at: string
  created_at: string
  status: Status
  cancelled_at: string | null
  cancelled_by: 'guest' | 'admin' | null
  cancel_note: string | null
  notified: boolean | null
  email_error: string | null
}

/** The answer to the pub cancelling: `email_sent` is null when no e-mail was asked for. */
export interface CancelResult {
  reservation: ReservationAdmin
  email_sent: boolean | null
}

export interface TableRow {
  id: string
  name: string
  seats: number
  position: number
  is_active: boolean
  upcoming_count: number
}

/** The reservations that stand in the way of a change (a 409 answer lists them). */
export interface Conflict {
  reservations: ReservationAdmin[]
  total: number
}

/** The error of a failed request: its HTTP status and the `detail` the server sent. */
export interface ApiError extends Error {
  status: number
  detail: unknown
}

export async function fetchJson<T>(path: string, init?: Parameters<typeof apiFetch>[1]): Promise<T> {
  const resp = await apiFetch(path, init)
  if (!resp.ok) {
    let detail: unknown = null
    try {
      detail = (await resp.json()).detail
    } catch {
      // not JSON
    }
    throw Object.assign(new Error(`HTTP ${resp.status}`), { status: resp.status, detail }) as ApiError
  }
  return resp.status === 204 ? (undefined as T) : resp.json()
}

export function sendJson<T>(path: string, method: 'POST' | 'PATCH' | 'PUT', body: unknown): Promise<T> {
  return fetchJson<T>(path, { method, body: JSON.stringify(body) })
}

/** The status of a failed request (0 when it never got an answer). */
export function statusOf(error: unknown): number {
  return (error as Partial<ApiError> | null)?.status ?? 0
}

/**
 * The field problems of a 422 / 409 answer: `{ field: code }`. `_form` is a problem
 * with the whole request. FastAPI's own validation answer (a malformed e-mail
 * address, say) is a list of { loc, msg }: each becomes "that field is invalid".
 */
export function errorsOf(error: unknown): Record<string, string> {
  const detail = (error as Partial<ApiError> | null)?.detail
  if (detail && typeof detail === 'object' && !Array.isArray(detail) && 'errors' in detail) {
    const errors = (detail as { errors: unknown }).errors
    if (errors && typeof errors === 'object') return errors as Record<string, string>
  }
  if (Array.isArray(detail)) {
    const found: Record<string, string> = {}
    for (const item of detail) {
      const loc = (item as { loc?: unknown })?.loc
      const field = Array.isArray(loc) ? loc[loc.length - 1] : undefined
      if (typeof field === 'string') found[field] = 'invalid'
    }
    return found
  }
  return {}
}

/** The reservations a 409 answer says stand in the way, or null when the error is not that. */
export function conflictOf(error: unknown): Conflict | null {
  if (statusOf(error) !== 409) return null
  const detail = (error as Partial<ApiError> | null)?.detail as { reservations?: ReservationAdmin[]; total?: number } | null
  if (!detail || !Array.isArray(detail.reservations)) return null
  return { reservations: detail.reservations, total: detail.total ?? detail.reservations.length }
}

export function query(params: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') search.set(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

// --- Dates and times (all local, no zones) -------------------------------------------------------

const LONG_DATE: Intl.DateTimeFormatOptions = { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }
const SHORT_DATE: Intl.DateTimeFormatOptions = { weekday: 'short', day: 'numeric', month: 'numeric', year: 'numeric' }

/** "YYYY-MM-DD" as a local date - new Date("YYYY-MM-DD") would be UTC midnight and can show the day before. */
export function parseDay(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function isoDay(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

export function isoMonth(year: number, month: number): string {
  return `${year}-${String(month + 1).padStart(2, '0')}`
}

export function addDays(iso: string, days: number): string {
  const date = parseDay(iso)
  date.setDate(date.getDate() + days)
  return isoDay(date)
}

export function formatDay(iso: string, language: string, style: 'long' | 'short' = 'long'): string {
  return parseDay(iso).toLocaleDateString(language, style === 'long' ? LONG_DATE : SHORT_DATE)
}

/** "18:00:00" from the server -> "18:00". */
export function formatTime(time: string): string {
  return time.slice(0, 5)
}

export function toMinutes(time: string): number {
  const [h, m] = time.split(':').map(Number)
  return h * 60 + m
}

export function fromMinutes(value: number): string {
  return `${String(Math.floor(value / 60)).padStart(2, '0')}:${String(value % 60).padStart(2, '0')}`
}

/** "2 h", "1 h 30 min", "45 min". */
export function formatDuration(minutes: number): string {
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  if (hours === 0) return `${rest} min`
  return rest === 0 ? `${hours} h` : `${hours} h ${rest} min`
}

export function formatDateTime(iso: string, language: string): string {
  return new Date(iso).toLocaleString(language, { dateStyle: 'medium', timeStyle: 'short' })
}

/** The name of a weekday (Monday = 0) in the language. 2024-01-01 was a Monday. */
export function weekdayName(weekday: number, language: string, style: 'long' | 'short' = 'long'): string {
  return new Date(2024, 0, 1 + weekday).toLocaleDateString(language, { weekday: style })
}
