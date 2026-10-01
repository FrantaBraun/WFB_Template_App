/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { apiFetch } from '../../api/client'
import { useAuth } from '../../context/AuthContext'
import type { MentionableItem } from '../../components/RichTextEditor'

export const API_BASE = '/api/modules/event_calendar'
export const EVENTS_PATH = '/events'

export type EventStatus = 'draft' | 'published' | 'deleted'

export interface EventTeaser {
  id: string
  title: string
  slug: string
  short_description: string
  image_url: string | null
  /** ISO date (YYYY-MM-DD), no time. */
  event_date: string
  pinned: boolean
}

export interface EventDetail extends EventTeaser {
  full_text: string
}

export interface EventAdmin extends EventDetail {
  display_from: string | null
  display_to: string | null
  status: EventStatus
  created_at: string
  updated_at: string
}

export interface ArchiveYear {
  year: number
  months: { month: number; count: number }[]
}

export function eventPath(slug: string): string {
  return `${EVENTS_PATH}/${slug}`
}

/** "YYYY-MM-DD" as a local date - new Date("YYYY-MM-DD") would parse it as UTC midnight and can show the previous day. */
export function parseEventDate(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function formatEventDate(iso: string, language: string): string {
  return parseEventDate(iso).toLocaleDateString(language, { day: 'numeric', month: 'long', year: 'numeric' })
}

export function monthName(year: number, month: number, language: string): string {
  return new Intl.DateTimeFormat(language, { month: 'long' }).format(new Date(year, month - 1, 1))
}

export async function fetchJson<T>(path: string, init?: Parameters<typeof apiFetch>[1]): Promise<T> {
  const resp = await apiFetch(path, init)
  if (!resp.ok) throw Object.assign(new Error(`HTTP ${resp.status}`), { status: resp.status })
  return resp.json()
}

/** Uploads a thumbnail or in-text image; resolves to its public URL. */
export async function uploadEventImage(file: File): Promise<string> {
  const form = new FormData()
  form.append('file', file)
  const { url } = await fetchJson<{ url: string }>(`${API_BASE}/manage/uploads`, { method: 'POST', body: form })
  return url
}

/** @-mention targets for the editor: every event, linking to its page. */
export async function loadEventMentionables(): Promise<MentionableItem[]> {
  const events = await fetchJson<EventAdmin[]>(`${API_BASE}/manage`)
  return events
    .filter((event) => event.status !== 'deleted')
    .map((event) => ({ id: event.id, label: event.title, url: eventPath(event.slug) }))
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
