/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import type { CSSProperties } from 'react'
import { apiFetch } from '../../api/client'
import type { MentionableItem } from '../../components/RichTextEditor'

export const API_BASE = '/api/modules/articles'
export const ARTICLES_PATH = '/articles'

export type ArticleStatus = 'draft' | 'published' | 'archived'

export interface ArticleType {
  id: string
  name: string
  border_light: string
  background_light: string
  border_dark: string
  background_dark: string
}

export interface ArticleTypeAdmin extends ArticleType {
  article_count: number
}

/** Listing shape - no content. */
export interface ArticleTeaser {
  id: string
  title: string
  slug: string
  perex: string
  image_url: string | null
  pinned: boolean
  status: ArticleStatus
  /** ISO timestamp. */
  created_at: string
  type: ArticleType | null
}

export interface ArticleDetail extends ArticleTeaser {
  /** Editor HTML the backend sanitized on save. */
  content: string
}

export interface ArticleAdminListItem extends ArticleTeaser {
  display_from: string | null
  display_to: string | null
  updated_at: string
}

export interface ArticleAdmin extends ArticleDetail {
  type_id: string | null
  display_from: string | null
  display_to: string | null
  updated_at: string
}

export interface Page<T> {
  items: T[]
  has_more: boolean
}

export function articlePath(slug: string): string {
  return `${ARTICLES_PATH}/${slug}`
}

export function formatDate(iso: string, language: string): string {
  return new Date(iso).toLocaleDateString(language, { day: 'numeric', month: 'long', year: 'numeric' })
}

export async function fetchJson<T>(path: string, init?: Parameters<typeof apiFetch>[1]): Promise<T> {
  const resp = await apiFetch(path, init)
  if (!resp.ok) throw Object.assign(new Error(`HTTP ${resp.status}`), { status: resp.status })
  return resp.status === 204 ? (undefined as T) : resp.json()
}

/** Uploads a thumbnail or in-text image; resolves to its public URL. */
export async function uploadArticleImage(file: File): Promise<string> {
  const form = new FormData()
  form.append('file', file)
  const { url } = await fetchJson<{ url: string }>(`${API_BASE}/manage/uploads`, { method: 'POST', body: form })
  return url
}

/** @-mention targets for the editor: every article, linking to its page. */
export async function loadArticleMentionables(): Promise<MentionableItem[]> {
  const { items } = await fetchJson<Page<ArticleAdminListItem>>(`${API_BASE}/manage?limit=100`)
  return items.map((article) => ({ id: article.id, label: article.title, url: articlePath(article.slug) }))
}

/**
 * The CSS custom properties that colour an element in its article type's
 * frame and tint, one pair per theme (see articles.css, which picks the pair
 * for the active theme under `.article-typed`). Empty for an untyped article.
 */
export function typeStyle(type: ArticleType | null): CSSProperties {
  if (!type) return {}
  return {
    '--art-border-light': type.border_light,
    '--art-bg-light': type.background_light,
    '--art-border-dark': type.border_dark,
    '--art-bg-dark': type.background_dark,
  } as CSSProperties
}

/** Lowercase, diacritics stripped, hyphen-separated - matches the backend's slug rule. */
export function slugify(text: string): string {
  return text
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 200)
}
