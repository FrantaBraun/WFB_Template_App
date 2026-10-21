/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { apiFetch } from '../../api/client'

export const API_BASE = '/api/modules/pub_menu'
export const MENU_PATH = '/menu'
export const MANAGE_PATH = '/menu/manage'

export type CategoryKind = 'food' | 'drink'
export type DailyKind = 'soup' | 'main' | 'dessert' | 'other'

export const DAILY_KINDS: DailyKind[] = ['soup', 'main', 'dessert', 'other']
/** The EU allergen numbers (regulation 1169/2011). */
export const ALLERGENS = Array.from({ length: 14 }, (_, index) => index + 1)

/** One price of an item, with the portion it is for ("0,5 l", "150 g", or empty). */
export interface Price {
  label: string
  price: number
}

export interface OfferItem {
  id: string
  name: string
  description: string
  allergens: number[]
  /** False = temporarily sold out: shown, but marked. */
  is_available: boolean
  prices: Price[]
}

export interface OfferCategory {
  id: string
  name: string
  description: string
  kind: CategoryKind
  items: OfferItem[]
}

export interface Offer {
  currency: string
  note: string
  categories: OfferCategory[]
}

export interface DailyItem {
  id: string
  kind: DailyKind
  name: string
  description: string
  amount: string
  allergens: number[]
  /** null = included in the price of another dish (a soup with a main course, say). */
  price: number | null
}

export interface DailyDay {
  day: string
  items: DailyItem[]
}

export interface DailyWeek {
  currency: string
  note: string
  week_start: string
  week_end: string
  min_week_start: string
  max_week_start: string
  days: DailyDay[]
}

export interface ItemAdmin extends OfferItem {
  category_id: string
  is_active: boolean
  position: number
}

export interface CategoryAdmin {
  id: string
  name: string
  description: string
  kind: CategoryKind
  position: number
  is_active: boolean
  items: ItemAdmin[]
}

export interface DailyAdmin {
  day: string
  is_published: boolean
  updated_at: string
  items: DailyItem[]
}

export interface Settings {
  daily_note: string
  offer_note: string
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
 * The field problems of a 422 answer: `{ field: code }`. FastAPI's own validation
 * answer is a list of { loc, msg }: each becomes "that field is invalid".
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

export function query(params: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') search.set(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

// --- Money -------------------------------------------------------------------------------------

/** "189 Kč", "57,50 Kč": whole amounts without decimals, the browser's own formatting for the language. */
export function formatPrice(value: number, currency: string, language: string): string {
  const whole = Number.isInteger(value)
  return new Intl.NumberFormat(language, {
    style: 'currency',
    currency,
    minimumFractionDigits: whole ? 0 : 2,
    maximumFractionDigits: 2,
  }).format(value)
}

/** The text of a price input as a number, or null when it is empty or not a number ("57,5" and "57.5" both work). */
export function parsePrice(text: string): number | null {
  const normalized = text.trim().replace(',', '.')
  if (normalized === '') return null
  const value = Number(normalized)
  return Number.isFinite(value) ? value : null
}

/** A price as it is typed into an input. */
export function priceText(value: number | null): string {
  return value === null ? '' : String(value).replace('.', ',')
}

// --- Dates (all local, no zones) -----------------------------------------------------------------

/** "YYYY-MM-DD" as a local date - new Date("YYYY-MM-DD") would be UTC midnight and can show the day before. */
export function parseDay(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function isoDay(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

export function addDays(iso: string, days: number): string {
  const date = parseDay(iso)
  date.setDate(date.getDate() + days)
  return isoDay(date)
}

/** The Monday of the week that contains the date. */
export function mondayOf(iso: string): string {
  const date = parseDay(iso)
  return addDays(iso, -((date.getDay() + 6) % 7))
}

export function weekdayName(iso: string, language: string): string {
  return parseDay(iso).toLocaleDateString(language, { weekday: 'long' })
}

export function shortDate(iso: string, language: string): string {
  return parseDay(iso).toLocaleDateString(language, { day: 'numeric', month: 'numeric' })
}

export function longDate(iso: string, language: string): string {
  return parseDay(iso).toLocaleDateString(language, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
}
