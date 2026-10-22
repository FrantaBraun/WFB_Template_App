/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { apiFetch } from '../../api/client'

export const API_BASE = '/api/modules/repository'
export const AREA_PATH = '/repository'

export const ATTRIBUTE_TYPES = ['text', 'number', 'boolean', 'date', 'datetime', 'image', 'reference', 'list', 'map'] as const
export type AttributeType = (typeof ATTRIBUTE_TYPES)[number]
/** What a list or map may hold: one simple type, never another list or map. */
export const ELEMENT_TYPES = ['text', 'number', 'boolean', 'date', 'datetime', 'image', 'reference'] as const
export type ElementType = (typeof ELEMENT_TYPES)[number]

export const PAGE_SIZES = [25, 50, 100] as const
/** Mirrors the backend's default (modules/repository.json) so an oversized file is refused before it is sent; the server has the last word. */
export const MAX_IMAGE_BYTES = 3 * 1024 * 1024
/** Images are scaled down to fit this many pixels before they are uploaded. */
export const MAX_IMAGE_SIDE = 1600
export const MAX_ELEMENTS = 200
export const MAX_TEXT_LENGTH = 5000

export interface Repository {
  id: string
  name: string
  description: string
  slug: string
  color_scheme: string
  created_at: string
  updated_at: string
  table_count: number
  /** Records that are not deleted, over all the tables. */
  record_count: number
}

export interface TableSummary {
  id: string
  name: string
  slug: string
  description: string
  view_type: 'table' | 'grid'
  position: number
  record_count: number
}

export interface RepositoryDetail extends Repository {
  tables: TableSummary[]
}

export interface AttributeConfig {
  /** For a reference, or a list/map of references: the table it points at. */
  table_id?: string
  /** For a list or map: the one simple type of its elements. */
  element_type?: ElementType
}

export interface Attribute {
  id: string
  name: string
  description: string
  type: AttributeType
  required: boolean
  show_in_list: boolean
  config: AttributeConfig
  position: number
}

export interface TableDetail extends TableSummary {
  attributes: Attribute[]
}

export interface RefInfo {
  name: string
  slug: string
  table_slug: string
  table_name: string
  deleted: boolean
}

/** A value as the server stores it: text, number, boolean, a date string, an image or record id, or a list/map object. */
export type StoredValue = unknown

export interface RepoRecord {
  id: string
  slug: string
  name: string
  created_on: string
  deleted_on: string | null
  data: Record<string, StoredValue>
  refs: Record<string, RefInfo>
}

export interface RecordListItem {
  id: string
  slug: string
  name: string
  created_on: string
  deleted_on: string | null
  values: Record<string, StoredValue>
}

export interface RecordPage {
  items: RecordListItem[]
  total: number
  page: number
  page_size: number
  refs: Record<string, RefInfo>
}

export interface RecordHit {
  id: string
  name: string
  slug: string
}

export interface RecordHitPage {
  items: RecordHit[]
  total: number
  page: number
  page_size: number
}

export interface ImageInfo {
  id: string
  mime: string
  size_bytes: number
}

export interface SlugCheck {
  slug: string
  available: boolean
  reason: 'invalid' | 'reserved' | 'taken' | null
  suggestion: string | null
}

/** A non-2xx answer: `status`, and the server's `detail` (see service.py: {errors}, {limit, max}, {purge_required}, {referenced_by}). */
export class ApiError extends Error {
  status: number
  detail: unknown
  constructor(status: number, detail: unknown) {
    super(`HTTP ${status}`)
    this.status = status
    this.detail = detail
  }
}

export async function fetchJson<T>(path: string, init?: Parameters<typeof apiFetch>[1]): Promise<T> {
  const resp = await apiFetch(path, init)
  if (!resp.ok) {
    let detail: unknown = null
    try {
      detail = (await resp.json()).detail
    } catch {
      // no JSON body: the status is all there is
    }
    throw new ApiError(resp.status, detail)
  }
  return resp.status === 204 ? (undefined as T) : resp.json()
}

export function sendJson<T>(path: string, method: 'POST' | 'PATCH' | 'PUT', body: unknown): Promise<T> {
  return fetchJson<T>(path, { method, body: JSON.stringify(body) })
}

export function deleteRequest(path: string): Promise<void> {
  return fetchJson<void>(path, { method: 'DELETE' })
}

export function errorStatus(error: unknown): number | null {
  return error instanceof ApiError ? error.status : null
}

function detailObject(error: unknown): Record<string, unknown> | null {
  if (!(error instanceof ApiError)) return null
  const detail = error.detail
  return detail !== null && typeof detail === 'object' && !Array.isArray(detail) ? (detail as Record<string, unknown>) : null
}

