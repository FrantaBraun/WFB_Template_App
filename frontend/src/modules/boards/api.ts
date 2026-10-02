/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { apiFetch } from '../../api/client'

export const API_BASE = '/api/modules/boards'
export const CATEGORIES_PATH = '/categories'

// The backend's text limits (app/modules/boards/models.py), in characters.
export const CATEGORY_TITLE_MAX = 120
export const CATEGORY_DESCRIPTION_MAX = 4096
export const POST_TITLE_MAX = 120
export const POST_BODY_MAX = 2048

export interface Category {
  id: string
  title: string
  slug: string
  description: string
  post_count: number
  created_at: string
}

/** What a visitor sees of a post: no author, and resonance only as a count. */
export interface Post {
  id: string
  title: string
  body: string
  value: number
  resonance_count: number
  /** The viewer's own resonance; always false when signed out. */
  resonated_by_me: boolean
  created_at: string
}

export interface Page<T> {
  items: T[]
  has_more: boolean
}

export class ApiError extends Error {
  status: number
  constructor(status: number) {
    super(`HTTP ${status}`)
    this.status = status
  }
}

export function categoryPath(slug: string): string {
  return `${CATEGORIES_PATH}/${slug}`
}

/**
 * Length the way the backend counts it: characters (code points), after
 * trimming and with line breaks as one - so an emoji counts once, where
 * String.length (and a textarea's maxLength) would count it twice.
 */
export function charCount(text: string): number {
  return Array.from(text.replace(/\r\n?/g, '\n').trim()).length
}

export async function fetchJson<T>(path: string, init?: Parameters<typeof apiFetch>[1]): Promise<T> {
  const resp = await apiFetch(path, init)
  if (!resp.ok) throw new ApiError(resp.status)
  return resp.json()
}

export function postJson<T>(path: string, body?: unknown): Promise<T> {
  return fetchJson<T>(path, { method: 'POST', ...(body === undefined ? {} : { body: JSON.stringify(body) }) })
}
