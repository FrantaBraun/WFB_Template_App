/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'
import RichTextEditor from '../../components/RichTextEditor'
import usePageMeta from '../../hooks/usePageMeta'
import {
  API_BASE,
  EVENTS_PATH,
  eventPath,
  fetchJson,
  loadEventMentionables,
  slugify,
  uploadEventImage,
  type EventAdmin,
  type EventStatus,
} from './api'
import { EditorGate } from './ManageEventsPage'

interface FormState {
  title: string
  slug: string
  short_description: string
  full_text: string
  image_url: string
  event_date: string
  display_from: string
  display_to: string
  pinned: boolean
  status: EventStatus
}

const EMPTY: FormState = {
  title: '',
  slug: '',
  short_description: '',
  full_text: '',
  image_url: '',
  event_date: '',
  display_from: '',
  display_to: '',
  pinned: false,
  status: 'draft',
}

const inputClass =
  'w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100'
const labelClass = 'mb-1 block text-sm text-slate-600 dark:text-slate-400'

function EventForm({ eventId }: { eventId: string | undefined }) {
  const { t } = useTranslation('event_calendar')
  const navigate = useNavigate()
  const fileRef = useRef<HTMLInputElement>(null)
  const [form, setForm] = useState<FormState | null>(eventId ? null : EMPTY)
  // A new event's slug follows its title until the editor types a slug of their own.
  const [slugTouched, setSlugTouched] = useState(Boolean(eventId))
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [message, setMessage] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null)

  useEffect(() => {
    if (!eventId) return
    fetchJson<EventAdmin>(`${API_BASE}/manage/${eventId}`)
      .then((e) =>
        setForm({
          title: e.title,
          slug: e.slug,
          short_description: e.short_description,
          full_text: e.full_text,
          image_url: e.image_url ?? '',
          event_date: e.event_date,
          display_from: e.display_from ?? '',
          display_to: e.display_to ?? '',
          pinned: e.pinned,
          status: e.status,
        }),
      )
      .catch(() => setMessage({ kind: 'error', text: t('form.loadError') }))
  }, [eventId, t])

  if (!form) {
    return <p className="mx-auto max-w-4xl px-6 py-16 text-slate-500 dark:text-slate-400">{message?.text ?? t('common.loading')}</p>
  }

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => {
      if (!current) return current
      const next = { ...current, [key]: value }
      if (key === 'title' && !slugTouched) next.slug = slugify(String(value))
      return next
    })
  }

  async function handleImage(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setUploading(true)
    try {
      update('image_url', await uploadEventImage(file))
    } catch {
      setMessage({ kind: 'error', text: t('form.uploadError') })
    } finally {
      setUploading(false)
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!form) return
    setSaving(true)
    setMessage(null)
    const payload = {
      ...form,
      image_url: form.image_url || null,
      display_from: form.display_from || null,
      display_to: form.display_to || null,
    }
    try {
      const saved = await fetchJson<EventAdmin>(eventId ? `${API_BASE}/manage/${eventId}` : `${API_BASE}/manage`, {
        method: eventId ? 'PATCH' : 'POST',
        body: JSON.stringify(payload),
      })
      if (!eventId) {
        navigate(`${EVENTS_PATH}/manage/${saved.id}`, { replace: true })
        return
      }
      setForm((current) => (current ? { ...current, full_text: saved.full_text } : current))
      setMessage({ kind: 'ok', text: t('form.saved') })
    } catch (err) {
      const status = (err as { status?: number }).status
      setMessage({ kind: 'error', text: status === 409 ? t('form.slugTaken') : status === 422 ? t('form.invalid') : t('form.saveError') })
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mx-auto max-w-4xl space-y-5 px-6 py-12 text-slate-900 dark:text-slate-100">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-3xl font-semibold tracking-tight">{eventId ? t('form.editTitle') : t('form.newTitle')}</h1>
        <div className="flex gap-3 text-sm">
          <Link to={`${EVENTS_PATH}/manage`} className="rounded-lg border border-slate-200 px-3 py-1.5 hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800">
            {t('form.backToList')}
          </Link>
          {eventId && form.status === 'published' && (
            <Link to={eventPath(form.slug)} className="rounded-lg border border-slate-200 px-3 py-1.5 hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800">
              {t('form.view')}
            </Link>
          )}
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <label htmlFor="ev-title" className={labelClass}>{t('form.title')}</label>
          <input id="ev-title" required maxLength={200} value={form.title} onChange={(e) => update('title', e.target.value)} className={inputClass} />
        </div>
        <div className="sm:col-span-2">
          <label htmlFor="ev-slug" className={labelClass}>{t('form.slug')}</label>
          <input
            id="ev-slug"
            required
            maxLength={200}
            pattern="[a-z0-9]+(-[a-z0-9]+)*"
            value={form.slug}
            onChange={(e) => {
              setSlugTouched(true)
              update('slug', e.target.value)
            }}
            className={`${inputClass} font-mono text-sm`}
          />
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{t('form.slugHint', { path: eventPath(form.slug || '…') })}</p>
        </div>
        <div className="sm:col-span-2">
          <label htmlFor="ev-short" className={labelClass}>{t('form.shortDescription')}</label>
          <textarea id="ev-short" rows={2} maxLength={500} value={form.short_description} onChange={(e) => update('short_description', e.target.value)} className={inputClass} />
        </div>

        <div>
          <label htmlFor="ev-date" className={labelClass}>{t('form.eventDate')}</label>
          <input id="ev-date" type="date" required value={form.event_date} onChange={(e) => update('event_date', e.target.value)} className={inputClass} />
        </div>
        <div>
          <label htmlFor="ev-status" className={labelClass}>{t('form.status')}</label>
          <select id="ev-status" value={form.status} onChange={(e) => update('status', e.target.value as EventStatus)} className={inputClass}>
            {(['draft', 'published', 'deleted'] as const).map((status) => (
              <option key={status} value={status}>{t(`status.${status}`)}</option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="ev-from" className={labelClass}>{t('form.displayFrom')}</label>
          <input id="ev-from" type="date" value={form.display_from} onChange={(e) => update('display_from', e.target.value)} className={inputClass} />
        </div>
        <div>
          <label htmlFor="ev-to" className={labelClass}>{t('form.displayTo')}</label>
          <input id="ev-to" type="date" value={form.display_to} min={form.display_from || undefined} onChange={(e) => update('display_to', e.target.value)} className={inputClass} />
        </div>
        <p className="-mt-2 text-xs text-slate-500 sm:col-span-2 dark:text-slate-400">{t('form.displayHint')}</p>
        <label className="flex items-center gap-2 text-sm sm:col-span-2">
          <input type="checkbox" checked={form.pinned} onChange={(e) => update('pinned', e.target.checked)} />
          {t('form.pinned')}
        </label>
      </div>

      <div>
        <span className={labelClass}>{t('form.image')}</span>
        <div className="flex flex-wrap items-center gap-4">
          <div className="h-28 w-40 overflow-hidden rounded-xl bg-slate-100 dark:bg-slate-800">
            {form.image_url && <img src={form.image_url} alt="" className="h-full w-full object-cover" />}
          </div>
          <div className="flex gap-2 text-sm">
            <button type="button" onClick={() => fileRef.current?.click()} disabled={uploading} className="rounded-lg border border-slate-300 px-3 py-1.5 disabled:opacity-50 dark:border-slate-700">
              {uploading ? t('common.loading') : form.image_url ? t('form.imageReplace') : t('form.imageUpload')}
            </button>
            {form.image_url && (
              <button type="button" onClick={() => update('image_url', '')} className="rounded-lg px-3 py-1.5 text-red-600 dark:text-red-400">
                {t('form.imageRemove')}
              </button>
            )}
          </div>
          <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp,image/gif" className="hidden" onChange={handleImage} />
        </div>
      </div>

      <div>
        <span className={labelClass}>{t('form.fullText')}</span>
        <RichTextEditor
          value={form.full_text}
          onChange={(html) => update('full_text', html)}
          uploadImage={uploadEventImage}
          loadMentionables={loadEventMentionables}
        />
      </div>

      {message && (
        <p role="status" className={`text-sm ${message.kind === 'ok' ? 'text-emerald-700 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
          {message.text}
        </p>
      )}
      <button type="submit" disabled={saving} className="rounded-lg bg-slate-900 px-5 py-2 font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900">
        {saving ? t('form.saving') : t('form.save')}
      </button>
    </form>
  )
}

/** /events/manage/new and /events/manage/:id. */
export default function EventFormPage() {
  const { t } = useTranslation('event_calendar')
  const { id } = useParams<{ id: string }>()
  usePageMeta({ title: id ? t('form.editTitle') : t('form.newTitle') })
  return (
    <EditorGate>
      <EventForm key={id ?? 'new'} eventId={id} />
    </EditorGate>
  )
}
