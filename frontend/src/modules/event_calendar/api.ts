/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { apiFetch } from '../../api/client'
import { useAuth } from '../../context/AuthContext'
import { articlePath, type ArticleStatus, type ArticleTeaser, type ArticleType } from '../articles/api'

export { articlePath, typeStyle } from '../articles/api'

export const API_BASE = '/api/modules/event_calendar'
export const EVENTS_PATH = '/events'

/** The article an event belongs to - as much as a calendar needs. */
export interface EventArticle {
  id: string
  slug: string
  title: string
  image_url: string | null
  pinned: boolean
  status: ArticleStatus
  type: ArticleType | null
}

/**
 * One date (or run of days) of an article. The text, image and type live on
 * the article; `short_description` (at most 128 characters) is what the
 * calendar shows when you point at the event.
 */
export interface EventTeaser {
  id: string
  title: string
  short_description: string
  /** ISO date (YYYY-MM-DD), no time. */
  start_date: string
  end_date: string | null
  /** "HH:MM:SS" as the backend sends it, or null (all day). */
  start_time: string | null
  end_time: string | null
  article: EventArticle
}

export interface EventAdmin extends EventTeaser {
  article_id: string
  created_at: string
  updated_at: string
}

/** An article on the wall or in search results with the date it is sorted by. */
export interface DatedArticle extends ArticleTeaser {
  /** ISO date: the nearest upcoming event (or its last one), or the creation day when it has none. */
  date: string
  date_kind: 'event' | 'created'
}

/** What GET /dashboard returns - an application's home page is made of this. */
export interface Dashboard {
  upcoming: DatedArticle | null
  pinned: DatedArticle[]
  recent_past: DatedArticle[]
}

export interface ArchiveYear {
  year: number
  months: { month: number; count: number }[]
}

/** Where an event leads: its article. */
export function eventPath(event: Pick<EventTeaser, 'article'>): string {
  return articlePath(event.article.slug)
}

/** "YYYY-MM-DD" as a local date - new Date("YYYY-MM-DD") would parse it as UTC midnight and can show the previous day. */
export function parseEventDate(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

const LONG_DATE: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'long', year: 'numeric' }

export function formatEventDate(iso: string, language: string): string {
  return parseEventDate(iso).toLocaleDateString(language, LONG_DATE)
}

function formatTime(time: string): string {
  return time.slice(0, 5)
}

/** "14. března 2026", "14. – 15. března 2026" for a run of days, with " · 10:00–16:30" when it has times. */
export function formatEventWhen(event: Pick<EventTeaser, 'start_date' | 'end_date' | 'start_time' | 'end_time'>, language: string): string {
  const formatter = new Intl.DateTimeFormat(language, LONG_DATE)
  const start = parseEventDate(event.start_date)
  const days =
    event.end_date && event.end_date !== event.start_date
      ? formatter.formatRange(start, parseEventDate(event.end_date))
      : formatter.format(start)
  if (!event.start_time) return days
  const times = event.end_time ? `${formatTime(event.start_time)}–${formatTime(event.end_time)}` : formatTime(event.start_time)
  return `${days} · ${times}`
}

export function monthName(year: number, month: number, language: string): string {
  return new Intl.DateTimeFormat(language, { month: 'long' }).format(new Date(year, month - 1, 1))
}

export async function fetchJson<T>(path: string, init?: Parameters<typeof apiFetch>[1]): Promise<T> {
  const resp = await apiFetch(path, init)
  if (!resp.ok) throw Object.assign(new Error(`HTTP ${resp.status}`), { status: resp.status })
  return resp.status === 204 ? (undefined as T) : resp.json()
}

/** null while unknown; false for anonymous visitors without asking the backend. */
export function useIsEditor(): boolean | null {
  const { user, loading } = useAuth()
  const [isEditor, setIsEditor] = useState<boolean | null>(null)

  useEffect(() => {
    if (loading) return
    if (!user) {
      setIsEditor(false)
      return
    }
    let cancelled = false
    fetchJson<{ is_editor: boolean }>(`${API_BASE}/manage/me`)
      .then((r) => !cancelled && setIsEditor(r.is_editor))
      .catch(() => !cancelled && setIsEditor(false))
    return () => {
      cancelled = true
    }
  }, [user, loading])

  return isEditor
}
