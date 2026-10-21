/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { FormBuilder } from '../forms'
import { formatEventWhen, type EventAdmin } from '../event_calendar/api'
import BlockEditor, { blockPayload } from './BlockEditor'
import BookingsAdmin from './BookingsAdmin'
import {
  API_BASE,
  BOOKINGS_PATH,
  downloadFile,
  errorsOf,
  fetchJson,
  registrationLink,
  sendJson,
  statusOf,
  type Access,
  type Block,
  type RegistrationAdmin,
  type RegistrationListItem,
} from './api'
import {
  BookingsGate,
  PageMessage,
  cardClass,
  dangerButtonClass,
  errorClass,
  inputClass,
  labelClass,
  mutedClass,
  okClass,
  primaryButtonClass,
  secondaryButtonClass,
  useNoindexMeta,
} from './ui'

const ACCESS_MODES: Access[] = ['public', 'authenticated', 'link']
const EVENTS_API = '/api/modules/event_calendar'

// --- The list ----------------------------------------------------------------------------------------

/** /bookings/manage - every registration with how many bookings it has. */
function RegistrationList() {
  const { t, i18n } = useTranslation('event_booking')
  const [items, setItems] = useState<RegistrationListItem[] | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    fetchJson<RegistrationListItem[]>(`${API_BASE}/manage/registrations`)
      .then(setItems)
      .catch(() => setFailed(true))
  }, [])

  return (
    <div className="mx-auto max-w-4xl px-4 py-10 text-slate-900 sm:px-6 sm:py-12 dark:text-slate-100">
      <h1 className="mb-2 text-2xl font-semibold tracking-tight sm:text-3xl">{t('manage.title')}</h1>
      <p className={`mb-6 ${mutedClass}`}>
        {t('manage.hint')} <Link to="/events/manage" className="underline">{t('manage.toEvents')}</Link>
      </p>
      {failed && <p role="alert" className={errorClass}>{t('manage.loadError')}</p>}
      {items === null && !failed && <p className={mutedClass}>{t('common.loading')}</p>}
      {items && items.length === 0 && <p className={mutedClass}>{t('manage.empty')}</p>}
      {items && items.length > 0 && (
        <ul className="divide-y divide-slate-200 overflow-hidden rounded-2xl border border-slate-200 bg-white dark:divide-slate-800 dark:border-slate-800 dark:bg-slate-900">
          {items.map((item) => (
            <li key={item.id}>
              <Link to={`${BOOKINGS_PATH}/manage/${item.id}`} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-800/60">
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">{item.name}</span>
                  <span className="block truncate text-xs text-slate-500 dark:text-slate-400">
                    {item.event_title} · {formatEventWhen({ start_date: item.event_start_date, end_date: item.event_end_date, start_time: null, end_time: null }, i18n.language)}
                  </span>
                </span>
                <span className="text-sm text-slate-500 dark:text-slate-400">{t(`access.${item.access}`)}</span>
                <span className="text-sm">{item.is_open ? t('manage.open') : t('manage.closedState')}</span>
                <span className="text-sm">{t('manage.counts', { confirmed: item.confirmed_count, cancelled: item.cancelled_count })}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function ManageRegistrationsPage() {
  const { t } = useTranslation('event_booking')
  useNoindexMeta(t('manage.title'))
  return (
    <BookingsGate>
      <RegistrationList />
    </BookingsGate>
  )
}

// --- The editor --------------------------------------------------------------------------------------

interface Draft {
  name: string
  description: string
  access: Access
  capacity: number
  is_open: boolean
  blocks: Block[]
}

function CopyLink({ url }: { url: string }) {
  const { t } = useTranslation('event_booking')
  const [copied, setCopied] = useState(false)
  async function copy() {
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // clipboard blocked: the address is shown and can be selected by hand
    }
  }
  return (
    <div className="flex flex-wrap items-center gap-2">
      <input readOnly aria-label={t('editor.linkLabel')} value={url} onFocus={(e) => e.currentTarget.select()} className={`${inputClass} min-w-0 flex-1 basis-64 text-sm`} />
      <button type="button" onClick={copy} className={secondaryButtonClass}>{copied ? t('editor.copied') : t('editor.copy')}</button>
    </div>
  )
}

function RegistrationEditor({ registrationId }: { registrationId: string | undefined }) {
  const { t, i18n } = useTranslation('event_booking')
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const eventId = params.get('event')
  const [registration, setRegistration] = useState<RegistrationAdmin | null>(null)
  const [event, setEvent] = useState<EventAdmin | null>(null)
  const [draft, setDraft] = useState<Draft | null>(null)
  const [loadFailed, setLoadFailed] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ kind: 'ok' | 'error'; lines: string[] } | null>(null)
  const [toolMessage, setToolMessage] = useState<string | null>(null)

  function draftOf(source: RegistrationAdmin): Draft {
    return {
      name: source.name,
      description: source.description,
      access: source.access,
      capacity: source.capacity,
      is_open: source.is_open,
      blocks: source.blocks.map(({ id: _id, position: _position, ...block }) => block),
    }
  }

  useEffect(() => {
    let cancelled = false
    if (registrationId) {
      fetchJson<RegistrationAdmin>(`${API_BASE}/manage/registrations/${registrationId}`)
        .then((found) => {
          if (cancelled) return
          setRegistration(found)
          setDraft(draftOf(found))
        })
        .catch(() => !cancelled && setLoadFailed(true))
    } else if (eventId) {
      fetchJson<EventAdmin>(`${EVENTS_API}/manage/${eventId}`)
        .then((found) => {
          if (cancelled) return
          setEvent(found)
          setDraft({ name: found.title, description: '', access: 'public', capacity: 1, is_open: true, blocks: [] })
        })
        .catch(() => !cancelled && setLoadFailed(true))
    }
    return () => {
      cancelled = true
    }
  }, [registrationId, eventId])

  if (!registrationId && !eventId) {
    return (
      <PageMessage>
        {t('editor.needEvent')} <Link to="/events/manage" className="underline">{t('manage.toEvents')}</Link>
      </PageMessage>
    )
  }
  if (loadFailed) return <PageMessage>{t('editor.loadError')}</PageMessage>
  if (!draft) return <PageMessage>{t('common.loading')}</PageMessage>

  const update = (patch: Partial<Draft>) => setDraft({ ...draft, ...patch })
  const heading = registration ?? event
  const eventTitle = registration?.event_title ?? event?.title ?? ''

  async function save(submit: FormEvent) {
    submit.preventDefault()
    if (!draft) return
    setSaving(true)
    setMessage(null)
    const body = {
      name: draft.name,
      description: draft.description,
      access: draft.access,
      capacity: draft.capacity,
      is_open: draft.is_open,
      blocks: draft.blocks.map(blockPayload),
    }
    try {
      if (registrationId) {
        const saved = await sendJson<RegistrationAdmin>(`${API_BASE}/manage/registrations/${registrationId}`, 'PATCH', body)
        setRegistration(saved)
        setMessage({ kind: 'ok', lines: [t('editor.saved')] })
      } else {
        const created = await sendJson<RegistrationAdmin>(`${API_BASE}/manage/registrations`, 'POST', { ...body, event_id: eventId })
        navigate(`${BOOKINGS_PATH}/manage/${created.id}`, { replace: true })
      }
    } catch (err) {
      const found = errorsOf(err)
      const lines = Object.values(found).flat()
      if (statusOf(err) === 409 && found.event_id === 'has_registration') setMessage({ kind: 'error', lines: [t('editor.hasRegistration')] })
      else if (lines.length > 0) setMessage({ kind: 'error', lines })
      else setMessage({ kind: 'error', lines: [t('editor.saveError')] })
    } finally {
      setSaving(false)
    }
  }

  async function regenerate() {
    if (!registration || !window.confirm(t('editor.regenerateConfirm'))) return
    setToolMessage(null)
    try {
      setRegistration(await sendJson<RegistrationAdmin>(`${API_BASE}/manage/registrations/${registration.id}/regenerate-link`, 'POST', {}))
      setToolMessage(t('editor.regenerated'))
    } catch {
      setToolMessage(t('editor.toolError'))
    }
  }

  async function purge() {
    if (!window.confirm(t('editor.purgeConfirm'))) return
    setToolMessage(null)
    try {
      const result = await sendJson<{ deleted_bookings: number }>(`${API_BASE}/manage/purge`, 'POST', {})
      setToolMessage(t('editor.purged', { count: result.deleted_bookings }))
    } catch {
      setToolMessage(t('editor.toolError'))
    }
  }

  async function exportCsv() {
    if (!registration) return
    setToolMessage(null)
    try {
      await downloadFile(`${API_BASE}/manage/registrations/${registration.id}/bookings.csv`, `bookings-${registration.id.slice(0, 8)}.csv`)
    } catch {
      setToolMessage(t('editor.toolError'))
    }
  }

  async function remove() {
    if (!registration || !window.confirm(t('editor.deleteConfirm'))) return
    setToolMessage(null)
    try {
      await fetchJson(`${API_BASE}/manage/registrations/${registration.id}`, { method: 'DELETE' })
      navigate(`${BOOKINGS_PATH}/manage`, { replace: true })
    } catch (err) {
      setToolMessage(statusOf(err) === 409 ? t('editor.deleteBlocked') : t('editor.toolError'))
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-8 px-4 py-10 text-slate-900 sm:px-6 sm:py-12 dark:text-slate-100">
      <div>
        <Link to={`${BOOKINGS_PATH}/manage`} className="text-sm underline">{t('editor.backToList')}</Link>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">{registrationId ? t('editor.editTitle') : t('editor.newTitle')}</h1>
        {heading && (
          <p className={`mt-1 ${mutedClass}`}>
            {t('editor.forEvent')}:{' '}
            <Link to={`/events/manage/${registration?.event_id ?? event?.id}`} className="underline">{eventTitle}</Link>
            {' · '}
            {formatEventWhen(
              registration
                ? { start_date: registration.event_start_date, end_date: registration.event_end_date, start_time: registration.event_start_time, end_time: registration.event_end_time }
                : event!,
              i18n.language,
            )}
          </p>
        )}
      </div>

      <form onSubmit={save} className="space-y-6">
        <div className={`${cardClass} space-y-4`}>
          <div>
            <label htmlFor="reg-name" className={labelClass}>{t('editor.name')}</label>
            <input id="reg-name" type="text" required maxLength={200} value={draft.name} onChange={(e) => update({ name: e.target.value })} className={inputClass} />
          </div>
          <div>
            <label htmlFor="reg-description" className={labelClass}>{t('editor.description')}</label>
            <textarea id="reg-description" rows={3} maxLength={5000} value={draft.description} onChange={(e) => update({ description: e.target.value })} className={inputClass} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="reg-access" className={labelClass}>{t('editor.access')}</label>
              <select id="reg-access" value={draft.access} onChange={(e) => update({ access: e.target.value as Access })} className={inputClass}>
                {ACCESS_MODES.map((mode) => (
                  <option key={mode} value={mode}>{t(`access.${mode}`)}</option>
                ))}
              </select>
              <p className={`mt-1 ${mutedClass}`}>{t(`editor.accessHints.${draft.access}`)}</p>
            </div>
            <div>
              <label htmlFor="reg-capacity" className={labelClass}>{t('editor.capacity')}</label>
              <input id="reg-capacity" type="number" required min={1} max={1000} value={draft.capacity} onChange={(e) => update({ capacity: Number(e.target.value) })} className={inputClass} />
              <p className={`mt-1 ${mutedClass}`}>{t('editor.capacityHint')}</p>
            </div>
          </div>
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" checked={draft.is_open} onChange={(e) => update({ is_open: e.target.checked })} className="mt-1" />
            <span>{t('editor.isOpen')}</span>
          </label>
        </div>

        <div className="space-y-3">
          <h2 className="text-xl font-semibold tracking-tight">{t('editor.blocksTitle')}</h2>
          <BlockEditor blocks={draft.blocks} capacity={draft.capacity} onChange={(blocks) => update({ blocks })} />
        </div>

        {message && (
          <div role="status" className={message.kind === 'ok' ? okClass : errorClass}>
            {message.lines.map((line) => (
              <p key={line}>{line}</p>
            ))}
          </div>
        )}
        <button type="submit" disabled={saving} className={primaryButtonClass}>{saving ? t('editor.saving') : registrationId ? t('editor.save') : t('editor.create')}</button>
      </form>

      {registration && (
        <>
          <section className={`${cardClass} space-y-3`} aria-labelledby="reg-link-heading">
            <h2 id="reg-link-heading" className="text-xl font-semibold tracking-tight">{t('editor.linkTitle')}</h2>
            <p className={mutedClass}>{registration.access === 'link' ? t('editor.linkHintLink') : t('editor.linkHintOther')}</p>
            <CopyLink url={registrationLink(registration.article_slug, registration.link_token)} />
            <button type="button" onClick={regenerate} className={secondaryButtonClass}>{t('editor.regenerate')}</button>
          </section>

          <section aria-labelledby="reg-questions-heading" className="space-y-3">
            <h2 id="reg-questions-heading" className="text-xl font-semibold tracking-tight">{t('editor.questionsTitle')}</h2>
            <p className={mutedClass}>{t('editor.questionsHint')}</p>
            <FormBuilder formId={registration.form_id} />
          </section>

          <section aria-labelledby="reg-bookings-heading" className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 id="reg-bookings-heading" className="text-xl font-semibold tracking-tight">{t('editor.bookingsTitle', { count: registration.confirmed_count })}</h2>
              <div className="flex flex-wrap gap-2">
                <button type="button" onClick={exportCsv} className={secondaryButtonClass}>{t('editor.exportCsv')}</button>
                <button type="button" onClick={purge} className={secondaryButtonClass}>{t('editor.purge')}</button>
              </div>
            </div>
            <p className={mutedClass}>{t('editor.purgeHint')}</p>
            <BookingsAdmin registrationId={registration.id} />
          </section>

          <section className="space-y-2 border-t border-slate-200 pt-6 dark:border-slate-800">
            <button type="button" onClick={remove} className={dangerButtonClass}>{t('editor.delete')}</button>
          </section>
          {toolMessage && <p role="status" className={mutedClass}>{toolMessage}</p>}
        </>
      )}
    </div>
  )
}

/** /bookings/manage/new?event=<id> and /bookings/manage/:id. */
export function RegistrationEditorPage() {
  const { t } = useTranslation('event_booking')
  const { id } = useParams<{ id: string }>()
  useNoindexMeta(id ? t('editor.editTitle') : t('editor.newTitle'))
  return (
    <BookingsGate>
      <RegistrationEditor key={id ?? 'new'} registrationId={id} />
    </BookingsGate>
  )
}
