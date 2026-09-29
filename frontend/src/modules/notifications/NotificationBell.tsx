/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../api/client'
import { useAuth } from '../../context/AuthContext'

interface NotificationItem {
  id: string
  message_key: string
  message_params: Record<string, unknown> | null
  link_url: string | null
  is_read: boolean
  created_at: string
}

interface NotificationsResponse {
  items: NotificationItem[]
  unread_count: number
}

const POLL_INTERVAL_MS = 60_000

function BellIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      <path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  )
}

export default function NotificationBell() {
  const { t } = useTranslation('notifications')
  // Per-item message_key/message_params are opaque, caller-defined strings
  // (see backend/app/modules/notifications/models.py) - the caller decides
  // their own namespacing (an explicit "ns:key" prefix, or none at all, the
  // same as any other t() call in the app they own), so rendering them must
  // use the DEFAULT-namespaced t, not this component's own "notifications"
  // namespace - otherwise an unprefixed key like a caller's own
  // "some.page.itemText" would incorrectly resolve inside the
  // "notifications" bundle instead of the caller's default one.
  const { t: tMessage } = useTranslation()
  const { user } = useAuth()
  const [items, setItems] = useState<NotificationItem[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!user) return
    let cancelled = false

    async function fetchNotifications() {
      const resp = await apiFetch('/api/modules/notifications').catch(() => null)
      if (cancelled || !resp?.ok) return
      const data: NotificationsResponse = await resp.json()
      if (cancelled) return
      setItems(data.items)
      setUnreadCount(data.unread_count)
    }

    fetchNotifications()
    const interval = setInterval(fetchNotifications, POLL_INTERVAL_MS)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [user])

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

  function handleToggle() {
    const opening = !open
    setOpen(opening)
    if (opening && unreadCount > 0) {
      setUnreadCount(0)
      setItems((prev) => prev.map((item) => ({ ...item, is_read: true })))
      apiFetch('/api/modules/notifications/read-all', { method: 'POST' }).catch(() => {})
    }
  }

  if (!user) return null

  return (
    <div ref={containerRef} className="relative">
      <button
        onClick={handleToggle}
        aria-label={t('bell.title')}
        className="relative rounded-full p-1.5 text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-100"
      >
        <BellIcon className="h-5 w-5" />
        {unreadCount > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-medium text-white">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="fixed inset-x-4 top-16 z-10 rounded-lg border border-slate-200 bg-white py-1 text-sm shadow-lg dark:border-slate-800 dark:bg-slate-900 sm:absolute sm:inset-x-auto sm:top-full sm:right-0 sm:mt-2 sm:w-80">
          <p className="border-b border-slate-100 px-3 py-2 font-medium text-slate-900 dark:border-slate-800 dark:text-slate-100">
            {t('bell.title')}
          </p>
          {items.length === 0 ? (
            <p className="px-3 py-4 text-center text-slate-500 dark:text-slate-400">{t('bell.empty')}</p>
          ) : (
            <ul className="max-h-96 overflow-y-auto">
              {items.map((item) => {
                const content = (
                  <>
                    <p className={item.is_read ? 'text-slate-600 dark:text-slate-400' : 'font-medium text-slate-900 dark:text-slate-100'}>
                      {tMessage(item.message_key, item.message_params ?? undefined)}
                    </p>
                    <p className="mt-0.5 text-xs text-slate-400 dark:text-slate-500">{new Date(item.created_at).toLocaleString()}</p>
                  </>
                )
                return (
                  <li key={item.id} className="border-b border-slate-100 last:border-0 dark:border-slate-800">
                    {item.link_url ? (
                      <Link
                        to={item.link_url}
                        onClick={() => setOpen(false)}
                        className="block px-3 py-2 hover:bg-slate-50 dark:hover:bg-slate-800"
                      >
                        {content}
                      </Link>
                    ) : (
                      <div className="px-3 py-2">{content}</div>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
