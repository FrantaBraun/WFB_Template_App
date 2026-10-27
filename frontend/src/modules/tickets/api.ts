/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { apiFetch } from '../../api/client'

/** Every administrator endpoint of the module lives under /manage; only the pictures' address is public. */
export const API_BASE = '/api/modules/tickets/manage'
export const CRM_API_BASE = '/api/modules/crm'
export const TICKETS_PATH = '/tickets'
/** Mirror the backend's caps (app/modules/tickets/storage.py) so an oversized file is refused before it is sent. */
export const MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
export const MAX_IMAGE_BYTES = 5 * 1024 * 1024
export const MAX_ATTACHMENTS_PER_ENTRY = 10
/** One entry's time is capped at a week of work (MAX_ENTRY_MINUTES in the backend's models.py). */
export const MAX_ENTRY_MINUTES = 7 * 24 * 60

export const TICKET_TYPES = ['general', 'issue', 'order', 'internal'] as const
export type TicketType = (typeof TICKET_TYPES)[number]
export const TICKET_STATUSES = ['open', 'closed'] as const
export type TicketStatus = (typeof TICKET_STATUSES)[number]
export type TicketSource = 'manual' | 'email' | 'contact_form'
export type EntryKind = 'note' | 'incoming' | 'outgoing'

export interface PartnerRef {
  id: string
  name: string
  company: string | null
  archived: boolean
}

export interface Ticket {
  id: string
  number: number
  subject: string
  type: TicketType
  status: TicketStatus
  source: TicketSource
  requester_name: string | null
  requester_email: string | null
  partner_id: string | null
  partner: PartnerRef | null
  /** Sum of the time of every entry, in minutes. */
  total_minutes: number
  created_at: string
  updated_at: string
  last_activity_at: string
}

export interface TicketListItem extends Ticket {
  entry_count: number
}

export interface TicketPage {
  items: TicketListItem[]
  total: number
  page: number
  page_size: number
}

export interface Attachment {
  id: string
  original_filename: string
  content_type: string
  size_bytes: number
  is_inline: boolean
  created_at: string
}

export interface Entry {
  id: string
  kind: EntryKind
  /** Already sanitized by the backend. */
  content_html: string
  minutes: number
  author_label: string | null
  from_name: string | null
  from_address: string | null
  to_address: string | null
  email_subject: string | null
  created_at: string
  attachments: Attachment[]
}

export interface TicketDetail extends Ticket {
  entries: Entry[]
}

export interface MailboxStatus {
  configured: boolean
  address: string | null
  poll_seconds: number
  last_checked_at: string | null
  last_error: string | null
  last_result: { fetched: number; created: number; attached: number; skipped: number; failed: number } | null
}

/** A CRM partner as the picker needs it (a subset of what GET /api/modules/crm/partners returns). */
export interface PartnerOption {
  id: string
  name: string
  company: string | null
  email: string | null
}

/**
 * A non-2xx answer. `code` is the backend's short `detail` code when it sent
 * one ("email_failed", "no_requester_email", ...), so callers can pick a
 * translated message; `status` is the fallback.
 */
export class ApiError extends Error {
  status: number
  code: string | null
  constructor(status: number, code: string | null = null) {
    super(`HTTP ${status}${code ? ` ${code}` : ''}`)
    this.status = status
    this.code = code
  }
}

async function errorFrom(resp: Response): Promise<ApiError> {
  let code: string | null = null
  try {
    const body = await resp.json()
    if (typeof body?.detail === 'string') code = body.detail
  } catch {
    // not JSON - the status alone will do
  }
  return new ApiError(resp.status, code)
}

export async function fetchJson<T>(path: string, init?: Parameters<typeof apiFetch>[1]): Promise<T> {
  const resp = await apiFetch(path, init)
  if (!resp.ok) throw await errorFrom(resp)
  return resp.status === 204 ? (undefined as T) : resp.json()
}

export function sendJson<T>(path: string, method: 'POST' | 'PATCH', body: unknown): Promise<T> {
  return fetchJson<T>(path, { method, body: JSON.stringify(body) })
}

