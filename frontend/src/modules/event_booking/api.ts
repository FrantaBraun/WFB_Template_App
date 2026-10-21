/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { apiFetch } from '../../api/client'
import type { Question, SubmissionEntry } from '../forms'

export const API_BASE = '/api/modules/event_booking'
export const BOOKINGS_PATH = '/bookings'

export type Access = 'public' | 'authenticated' | 'link'
export type DaysMode = 'dates' | 'weekdays' | 'any_future'
export type TimeMode = 'all_day' | 'manual' | 'generated'
export type BookingStatus = 'confirmed' | 'cancelled'

/** What the event list is told about an event's registration. */
export interface RegistrationBrief {
  event_id: string
  registration_id: string
  name: string
  description: string
  access: Access
  /** Whether people can register right now (open, article published, event not over). */
  is_open: boolean
  requires_login: boolean
}

export interface RegistrationPublic {
  id: string
  event_id: string
  event_title: string
  name: string
  description: string
  access: Access
  is_open: boolean
  requires_login: boolean
  /** Every block is a list of days: offer them as a list, not a calendar. */
  finite_days: boolean
  privacy_url: string | null
  max_days_ahead: number
  questions: Question[]
}

export interface FreeDay {
  date: string
  free_slots: number
}

/** A time of a day with room left; `time` null is the whole day. */
export interface SlotInfo {
  time: string | null
  capacity: number
  free: number
}

export interface BookingCreated {
  cancel_token: string
  slot_date: string
  slot_time: string | null
}

export interface BookingPublic {
  event_title: string
  registration_name: string
  slot_date: string
  slot_time: string | null
  name: string
  status: BookingStatus
  cancelled_at: string | null
}

/** One block of a registration's offer (see backend slots.py). Dates and times are ISO strings. */
export interface Block {
  days_mode: DaysMode
  dates: string[]
  weekdays: number[]
  range_from: string | null
  range_to: string | null
  time_mode: TimeMode
  times: string[]
  slot_minutes: number | null
  time_from: string | null
  time_to: string | null
  capacity: number | null
}

export interface RegistrationAdmin {
  id: string
  event_id: string
  event_title: string
  event_start_date: string
  event_end_date: string | null
  event_start_time: string | null
  event_end_time: string | null
  article_id: string
  article_slug: string
  name: string
  description: string
  access: Access
  link_token: string
  capacity: number
  form_id: string
  is_open: boolean
  blocks: (Block & { id: string; position: number })[]
  confirmed_count: number
  cancelled_count: number
  created_at: string
  updated_at: string
}

export interface RegistrationListItem {
  id: string
  event_id: string
  event_title: string
  event_start_date: string
  event_end_date: string | null
  name: string
  access: Access
  is_open: boolean
  confirmed_count: number
  cancelled_count: number
}

export interface BookingRow {
  id: string
  slot_date: string
  slot_time: string | null
  name: string
  email: string
  status: BookingStatus
  created_at: string
  has_history: boolean
}

export interface BookingRowPage {
  items: BookingRow[]
  total: number
}

/** What an administrator's change recorded: only the fields that changed, and for answers just which questions. */
export interface BookingChange {
  id: string
  kind: 'updated' | 'cancelled'
  note: string | null
  changes: {
    name?: { from: string; to: string }
    email?: { from: string; to: string }
    slot_date?: { from: string; to: string }
    slot_time?: { from: string | null; to: string | null }
    status?: { from: string; to: string }
    answers?: { questions: { id: string; label: string }[] }
  }
  notified: boolean
  email_error: string | null
  user_sub: string | null
  created_at: string
}

export interface BookingDetail {
  id: string
  registration_id: string
  event_title: string
  registration_name: string
  slot_date: string
  slot_time: string | null
  name: string
  email: string
  user_sub: string | null
  language: string
  status: BookingStatus
  consent_at: string
  created_at: string
  updated_at: string
  cancelled_at: string | null
  answers: SubmissionEntry[]
  history: BookingChange[]
}

/** The answer to an administrator's change: `email_sent` is null when no e-mail was asked for. */
export interface BookingMutation {
  booking: BookingDetail
  email_sent: boolean | null
}

export interface PreviewResult {
  problems: string[]
  slots: { date: string; time: string | null; capacity: number }[]
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
 * The field problems of a 422 / 409 answer: `{ field_or_question_id: code }`,
 * where a code (or, for blocks, a list of sentences) says what is wrong. The
 * form puts each at its field; `_form` is a problem with the whole request.
 */
export function errorsOf(error: unknown): Record<string, string | string[]> {
  const detail = (error as Partial<ApiError> | null)?.detail
  if (detail && typeof detail === 'object' && 'errors' in detail) {
    const errors = (detail as { errors: unknown }).errors
    if (errors && typeof errors === 'object') return errors as Record<string, string | string[]>
  }
  // FastAPI's own validation answer (a malformed e-mail address, say) is a list of
  // { loc: ['body', field, ...], msg }: each becomes "that field is invalid".
  if (Array.isArray(detail)) {
    const found: Record<string, string> = {}
    for (const item of detail) {
      const loc = (item as { loc?: unknown })?.loc
      const field = Array.isArray(loc) ? loc[1] : undefined
      if (typeof field === 'string') found[field] = 'invalid'
    }
    return found
  }
  return {}
}

/** Only the plain codes (the question errors a form shows are strings). */
export function stringErrors(errors: Record<string, string | string[]>): Record<string, string> {
  return Object.fromEntries(Object.entries(errors).filter(([, value]) => typeof value === 'string')) as Record<string, string>
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

export function formatDay(iso: string, language: string, style: 'long' | 'short' = 'long'): string {
  return parseDay(iso).toLocaleDateString(language, style === 'long' ? LONG_DATE : SHORT_DATE)
}

/** "10:00:00" from the server -> "10:00". */
export function formatTime(time: string): string {
  return time.slice(0, 5)
}

/** The slot as one line: the day and, unless it is the whole day, the time. */
export function formatSlot(day: string, time: string | null, language: string, allDay: string): string {
  return `${formatDay(day, language, 'short')}, ${time ? formatTime(time) : allDay}`
}

export function formatDateTime(iso: string, language: string): string {
  return new Date(iso).toLocaleString(language, { dateStyle: 'medium', timeStyle: 'short' })
}

/** The address of a link registration: the article page with the secret in `?r=`. */
export function registrationLink(articleSlug: string, linkToken: string): string {
  return `${window.location.origin}/articles/${articleSlug}?r=${encodeURIComponent(linkToken)}`
}

/** Downloads a file the API serves behind the bearer token (a plain link could not send it). */
export async function downloadFile(path: string, filename: string): Promise<void> {
  const resp = await apiFetch(path)
  if (!resp.ok) throw Object.assign(new Error(`HTTP ${resp.status}`), { status: resp.status })
  const url = URL.createObjectURL(await resp.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
