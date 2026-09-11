/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { apiFetch } from '../api/client'
import { useAuth } from '../context/AuthContext'

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

/**
 * Renders nothing unless the signed-in caller has unread notifications for
 * this exact document. GET /api/notifications is auth-required, so an
 * anonymous visitor is never even asked - same "don't render, don't crash"
 * rule ApiDocDetail.tsx's subscribe button follows for the same reason.
 * Dismissing only hides the banner for this page view; it never calls
 * /read or /read-all itself, which stay the bell dropdown's job.
 */
export default function VersionBanner({ documentationId }: { documentationId: string }) {
  const { t } = useTranslation()
  const { user } = useAuth()
  const [items, setItems] = useState<NotificationItemData[]>([])
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    setDismissed(false)
    setItems([])
    if (!user) return
    let cancelled = false
    apiFetch(`/api/notifications?documentation_id=${documentationId}&unread=true`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data: NotificationListData) => {
        if (!cancelled) setItems(data.items)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [documentationId, user])

  if (dismissed || items.length === 0) return null

  const versions = items.map((item) => item.version).join(', ')

  return (
    <div className="flex items-center justify-between gap-4 rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-800 dark:border-sky-800 dark:bg-sky-950/40 dark:text-sky-200">
      <p>{t('notifications.banner.text', { versions })}</p>
      <button
        type="button"
        onClick={() => setDismissed(true)}
        className="shrink-0 font-medium text-sky-700 underline dark:text-sky-300"
      >
        {t('notifications.banner.dismiss')}
      </button>
    </div>
  )
}
