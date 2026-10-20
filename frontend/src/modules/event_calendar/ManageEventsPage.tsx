/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import usePageMeta from '../../hooks/usePageMeta'
import ModuleSlot from '../ModuleSlot'
import { API_BASE, EVENTS_PATH, fetchJson, formatEventWhen, useIsEditor, type EventAdmin } from './api'

/** Wraps an editor-only page: sends signed-out visitors to /login, shows a notice to signed-in non-editors. */
export function EditorGate({ children }: { children: ReactNode }) {
  const { t } = useTranslation('event_calendar')
  const { user, loading } = useAuth()
  const navigate = useNavigate()
  const isEditor = useIsEditor()

  useEffect(() => {
    if (!loading && !user) navigate('/login')
  }, [loading, user, navigate])

  if (loading || isEditor === null) {
    return <p className="mx-auto max-w-4xl px-6 py-16 text-slate-500 dark:text-slate-400">{t('common.loading')}</p>
  }
  if (!isEditor) {
    return <p className="mx-auto max-w-4xl px-6 py-16 text-slate-600 dark:text-slate-300">{t('manage.forbidden')}</p>
  }
  return <>{children}</>
}

function ManageList() {
  const { t, i18n } = useTranslation('event_calendar')
  const [events, setEvents] = useState<EventAdmin[] | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    fetchJson<EventAdmin[]>(`${API_BASE}/manage`)
      .then(setEvents)
      .catch(() => setError(true))
  }, [])

  return (
    <div className="mx-auto max-w-4xl px-6 py-12 text-slate-900 dark:text-slate-100">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-3xl font-semibold tracking-tight">{t('manage.title')}</h1>
        <Link to={`${EVENTS_PATH}/manage/new`} className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-medium text-slate-100 dark:bg-slate-100 dark:text-slate-900">
          {t('manage.new')}
        </Link>
      </div>

      {error && <p className="text-sm text-red-600 dark:text-red-400">{t('list.error')}</p>}
      {events === null && !error && <p className="text-slate-500 dark:text-slate-400">{t('common.loading')}</p>}
      {events && events.length === 0 && <p className="text-slate-500 dark:text-slate-400">{t('manage.empty')}</p>}

      {events && events.length > 0 && (
        <ul className="divide-y divide-slate-200 overflow-hidden rounded-2xl border border-slate-200 bg-white dark:divide-slate-800 dark:border-slate-800 dark:bg-slate-900">
          {events.map((event) => (
            <li key={event.id} className="flex flex-wrap items-center gap-x-3 px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-800/60">
              <Link to={`${EVENTS_PATH}/manage/${event.id}`} className="flex min-w-0 flex-1 flex-wrap items-center gap-x-3 gap-y-1">
                <span className="w-56 shrink-0 text-sm text-slate-500 dark:text-slate-400">{formatEventWhen(event, i18n.language)}</span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">{event.title}</span>
                  <span className="block truncate text-xs text-slate-500 dark:text-slate-400">
                    {event.article.pinned && <span aria-label={t('list.pinned')}>📌 </span>}
                    {event.article.title}
                    {event.article.status !== 'published' && ` · ${t(`articleStatus.${event.article.status}`)}`}
                  </span>
                </span>
              </Link>
              {/* Other modules add their row actions here (e.g. a link to the event's registration). */}
              <ModuleSlot name="event.manage" context={{ event }} />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/** /events/manage - every event of every article, for editors. */
export default function ManageEventsPage() {
  const { t } = useTranslation('event_calendar')
  usePageMeta({ title: t('manage.title'), noindex: true })
  return (
    <EditorGate>
      <ManageList />
    </EditorGate>
  )
}
