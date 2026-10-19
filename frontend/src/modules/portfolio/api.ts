/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import { apiFetch } from '../../api/client'

export const API_BASE = '/api/modules/portfolio'
export const PORTFOLIO_PATH = '/portfolio'
export const MANAGE_PATH = '/portfolio/manage'

/** Mirrors the backend's limits (app/modules/portfolio/schemas.py), so the form says what the server will refuse. */
export const LIMITS = { title: 120, summary: 400, description: 8000, url: 500, slug: 80, tags: 10, tag: 40 } as const

export const ITEM_STATUSES = ['live', 'in_preparation'] as const
export type ItemStatus = (typeof ITEM_STATUSES)[number]

/** One item of the public list - the texts already in the requested language. */
export interface PublicItem {
  slug: string
  title: string
  summary: string
  url: string | null
  status: ItemStatus
  tags: string[]
}

export interface PublicItemDetail extends PublicItem {
  description: string
}

/** Everything about an item, both languages - what the administrator's endpoints return. */
export interface AdminItem {
  id: string
  slug: string
  title_cs: string
  title_en: string
  summary_cs: string
  summary_en: string
  description_cs: string
  description_en: string
  url: string | null
  status: ItemStatus
  tags: string[]
  published: boolean
  sort_order: number
  created_at: string
  updated_at: string
}

/** The fields the form sends (create) or may send (partial update). */
export type ItemInput = Partial<Omit<AdminItem, 'id' | 'sort_order' | 'created_at' | 'updated_at'>>

/** A non-2xx answer: `status` lets callers pick their own translated message, `body` is the parsed JSON (if any). */
export class ApiError extends Error {
  status: number
  body: unknown
  constructor(status: number, body: unknown = null) {
    super(`HTTP ${status}`)
    this.status = status
    this.body = body
  }
}

export async function fetchJson<T>(path: string, init?: Parameters<typeof apiFetch>[1]): Promise<T> {
  const resp = await apiFetch(path, init)
  if (!resp.ok) throw new ApiError(resp.status, await resp.json().catch(() => null))
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

export const itemPath = (slug: string) => `${PORTFOLIO_PATH}/${encodeURIComponent(slug)}`
export const editPath = (id: string) => `${MANAGE_PATH}/${id}`

/** The language the public endpoints are asked for - and refetched on when it changes. */
export function usePublicLanguage(): string {
  const { i18n } = useTranslation()
  return i18n.resolvedLanguage ?? i18n.language
}

/** The backend only stores http(s) URLs; checked again here because the value ends up in an href. */
export const isWebUrl = (url: string | null | undefined): url is string => !!url && /^https?:\/\//i.test(url)

/** A text for a <meta> description: one line, cut on a word boundary when it is long. */
export function metaText(text: string, max = 160): string {
  const line = text.replace(/\s+/g, ' ').trim()
  if (line.length <= max) return line
  const cut = line.slice(0, max - 1)
  const space = cut.lastIndexOf(' ')
  return `${space >= max / 2 ? cut.slice(0, space) : cut}…`
}

/** Paragraphs of a description: a blank line separates them (single line breaks stay inside a paragraph). */
export function paragraphsOf(text: string): string[] {
  return text
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean)
}

/** One field's problem in a 422 answer, as a translation key plus its interpolation values. */
export interface FieldProblem {
  key: string
  values?: Record<string, unknown>
}

/**
 * Turns FastAPI's 422 body (`detail: [{loc: ['body', field, ...], type, ctx}]`)
 * into a problem per field, so the form can say it in the visitor's language
 * under the right control instead of showing the server's English text.
 */
export function fieldProblems(body: unknown): Record<string, FieldProblem> {
  const detail = (body as { detail?: unknown } | null)?.detail
  const problems: Record<string, FieldProblem> = {}
  if (!Array.isArray(detail)) return problems
  for (const entry of detail as { loc?: unknown[]; type?: string; ctx?: { max_length?: number } }[]) {
    const field = entry.loc?.[1]
    if (typeof field !== 'string' || field in problems) continue
    if (entry.type === 'string_too_long') {
      problems[field] = { key: 'form.errors.tooLong', values: { max: entry.ctx?.max_length } }
    } else if (entry.type === 'string_too_short' || entry.type === 'missing') {
      problems[field] = { key: 'form.errors.required' }
    } else if (field === 'slug' || field === 'url' || field === 'tags') {
      problems[field] = { key: `form.errors.${field}`, values: { maxTags: LIMITS.tags, maxTag: LIMITS.tag, maxSlug: LIMITS.slug } }
    } else {
      problems[field] = { key: 'form.errors.invalid' }
    }
  }
  return problems
}
