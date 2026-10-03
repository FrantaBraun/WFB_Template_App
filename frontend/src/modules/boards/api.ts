/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { apiFetch } from '../../api/client'
import { useAuth } from '../../context/AuthContext'

export const API_BASE = '/api/modules/boards'
export const CATEGORIES_PATH = '/categories'
export const MODERATION_PATH = '/moderation'
export const MY_POSTS_PATH = '/my-posts'
export const RECEIPTS_PATH = '/receipts'
export const MY_PAYMENTS_PATH = '/my-payments'
/** Key of the payment purpose this module registers on the backend (app/modules/boards/payments.py). */
export const POST_BOOST = 'post_boost'
// Pages other modules provide, linked from here: the terms and rules
// (stripe_payment_gate's legal pages) and the contact form (kontaktni_formular).
export const RULES_PATH = '/obchodni-podminky'
export const CONTACT_PATH = '/kontakt'

// The backend's text limits (app/modules/boards/models.py), in characters.
export const CATEGORY_TITLE_MAX = 120
export const CATEGORY_DESCRIPTION_MAX = 4096
export const POST_TITLE_MAX = 120
export const POST_BODY_MAX = 2048
export const MODERATION_REASON_MAX = 1000

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
  /** True only for the post's own author, looking at their own post. */
  mine: boolean
  /** What the author has paid for it so far, in cents; null for everyone else. */
  paid_cents: number | null
  created_at: string
}

export type PostStatus = 'published' | 'blocked' | 'removed'

/** One of the signed-in user's own posts, in any state (GET /me/posts). */
export interface MyPost {
  id: string
  category_slug: string
  category_title: string
  title: string
  body: string
  status: PostStatus
  value: number
  resonance_count: number
  paid_cents: number
  /** The post's category is blocked: the post is still "published" but nobody can see it. */
  category_blocked: boolean
  /** An administrator's free text for a blocked post, or the code "account_blocked". */
  moderation_reason: string | null
  created_at: string
}

/** One of the signed-in user's payment documents, in brief (GET /me/receipts). */
export interface Receipt {
  id: string
  /** Runs without gaps within a year: 2026-000001. */
  number: string
  issued_at: string
  /** In the currency's minor unit (cents). */
  amount: number
  currency: string
  post_title: string
  points: number
  /** Whether the confirmation email went out. */
  emailed: boolean
}

/** One payment the signed-in user started for one of their posts (GET /me/payments). */
export interface Payment {
  id: string
  /** The gateway's: "pending" until Stripe confirms; only "paid" is money spent. */
  status: 'pending' | 'paid' | 'failed' | 'expired'
  /** In the currency's minor unit (cents). */
  amount: number
  currency: string
  points: number
  created_at: string
  paid_at: string | null
  /** The post's title today; null when the post cannot be found and there is no document. */
  post_title: string | null
  /** The post's state today; null when it cannot be found. A blocked or removed post keeps what was paid. */
  post_status: PostStatus | null
  /** The post is hidden because its category is blocked. */
  category_blocked: boolean
  /** The document issued for a paid payment (see `Receipt`). */
  receipt_id: string | null
  receipt_number: string | null
}

/** What the user has actually paid: completed payments only, in cents, over every page. */
export interface PaymentSummary {
  paid_count: number
  paid_cents: number
  currency: string
}

export interface PaymentHistory {
  summary: PaymentSummary
  items: Payment[]
  has_more: boolean
}

/** Whether authors can pay to raise a post's value on this deployment, and within what limits. */
export interface PaymentsInfo {
  enabled: boolean
  currency: string
  min_amount_usd: number
  max_amount_usd: number
  points_per_usd: number
}

export interface Page<T> {
  items: T[]
  has_more: boolean
}

// --- Moderation: what an author is shown --------------------------------------

/** "ok" - nothing to say; "warn" (> 30 %) - edit it; "risk" (> 50 %) - potentially violating; "blocked" (> 75 %) - not allowed. */
export type Level = 'ok' | 'warn' | 'risk' | 'blocked'

export interface Finding {
  /** Language-neutral aspect code; translated as `moderation.finding.<code>`. */
  code: string
  /** Which score it belongs to: breaking the rules, or not fitting the category. */
  aspect: 'violation' | 'topic'
  /** Words from the author's own text (violation) or the category's keywords the text lacks (topic). */
  matches: string[]
}

export interface Score {
  percent: number
  level: Level
}

