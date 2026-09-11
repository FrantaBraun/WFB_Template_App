/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { apiFetch } from '../api/client'

interface NotificationItemData {
  id: string
  documentation_id: string
  document_title: string
  version: string
  is_read: boolean
  created_at: string
}

interface NotificationListData {
  items: NotificationItemData[]
  unread_count: number
}

const POLL_INTERVAL_MS = 60_000

function formatDateTime(iso: string, locale: string): string {
  return new Date(iso).toLocaleString(locale, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** Bell glyph, hand-drawn to match ThemeToggle.tsx's inline-SVG icon style rather than pulling in an icon library. */
function BellIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  )
}

/**
 * Header bell: fetches the caller's notifications on mount and every
 * POLL_INTERVAL_MS thereafter, showing unread_count as a badge. Only ever
 * mounted while signed in (see Layout.tsx's Nav), so it needs no auth guard
 * of its own. Opening the dropdown marks everything read in one shot -
 * closing and reopening never repeats that call, only the closed->open
 * transition itself does (checked in handleBellClick, not via an effect).
 */
export default function NotificationBell() {
  const { t, i18n } = useTranslation()
  const [data, setData] = useState<NotificationListData | null>(null)
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  function fetchNotifications() {
    apiFetch('/api/notifications')
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((result: NotificationListData) => setData(result))
      .catch(() => {})
  }

  useEffect(() => {
    fetchNotifications()
    const intervalId = setInterval(fetchNotifications, POLL_INTERVAL_MS)
    return () => clearInterval(intervalId)
  }, [])

  useEffect(() => {
    if (!open) return
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  function handleBellClick() {
    const next = !open
    setOpen(next)
    if (next) {
      // Optimistic zero so the badge clears the instant the dropdown opens,
      // not only once the request below resolves.
      setData((prev) =>
        prev ? { ...prev, unread_count: 0, items: prev.items.map((item) => ({ ...item, is_read: true })) } : prev,
      )
      apiFetch('/api/notifications/read-all', { method: 'POST' })
        .then(() => fetchNotifications())
        .catch(() => {})
    }
  }

  const unreadCount = data?.unread_count ?? 0
  const items = data?.items ?? []

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={handleBellClick}
        aria-label={t('notifications.bell.title')}
        className="relative rounded-full p-1 text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-slate-100"
      >
        <BellIcon className="h-5 w-5" />
        {unreadCount > 0 && (
          <span className="absolute -right-1 -top-1 flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-medium leading-none text-white">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full z-10 mt-2 w-72 rounded-xl border border-slate-200 bg-white p-2 text-sm shadow-lg dark:border-slate-800 dark:bg-slate-900">
          <p className="px-2 py-1 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            {t('notifications.bell.title')}
          </p>
          {items.length === 0 ? (
            <p className="px-2 py-3 text-slate-600 dark:text-slate-400">{t('notifications.bell.empty')}</p>
          ) : (
            <ul className="divide-y divide-slate-200 dark:divide-slate-800">
              {items.map((item) => (
                <li key={item.id}>
                  <Link
                    to={`/api-docs/${item.documentation_id}`}
                    onClick={() => setOpen(false)}
                    className="block rounded-lg px-2 py-2 hover:bg-slate-50 dark:hover:bg-slate-800/50"
                  >
                    <p className="font-medium text-slate-900 dark:text-slate-100">{item.document_title}</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      {t('notifications.bell.itemText', { version: item.version })}
                      {' · '}
                      {formatDateTime(item.created_at, i18n.language)}
                    </p>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
