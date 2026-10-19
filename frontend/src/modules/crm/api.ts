/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { apiFetch } from '../../api/client'

export const API_BASE = '/api/modules/crm'
export const CRM_PATH = '/crm'
/** Mirrors the backend's cap (app/modules/crm/storage.py) so an oversized file is refused before it is sent. */
export const MAX_INVOICE_BYTES = 10 * 1024 * 1024

export const TASK_STATUSES = ['new', 'in_progress', 'done', 'invoiced', 'paid', 'cancelled'] as const
export type TaskStatus = (typeof TASK_STATUSES)[number]

export interface Partner {
  id: string
  name: string
  company: string | null
  company_id: string | null
  vat_id: string | null
  address: string
  email: string | null
  phone: string | null
  notes: string
  archived: boolean
  created_at: string
  updated_at: string
}

export interface PartnerListItem extends Partner {
  task_count: number
}

export interface Task {
  id: string
  partner_id: string
  title: string
  description: string
  status: TaskStatus
  /** Decimal serialized as a string ("1500.00"), or null when no price is set. */
  price: string | null
  currency: string
  /** ISO date (YYYY-MM-DD), no time. */
  start_date: string | null
  due_date: string | null
  created_at: string
  updated_at: string
}

export interface TaskListItem extends Task {
  invoice_count: number
}

export interface Invoice {
  id: string
  task_id: string
  number: string | null
  original_filename: string
  size_bytes: number
  uploaded_at: string
}

export interface TaskDetail extends Task {
  partner: { id: string; name: string; company: string | null }
  invoices: Invoice[]
}

/** A non-2xx answer; `status` lets callers pick their own translated message. */
export class ApiError extends Error {
  status: number
  constructor(status: number) {
    super(`HTTP ${status}`)
    this.status = status
  }
}

export async function fetchJson<T>(path: string, init?: Parameters<typeof apiFetch>[1]): Promise<T> {
  const resp = await apiFetch(path, init)
  if (!resp.ok) throw new ApiError(resp.status)
  return resp.status === 204 ? (undefined as T) : resp.json()
}

export function sendJson<T>(path: string, method: 'POST' | 'PATCH', body: unknown): Promise<T> {
  return fetchJson<T>(path, { method, body: JSON.stringify(body) })
}

export function deleteRequest(path: string): Promise<void> {
  return fetchJson<void>(path, { method: 'DELETE' })
}

export function errorStatus(error: unknown): number | null {
  return error instanceof ApiError ? error.status : null
}

export const partnerPath = (id: string) => `${CRM_PATH}/partners/${id}`
export const taskPath = (id: string) => `${CRM_PATH}/tasks/${id}`

/**
 * A plain "YYYY-MM-DD" date is shown as that local date - new Date("YYYY-MM-DD")
 * would parse it as UTC midnight and can show the previous day. A full
 * timestamp (uploaded_at) is an instant, shown in the viewer's own time zone.
 */
export function formatDate(iso: string | null, language: string): string {
  if (!iso) return '—'
  let date: Date
  if (iso.length > 10) {
    date = new Date(iso)
  } else {
    const [y, m, d] = iso.split('-').map(Number)
    date = new Date(y, m - 1, d)
  }
  return date.toLocaleDateString(language, { day: 'numeric', month: 'numeric', year: 'numeric' })
}

export function formatPrice(price: string | null, currency: string, language: string): string {
  if (price === null) return '—'
  try {
    return new Intl.NumberFormat(language, { style: 'currency', currency }).format(Number(price))
  } catch {
    return `${price} ${currency}`
  }
}

export function formatFileSize(bytes: number, language: string): string {
  const number = (value: number) => value.toLocaleString(language, { maximumFractionDigits: 1 })
  if (bytes < 1024) return `${number(bytes)} B`
  if (bytes < 1024 * 1024) return `${number(bytes / 1024)} kB`
  return `${number(bytes / (1024 * 1024))} MB`
}

/**
 * Invoice files are private: the download route needs the bearer token, so a
 * plain link can't work. Fetch the PDF with it and hand the blob to the
 * browser as a file download.
 */
export async function downloadInvoice(invoice: Invoice): Promise<void> {
  const resp = await apiFetch(`${API_BASE}/invoices/${invoice.id}/file`)
  if (!resp.ok) throw new ApiError(resp.status)
  const url = URL.createObjectURL(await resp.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = invoice.original_filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  // Not at once: some browsers start reading the blob only after click() returns.
  setTimeout(() => URL.revokeObjectURL(url), 10_000)
}