export interface Assessment {
  level: Level
  violation: Score
  /** null for a category, or a category without machine rules. */
  topic: Score | null
  findings: Finding[]
}

/** The signed-in user's standing in this application. */
export interface Me {
  is_admin: boolean
  blocked: boolean
  blocked_reason: string | null
}

// --- Moderation: administrators ------------------------------------------------

export interface AdminPost {
  id: string
  category_slug: string
  category_title: string
  title: string
  body: string
  status: PostStatus
  value: number
  resonance_count: number
  violation_score: number
  topic_mismatch_score: number
  findings: Finding[]
  category_blocked: boolean
  moderation_reason: string | null
  moderated_at: string | null
  author_id: string
  author_blocked: boolean
  created_at: string
}

/** A category as an administrator sees it, blocked or not (GET /manage/categories). */
export interface AdminCategory {
  id: string
  title: string
  slug: string
  description: string
  status: 'published' | 'blocked'
  /** Published posts in it. */
  post_count: number
  violation_score: number
  moderation_reason: string | null
  moderated_at: string | null
  created_by_id: string
  created_at: string
}

export interface RuleKeyword {
  term: string
  weight: number
}

export interface Rules {
  keywords: RuleKeyword[]
  notes: string
}

export interface RulesResponse {
  rules: Rules
  /** "algorithm", "ai" or "admin" - who wrote them last; null when the category has none. */
  source: string | null
  updated_at: string | null
}

export interface BlockedUser {
  id: string
  blocked_at: string | null
  blocked_reason: string | null
}

export class ApiError extends Error {
  status: number
  /** The decoded JSON body of the error response, when it had one. */
  body: unknown
  constructor(status: number, body: unknown = null) {
    super(`HTTP ${status}`)
    this.status = status
    this.body = body
  }
}

/** The `detail` object of a structured error ({code, ...}), or null for a plain one. */
export function errorDetail(err: unknown): { code: string; assessment?: Assessment; reason?: string | null } | null {
  if (!(err instanceof ApiError)) return null
  const detail = (err.body as { detail?: unknown } | null)?.detail
  return detail && typeof detail === 'object' && 'code' in detail ? (detail as { code: string }) : null
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
  if (!resp.ok) throw new ApiError(resp.status, await resp.json().catch(() => null))
  return resp.json()
}

export function sendJson<T>(method: 'POST' | 'PUT', path: string, body?: unknown): Promise<T> {
  return fetchJson<T>(path, { method, ...(body === undefined ? {} : { body: JSON.stringify(body) }) })
}

export function postJson<T>(path: string, body?: unknown): Promise<T> {
  return sendJson<T>('POST', path, body)
}

let paymentsInfo: Promise<PaymentsInfo | null> | null = null

/**
 * Whether payments are on here and their limits; null until known. Fetched
 * once per page load and shared - every post card asks, only one request is
 * made. A failed request is not remembered, so the next ask tries again.
 */
export function usePaymentsInfo(): PaymentsInfo | null {
  const [info, setInfo] = useState<PaymentsInfo | null>(null)

  useEffect(() => {
    let cancelled = false
    paymentsInfo ??= fetchJson<PaymentsInfo>(`${API_BASE}/payments`).catch(() => {
      paymentsInfo = null
      return null
    })
    paymentsInfo.then((found) => !cancelled && setInfo(found))
    return () => {
      cancelled = true
    }
  }, [])

  return info
}

/** "$5" or "$5.50" - cents shown only when there are some. */
export function formatUsd(cents: number, locale: string): string {
  return new Intl.NumberFormat(locale, {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: cents % 100 === 0 ? 0 : 2,
  }).format(cents / 100)
}

/** A minor-unit amount in its own currency, always with cents - how a document states it. */
export function formatMoney(cents: number, currency: string, locale: string): string {
  return new Intl.NumberFormat(locale, { style: 'currency', currency: currency.toUpperCase() }).format(cents / 100)
}

/** The signed-in user's standing here (administrator, blocked); null while unknown and when signed out. */
export function useBoardsMe(): Me | null {
  const { user, loading } = useAuth()
  const [me, setMe] = useState<Me | null>(null)

  useEffect(() => {
    if (loading || !user) {
      setMe(null)
      return
    }
    let cancelled = false
    fetchJson<Me>(`${API_BASE}/me`)
      .then((found) => !cancelled && setMe(found))
      .catch(() => !cancelled && setMe(null))
    return () => {
      cancelled = true
    }
  }, [user, loading])

  return me
}