/** The `{field or attribute id: code}` map of a 422/409 answer, or {} when it has none. */
export function fieldErrors(error: unknown): Record<string, string> {
  const errors = detailObject(error)?.errors
  return errors !== null && typeof errors === 'object' ? (errors as Record<string, string>) : {}
}

/** The configured limit a 409 answer says was reached ("max_tables_per_repository", ...), if it says so. */
export function limitReached(error: unknown): { limit: string; max: number } | null {
  const detail = detailObject(error)
  return detail && typeof detail.limit === 'string' ? { limit: detail.limit, max: Number(detail.max) } : null
}

export function detailField<T>(error: unknown, key: string): T | null {
  const detail = detailObject(error)
  return detail && key in detail ? (detail[key] as T) : null
}

export const repositoryPath = (repository: string) => `${AREA_PATH}/${repository}`
export const tablesPath = (repository: string) => `${repositoryPath(repository)}/tables`
export const tablePath = (repository: string, table: string) => `${repositoryPath(repository)}/table/${table}`
export const recordPath = (repository: string, table: string, record: string) => `${tablePath(repository, table)}/item/${record}`

export const repositoryApi = (repository: string) => `${API_BASE}/repositories/${encodeURIComponent(repository)}`
export const tableApi = (repository: string, table: string) => `${repositoryApi(repository)}/tables/${encodeURIComponent(table)}`
export const recordApi = (repository: string, table: string, record?: string) =>
  `${tableApi(repository, table)}/records${record ? `/${encodeURIComponent(record)}` : ''}`

/** The elements of a stored list (an object keyed "0".."n-1"), in order. */
export function listValues(value: StoredValue): StoredValue[] {
  if (value === null || typeof value !== 'object') return []
  return Object.entries(value as Record<string, StoredValue>)
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([, element]) => element)
}

/** The [key, element] pairs of a stored map, in the order the server sent them. */
export function mapEntries(value: StoredValue): [string, StoredValue][] {
  return value !== null && typeof value === 'object' ? Object.entries(value as Record<string, StoredValue>) : []
}

/** The simple type a value of this attribute has: its own, or the element type of a list/map. */
export function elementTypeOf(attribute: Pick<Attribute, 'type' | 'config'>): ElementType {
  return (attribute.type === 'list' || attribute.type === 'map' ? attribute.config.element_type : attribute.type) as ElementType
}

/**
 * A plain "YYYY-MM-DD" date is shown as that local date - new Date("YYYY-MM-DD")
 * would parse it as UTC midnight and can show the previous day. "YYYY-MM-DDTHH:MM"
 * carries no zone and is shown as written. A full timestamp (created_on) is an
 * instant, shown in the viewer's own time zone.
 */
export function formatDate(iso: string | null, language: string): string {
  if (!iso) return '—'
  if (iso.length === 10) {
    const [y, m, d] = iso.split('-').map(Number)
    return new Date(y, m - 1, d).toLocaleDateString(language, { day: 'numeric', month: 'numeric', year: 'numeric' })
  }
  if (iso.length === 16) {
    const [datePart, timePart] = iso.split('T')
    const [y, m, d] = datePart.split('-').map(Number)
    const [hh, mm] = timePart.split(':').map(Number)
    return new Date(y, m - 1, d, hh, mm).toLocaleString(language, { dateStyle: 'short', timeStyle: 'short' })
  }
  return new Date(iso).toLocaleString(language, { dateStyle: 'short', timeStyle: 'short' })
}

export function formatNumber(value: number, language: string): string {
  return value.toLocaleString(language, { maximumFractionDigits: 10 })
}

export function formatFileSize(bytes: number, language: string): string {
  const number = (value: number) => value.toLocaleString(language, { maximumFractionDigits: 1 })
  if (bytes < 1024) return `${number(bytes)} B`
  if (bytes < 1024 * 1024) return `${number(bytes / 1024)} kB`
  return `${number(bytes / (1024 * 1024))} MB`
}

/** A new id for an attribute (the client chooses them, see the backend's replace_attributes). */
export function newId(): string {
  return crypto.randomUUID()
}

/** Slug the way the backend makes it (logic.slugify), so the field can show what will be generated. */
export function slugify(text: string): string {
  const letters: Record<string, string> = { ł: 'l', đ: 'd', ø: 'o', ð: 'd', ß: 'ss', æ: 'ae', œ: 'oe', þ: 'th' }
  const plain = text
    .toLowerCase()
    .replace(/[łđøðßæœþ]/g, (char) => letters[char])
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
  return plain.replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 80).replace(/-+$/, '')
}
