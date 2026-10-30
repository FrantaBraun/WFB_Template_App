/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import usePageMeta from '../../hooks/usePageMeta'
import ModuleSlot from '../ModuleSlot'
import { API_BASE as ARTICLES_API, type ArticleAdmin, type ArticleAdminListItem, type Page } from '../articles/api'
import { API_BASE, EVENTS_PATH, articlePath, fetchJson, type EventAdmin } from './api'
import { EditorGate } from './ManageEventsPage'

const SHORT_DESCRIPTION_MAX = 128

interface FormState {
  article_id: string
  title: string
  short_description: string
  start_date: string
  end_date: string
  start_time: string
  end_time: string
}

const EMPTY: FormState = { article_id: '', title: '', short_description: '', start_date: '', end_date: '', start_time: '', end_time: '' }

const inputClass =
  'w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100'
const labelClass = 'mb-1 block text-sm text-slate-600 dark:text-slate-400'
const secondaryButton =
  'rounded-lg border border-slate-200 px-3 py-1.5 text-sm hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800'

/** "10:00:00" from the backend -> "10:00" for <input type="time">. */
function timeValue(time: string | null): string {
  return time ? time.slice(0, 5) : ''
}

/** Search-as-you-type over the articles (administrators see every status), pick one. */
function ArticlePicker({ onPick }: { onPick: (article: { id: string; title: string }) => void }) {
  const { t } = useTranslation('event_calendar')
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<ArticleAdminListItem[]>([])

  useEffect(() => {
    let cancelled = false
    const timer = setTimeout(() => {
      const params = new URLSearchParams({ limit: '8' })
      if (query.trim()) params.set('q', query.trim())
      fetchJson<Page<ArticleAdminListItem>>(`${ARTICLES_API}/manage?${params}`)
        .then((page) => !cancelled && setResults(page.items))
        .catch(() => !cancelled && setResults([]))
    }, 250)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [query])

  return (
    <div className="space-y-2">
      <input
        type="search"
        autoFocus
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={t('form.articleSearch')}
        aria-label={t('form.articleSearch')}
        className={inputClass}
      />
      <ul className="max-h-60 overflow-y-auto rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
        {results.length === 0 && <li className="px-3 py-2 text-sm text-slate-500 dark:text-slate-400">{t('form.articleNoResults')}</li>}
        {results.map((article) => (
          <li key={article.id}>
            <button
              type="button"
              onClick={() => onPick({ id: article.id, title: article.title })}
              className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-slate-50 dark:hover:bg-slate-800"
            >
              <span className="truncate">{article.title}</span>
              <span className="shrink-0 text-xs text-slate-500 dark:text-slate-400">{t(`articleStatus.${article.status}`)}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

function EventForm({ eventId }: { eventId: string | undefined }) {
  const { t } = useTranslation('event_calendar')
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const presetArticleId = searchParams.get('article')
  const [form, setForm] = useState<FormState | null>(eventId ? null : { ...EMPTY, article_id: presetArticleId ?? '' })
  const [saved, setSaved] = useState<EventAdmin | null>(null)
  const [articleTitle, setArticleTitle] = useState('')
  const [pickingArticle, setPickingArticle] = useState(!eventId && !presetArticleId)
  // A new event's title follows the article's until the editor types a title of their own.
  const [titleTouched, setTitleTouched] = useState(Boolean(eventId))
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null)

  useEffect(() => {
    if (!eventId) return
    fetchJson<EventAdmin>(`${API_BASE}/manage/${eventId}`)
      .then((e) => {
        setSaved(e)
        setArticleTitle(e.article.title)
        setForm({
          article_id: e.article_id,
          title: e.title,
          short_description: e.short_description,
          start_date: e.start_date,
          end_date: e.end_date ?? '',
          start_time: timeValue(e.start_time),
          end_time: timeValue(e.end_time),
        })
      })
      .catch(() => setMessage({ kind: 'error', text: t('form.loadError') }))
  }, [eventId, t])

  // /events/manage/new?article=<id> (the "add a date" link in an article's editor): look the article up.
  useEffect(() => {
    if (eventId || !presetArticleId) return
    fetchJson<ArticleAdmin>(`${ARTICLES_API}/manage/${presetArticleId}`)
      .then((a) => {
        setArticleTitle(a.title)
        setForm((current) => (current && !current.title ? { ...current, title: a.title } : current))
      })
      .catch(() => {
        setPickingArticle(true)
        setForm((current) => (current ? { ...current, article_id: '' } : current))
      })
  }, [eventId, presetArticleId])

  if (!form) {
    return <p className="mx-auto max-w-4xl px-6 py-16 text-slate-500 dark:text-slate-400">{message?.text ?? t('common.loading')}</p>
  }

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => (current ? { ...current, [key]: value } : current))
  }

  function pickArticle(article: { id: string; title: string }) {
    setArticleTitle(article.title)
    setPickingArticle(false)
    setForm((current) => {
      if (!current) return current
      return { ...current, article_id: article.id, title: titleTouched || current.title ? current.title : article.title }
    })
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!form) return
    if (!form.article_id) {
      setMessage({ kind: 'error', text: t('form.noArticle') })
      return
    }
    setSaving(true)
    setMessage(null)
    const payload = {
      ...form,
      end_date: form.end_date || null,
      start_time: form.start_time || null,
      end_time: form.end_time || null,
    }
    try {
      const result = await fetchJson<EventAdmin>(eventId ? `${API_BASE}/manage/${eventId}` : `${API_BASE}/manage`, {
        method: eventId ? 'PATCH' : 'POST',
        body: JSON.stringify(payload),
      })
      if (!eventId) {
        // Straight to the edit page, where what other modules add to a saved event (e.g. its registration) can attach.
        navigate(`${EVENTS_PATH}/manage/${result.id}`, { replace: true })
        return
      }
      setSaved(result)
      setArticleTitle(result.article.title)
      setMessage({ kind: 'ok', text: t('form.saved') })
    } catch (err) {
      const status = (err as { status?: number }).status
      setMessage({ kind: 'error', text: status === 422 ? t('form.invalid') : t('form.saveError') })
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete() {
    if (!eventId || !window.confirm(t('form.confirmDelete'))) return
    try {
      await fetchJson(`${API_BASE}/manage/${eventId}`, { method: 'DELETE' })
      navigate(`${EVENTS_PATH}/manage`)
    } catch (err) {
      setMessage({ kind: 'error', text: (err as { status?: number }).status === 409 ? t('form.deleteBlocked') : t('form.deleteError') })
    }
  }

  return (
    <div className="mx-auto max-w-4xl px-6 py-12 text-slate-900 dark:text-slate-100">
      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-3xl font-semibold tracking-tight">{eventId ? t('form.editTitle') : t('form.newTitle')}</h1>
          <div className="flex gap-2">
            <Link to={`${EVENTS_PATH}/manage`} className={secondaryButton}>
              {t('form.backToList')}
            </Link>
            {saved && (
              <Link to={articlePath(saved.article.slug)} className={secondaryButton}>
                {t('form.viewArticle')}
              </Link>
            )}
          </div>
        </div>

        <div>
          <span className={labelClass}>{t('form.article')}</span>
          {pickingArticle ? (
            <div className="space-y-2">
              <ArticlePicker onPick={pickArticle} />
              {form.article_id && (
                <button type="button" onClick={() => setPickingArticle(false)} className="text-sm text-slate-500 underline dark:text-slate-400">
                  {t('form.articleKeep')}
                </button>
              )}
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-3">
              <span className="font-medium">{articleTitle || '…'}</span>
              <button type="button" onClick={() => setPickingArticle(true)} className={secondaryButton}>
                {t('form.articleChange')}
              </button>
            </div>
          )}
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label htmlFor="ev-title" className={labelClass}>{t('form.title')}</label>
            <input
              id="ev-title"
              required
              maxLength={200}
              value={form.title}
              onChange={(e) => {
                setTitleTouched(true)
                update('title', e.target.value)
              }}
              className={inputClass}
            />
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{t('form.titleHint')}</p>
          </div>
          <div className="sm:col-span-2">
            <label htmlFor="ev-short" className={labelClass}>{t('form.shortDescription')}</label>
            <textarea
              id="ev-short"
              rows={2}
              maxLength={SHORT_DESCRIPTION_MAX}
              value={form.short_description}
              onChange={(e) => update('short_description', e.target.value)}
              className={inputClass}
            />
            <p className="mt-1 text-right text-xs text-slate-500 dark:text-slate-400">{form.short_description.length} / {SHORT_DESCRIPTION_MAX}</p>
          </div>

          <div>
            <label htmlFor="ev-start-date" className={labelClass}>{t('form.startDate')}</label>
            <input id="ev-start-date" type="date" required value={form.start_date} onChange={(e) => update('start_date', e.target.value)} className={inputClass} />
          </div>
          <div>
            <label htmlFor="ev-end-date" className={labelClass}>{t('form.endDate')}</label>
            <input id="ev-end-date" type="date" value={form.end_date} min={form.start_date || undefined} onChange={(e) => update('end_date', e.target.value)} className={inputClass} />
          </div>
          <div>
            <label htmlFor="ev-start-time" className={labelClass}>{t('form.startTime')}</label>
            <input id="ev-start-time" type="time" value={form.start_time} onChange={(e) => update('start_time', e.target.value)} className={inputClass} />
          </div>
          <div>
            <label htmlFor="ev-end-time" className={labelClass}>{t('form.endTime')}</label>
            <input id="ev-end-time" type="time" value={form.end_time} disabled={!form.start_time} onChange={(e) => update('end_time', e.target.value)} className={`${inputClass} disabled:opacity-50`} />
          </div>
          <p className="-mt-2 text-xs text-slate-500 sm:col-span-2 dark:text-slate-400">{t('form.termHint')}</p>
        </div>

        {message && (
          <p role="status" className={`text-sm ${message.kind === 'ok' ? 'text-emerald-700 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
            {message.text}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-3">
          <button type="submit" disabled={saving} className="rounded-lg bg-slate-900 px-5 py-2 font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900">
            {saving ? t('form.saving') : t('form.save')}
          </button>
          {eventId && (
            <button type="button" onClick={handleDelete} className="rounded-lg px-3 py-2 text-sm text-red-600 dark:text-red-400">
              {t('form.delete')}
            </button>
          )}
        </div>
      </form>

      {/* Other modules add their panels here (the registration for this event, ...). Only once it is saved: they need its id. */}
      {saved && <ModuleSlot name="event.editor" context={{ event: saved }} />}
    </div>
  )
}

/** /events/manage/new (optionally ?article=<id>) and /events/manage/:id. */
export default function EventFormPage() {
  const { t } = useTranslation('event_calendar')
  const { id } = useParams<{ id: string }>()
  usePageMeta({ title: id ? t('form.editTitle') : t('form.newTitle'), noindex: true })
  return (
    <EditorGate>
      <EventForm key={id ?? 'new'} eventId={id} />
    </EditorGate>
  )
}