export function deleteRequest(path: string): Promise<void> {
  return fetchJson<void>(path, { method: 'DELETE' })
}

export function errorCode(error: unknown): string | null {
  return error instanceof ApiError ? error.code : null
}

export function errorStatus(error: unknown): number | null {
  return error instanceof ApiError ? error.status : null
}

export const ticketPath = (number: number) => `${TICKETS_PATH}/${number}`
export const partnerPath = (id: string) => `/crm/partners/${id}`

/** Uploads a picture for the text of an entry; resolves to its address (what the editor puts in the text). */
export function uploadTicketImage(number: number): (file: File) => Promise<string> {
  return async (file) => {
    const form = new FormData()
    form.append('file', file)
    const { url } = await fetchJson<{ url: string }>(`${API_BASE}/${number}/images`, { method: 'POST', body: form })
    return url
  }
}

/** Uploads a file for the next entry; it stays unattached until the entry names it. */
export function uploadAttachment(number: number, file: File): Promise<Attachment> {
  const form = new FormData()
  form.append('file', file)
  return fetchJson<Attachment>(`${API_BASE}/${number}/attachments`, { method: 'POST', body: form })
}

/**
 * Attachments are private: the download route needs the bearer token, so a
 * plain link can't work. Fetch the file with it and hand the blob to the
 * browser as a file download.
 */
export async function downloadAttachment(attachment: Attachment): Promise<void> {
  const resp = await apiFetch(`${API_BASE}/attachments/${attachment.id}/file`)
  if (!resp.ok) throw await errorFrom(resp)
  const url = URL.createObjectURL(await resp.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = attachment.original_filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  // Not at once: some browsers start reading the blob only after click() returns.
  setTimeout(() => URL.revokeObjectURL(url), 10_000)
}

/**
 * The time an administrator typed as minutes, or null when it is not a time.
 * Accepted: "90" (minutes), "1:30", "1h", "1h 30m", "45m", "1.5h" / "1,5h";
 * an empty field is 0. At most MAX_ENTRY_MINUTES.
 */
export function parseMinutes(input: string): number | null {
  const text = input.trim().toLowerCase().replace(',', '.')
  if (text === '') return 0
  let minutes: number | null = null
  let match: RegExpMatchArray | null
  if ((match = text.match(/^(\d+)$/))) {
    minutes = Number(match[1])
  } else if ((match = text.match(/^(\d+):(\d{1,2})$/))) {
    minutes = Number(match[2]) < 60 ? Number(match[1]) * 60 + Number(match[2]) : null
  } else if ((match = text.match(/^(?:(\d+(?:\.\d+)?)\s*h)?\s*(?:(\d+)\s*m(?:in)?)?$/))) {
    if (match[1] === undefined && match[2] === undefined) return null
    minutes = Math.round(Number(match[1] ?? 0) * 60 + Number(match[2] ?? 0))
  }
  return minutes !== null && minutes <= MAX_ENTRY_MINUTES ? minutes : null
}

/** 95 -> { hours: 1, minutes: 35 }; shown by the caller in the viewer's language. */
export function splitMinutes(total: number): { hours: number; minutes: number } {
  return { hours: Math.floor(total / 60), minutes: total % 60 }
}

/** An instant in the viewer's own time zone. */
export function formatDateTime(iso: string, language: string): string {
  return new Date(iso).toLocaleString(language, { day: 'numeric', month: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export function formatDate(iso: string, language: string): string {
  return new Date(iso).toLocaleDateString(language, { day: 'numeric', month: 'numeric', year: 'numeric' })
}

export function formatFileSize(bytes: number, language: string): string {
  const number = (value: number) => value.toLocaleString(language, { maximumFractionDigits: 1 })
  if (bytes < 1024) return `${number(bytes)} B`
  if (bytes < 1024 * 1024) return `${number(bytes / 1024)} kB`
  return `${number(bytes / (1024 * 1024))} MB`
}
