/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import usePageMeta from '../../hooks/usePageMeta'
import { API_BASE, EVENTS_PATH, fetchJson, formatEventDate, useIsEditor, type EventDetail } from './api'

/** /events/:slug - the full event page. full_text is editor HTML the backend sanitized on save. */
export default function EventDetailPage() {
  const { t, i18n } = useTranslation('event_calendar')
  const { slug } = useParams<{ slug: string }>()
  const isEditor = useIsEditor()
  const [event, setEvent] = useState<EventDetail | null>(null)
  const [notFound, setNotFound] = useState(false)

  usePageMeta({ title: event?.title, description: event?.short_description })

  useEffect(() => {
    if (!slug) return
    let cancelled = false
    setEvent(null)
    setNotFound(false)
    fetchJson<EventDetail>(`${API_BASE}/${encodeURIComponent(slug)}`)
      .then((e) => !cancelled && setEvent(e))
      .catch(() => !cancelled && setNotFound(true))
    return () => {
      cancelled = true
    }
  }, [slug])

  if (notFound || !event) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-24 text-center text-slate-600 dark:text-slate-400">
        <p>{notFound ? t('detail.notFound') : t('common.loading')}</p>
        {notFound && (
          <Link to={EVENTS_PATH} className="mt-4 inline-block underline">
            {t('detail.back')}
          </Link>
        )}
      </div>
    )
  }

  return (
    <article className="mx-auto max-w-3xl px-6 py-12 text-slate-900 dark:text-slate-100">
      <div className="mb-6 flex items-center justify-between gap-3 text-sm">
        <Link to={EVENTS_PATH} className="text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-100">
          ← {t('detail.back')}
        </Link>
        {isEditor && (
          <Link to={`${EVENTS_PATH}/manage/${event.id}`} className="rounded-lg border border-slate-200 px-3 py-1.5 hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800">
            {t('detail.edit')}
          </Link>
        )}
      </div>
      {event.image_url && (
        <img src={event.image_url} alt="" className="mb-6 max-h-96 w-full rounded-2xl object-cover" />
      )}
      <p className="mb-2 text-sm text-slate-500 dark:text-slate-400">{formatEventDate(event.event_date, i18n.language)}</p>
      <h1 className="mb-4 text-3xl font-semibold tracking-tight">{event.title}</h1>
      {event.short_description && <p className="mb-6 text-lg text-slate-600 dark:text-slate-300">{event.short_description}</p>}
      <div className="rich-text-content" dangerouslySetInnerHTML={{ __html: event.full_text }} />
    </article>
  )
}
