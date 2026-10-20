/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import ModuleSlot from '../ModuleSlot'
import { API_BASE, EVENTS_PATH, fetchJson, formatEventWhen, parseEventDate, type EventAdmin, type EventTeaser } from './api'

/** Midnight at the start of today, to tell the dates still to come from those gone by. */
function startOfToday(): Date {
  const now = new Date()
  return new Date(now.getFullYear(), now.getMonth(), now.getDate())
}

/**
 * The dates of an article, on the article's own page (contributed to the
 * "article.detail" slot of the articles module; context `{ article }`).
 * Each date renders the "event.actions" slot (context `{ event }`), where
 * modules built on events - a registration, say - put their buttons.
 * Renders nothing for an article without dates.
 */
export function ArticleDates({ context }: { context: { article: { id: string } } }) {
  const { t, i18n } = useTranslation('event_calendar')
  const [events, setEvents] = useState<EventTeaser[] | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchJson<EventTeaser[]>(`${API_BASE}/by-article/${context.article.id}`)
      .then((found) => !cancelled && setEvents(found))
      .catch(() => !cancelled && setEvents([]))
    return () => {
      cancelled = true
    }
  }, [context.article.id])

  if (!events || events.length === 0) return null
  const today = startOfToday()

  return (
    <section aria-labelledby="article-dates-heading" className="mt-8 text-slate-900 dark:text-slate-100">
      <h2 id="article-dates-heading" className="mb-3 text-xl font-semibold tracking-tight">{t('articleDates.title')}</h2>
      <ul className="space-y-3">
        {events.map((event) => {
          const over = parseEventDate(event.end_date ?? event.start_date) < today
          return (
            <li key={event.id} className={`rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900 ${over ? 'opacity-70' : ''}`}>
              <p className="text-sm font-medium">
                {formatEventWhen(event, i18n.language)}
                {over && <span className="ml-2 text-xs font-normal text-slate-500 dark:text-slate-400">{t('articleDates.over')}</span>}
              </p>
              <p className="font-semibold">{event.title}</p>
              {event.short_description && <p className="text-sm text-slate-600 dark:text-slate-300">{event.short_description}</p>}
              <ModuleSlot name="event.actions" context={{ event }} />
            </li>
          )
        })}
      </ul>
    </section>
  )
}

/**
 * The dates of an article in its editor - add, edit (in the event editor) and
 * delete them without leaving the article (contributed to the "article.editor"
 * slot; context `{ article }`, the article already saved).
 */
export function ArticleDatesPanel({ context }: { context: { article: { id: string } } }) {
  const { t, i18n } = useTranslation('event_calendar')
  const [events, setEvents] = useState<EventAdmin[] | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const load = useCallback(() => {
    fetchJson<EventAdmin[]>(`${API_BASE}/manage?article_id=${context.article.id}`)
      .then(setEvents)
      .catch(() => setEvents([]))
  }, [context.article.id])

  useEffect(load, [load])

  async function remove(event: EventAdmin) {
    if (!window.confirm(t('form.confirmDelete'))) return
    setMessage(null)
    try {
      await fetchJson(`${API_BASE}/manage/${event.id}`, { method: 'DELETE' })
      load()
    } catch (err) {
      setMessage((err as { status?: number }).status === 409 ? t('form.deleteBlocked') : t('form.deleteError'))
    }
  }

  return (
    <section aria-labelledby="article-dates-panel-heading" className="mt-10 rounded-2xl border border-slate-200 bg-white p-5 text-slate-900 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <h2 id="article-dates-panel-heading" className="text-xl font-semibold tracking-tight">{t('articleDates.title')}</h2>
        <Link
          to={`${EVENTS_PATH}/manage/new?article=${context.article.id}`}
          className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-medium text-slate-100 dark:bg-slate-100 dark:text-slate-900"
        >
          {t('articleDates.add')}
        </Link>
      </div>
      {events === null && <p className="text-sm text-slate-500 dark:text-slate-400">{t('common.loading')}</p>}
      {events && events.length === 0 && <p className="text-sm text-slate-500 dark:text-slate-400">{t('articleDates.none')}</p>}
      {events && events.length > 0 && (
        <ul className="divide-y divide-slate-200 dark:divide-slate-800">
          {events.map((event) => (
            <li key={event.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2">
              <span className="w-56 shrink-0 text-sm text-slate-500 dark:text-slate-400">{formatEventWhen(event, i18n.language)}</span>
              <span className="min-w-0 flex-1 truncate font-medium">{event.title}</span>
              <Link to={`${EVENTS_PATH}/manage/${event.id}`} className="text-sm underline">{t('articleDates.edit')}</Link>
              <button type="button" onClick={() => remove(event)} className="text-sm text-red-600 dark:text-red-400">{t('articleDates.delete')}</button>
            </li>
          ))}
        </ul>
      )}
      {message && <p role="alert" className="mt-2 text-sm text-red-600 dark:text-red-400">{message}</p>}
    </section>
  )
}
