/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import {
  API_BASE,
  conflictOf,
  errorsOf,
  fetchJson,
  formatDateTime,
  formatDay,
  formatTime,
  sendJson,
  statusOf,
  type CancelResult,
  type Conflict,
  type ExceptionDay,
  type ReservationAdmin,
} from './api'
import { cardClass, dangerButtonClass, errorClass, inputClass, labelClass, mutedClass, okClass, primaryButtonClass, secondaryButtonClass } from './ui'

/** The text of an error code the API gives for a field (see the locales' `errors.codes`). */
export function useErrorText() {
  const { t } = useTranslation('table_reservations')
  return (code: string) => t(`errors.codes.${code}`, { defaultValue: t('errors.unknown', { code }) })
}

/** What happened with the e-mail to the guest, as a sentence - from what the reservation records. */
function EmailStatus({ reservation }: { reservation: ReservationAdmin }) {
  const { t } = useTranslation('table_reservations')
  if (reservation.notified === true) return <span className={okClass}>{t('card.emailSent')}</span>
  if (reservation.notified === false) return <span className={errorClass}>{t('card.emailFailed', { error: reservation.email_error ?? '' })}</span>
  return <span className={mutedClass}>{t('card.emailNotAsked')}</span>
}

interface CancelFormProps {
  reservation: ReservationAdmin
  onDone: (result: CancelResult) => void
  onClose: () => void
}

/**
 * The pub cancels one reservation: a message for the guest (optional, goes into
 * the e-mail and is kept with the reservation) and whether to send that e-mail.
 * The cancellation stands even when the e-mail cannot be sent - the result says
 * which it was.
 */
function CancelForm({ reservation, onDone, onClose }: CancelFormProps) {
  const { t } = useTranslation('table_reservations')
  const [note, setNote] = useState('')
  const [notify, setNotify] = useState(true)
  const [busy, setBusy] = useState(false)
  const [failed, setFailed] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setFailed(false)
    try {
      const result = await sendJson<CancelResult>(`${API_BASE}/manage/reservations/${reservation.id}/cancel`, 'POST', {
        note: note.trim() || null,
        notify,
      })
      onDone(result)
    } catch {
      setFailed(true)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="mt-3 space-y-3 rounded-xl border border-red-200 bg-red-50/50 p-3 dark:border-red-900 dark:bg-red-950/30">
      <p className="text-sm font-medium">{t('cancelForm.title', { name: reservation.name })}</p>
      <div>
        <label htmlFor={`note-${reservation.id}`} className={labelClass}>{t('cancelForm.note')}</label>
        <textarea
          id={`note-${reservation.id}`}
          rows={3}
          maxLength={1000}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder={t('cancelForm.notePlaceholder')}
          className={inputClass}
        />
        <p className={`mt-1 ${mutedClass}`}>{t('cancelForm.noteHint')}</p>
      </div>
      <label className="flex items-start gap-2 text-sm">
        <input type="checkbox" checked={notify} onChange={(e) => setNotify(e.target.checked)} className="mt-1" />
        <span>{t('cancelForm.notify', { email: reservation.email })}</span>
      </label>
      {failed && <p role="alert" className={errorClass}>{t('cancelForm.failed')}</p>}
      <div className="flex flex-wrap gap-2">
        <button type="submit" disabled={busy} className={dangerButtonClass}>
          {busy ? t('cancelForm.cancelling') : t('cancelForm.confirm')}
        </button>
        <button type="button" onClick={onClose} disabled={busy} className={secondaryButtonClass}>
          {t('cancelForm.keep')}
        </button>
      </div>
    </form>
  )
}

interface CardProps {
  reservation: ReservationAdmin
  /** Present = a confirmed reservation can be cancelled from here. */
  onCancelled?: (result: CancelResult) => void
  /** Show the date too (in lists that are not of one day). */
  showDay?: boolean
}

/** One reservation with everything the pub knows, and (when confirmed) the way to cancel it with a message. */
export function ReservationCard({ reservation, onCancelled, showDay = false }: CardProps) {
  const { t, i18n } = useTranslation('table_reservations')
  const language = i18n.resolvedLanguage ?? i18n.language
  const [cancelling, setCancelling] = useState(false)
  const cancelled = reservation.status === 'cancelled'

  return (
    <li className={`rounded-xl border p-3 ${cancelled ? 'border-slate-200 bg-slate-50 text-slate-500 dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-400' : 'border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900'}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <p className={`font-medium ${cancelled ? 'line-through' : ''}`}>
          {showDay && `${formatDay(reservation.day, language, 'short')}, `}
          {formatTime(reservation.start_time)}–{formatTime(reservation.end_time)}
        </p>
        <p className="text-sm">
          {reservation.kind === 'whole_venue' ? t('card.wholeVenue') : reservation.table_name ?? t('card.table')}
          {' · '}
          {t('card.party', { count: reservation.party_size })}
        </p>
      </div>
      <p className="mt-1 text-sm">
        <span className="font-medium">{reservation.name}</span>
        {' · '}
        <a href={`mailto:${reservation.email}`} className="underline">{reservation.email}</a>
        {reservation.phone && (
          <>
            {' · '}
            <a href={`tel:${reservation.phone}`} className="underline">{reservation.phone}</a>
          </>
        )}
      </p>
      {reservation.note && <p className="mt-1 text-sm">„{reservation.note}“</p>}
      {cancelled && (
        <div className="mt-2 space-y-0.5 text-sm">
          <p>
            {t(reservation.cancelled_by === 'admin' ? 'card.cancelledByPub' : 'card.cancelledByGuest')}
            {reservation.cancelled_at && ` (${formatDateTime(reservation.cancelled_at, language)})`}
          </p>
          {reservation.cancel_note && <p>{t('card.messageSent')}: „{reservation.cancel_note}“</p>}
          {reservation.cancelled_by === 'admin' && <p><EmailStatus reservation={reservation} /></p>}
        </div>
      )}
      {!cancelled && onCancelled && !cancelling && (
        <div className="mt-2">
          <button type="button" onClick={() => setCancelling(true)} className={dangerButtonClass}>
            {t('card.cancel')}
          </button>
        </div>
      )}
      {!cancelled && onCancelled && cancelling && (
        <CancelForm
          reservation={reservation}
          onClose={() => setCancelling(false)}
          onDone={(result) => {
            setCancelling(false)
            onCancelled(result)
          }}
        />
      )}
    </li>
  )
}

/**
 * The reservations that stand in the way of a change (closing a day, shortening
 * hours, taking a table out of use): each is cancelled by the pub, one by one,
 * with its own message to the guest. Cancelled ones stay listed (so the pub sees
 * what it has done) and the count of what is left goes down; at zero the change can
 * be saved again. The change is NOT retried by itself - saving it is the pub's act.
 */
export function ConflictBox({ conflict, onChanged }: { conflict: Conflict; onChanged?: (result: CancelResult) => void }) {
  const { t } = useTranslation('table_reservations')
  const [items, setItems] = useState(conflict.reservations)
  const hidden = Math.max(0, conflict.total - conflict.reservations.length)
  const left = items.filter((item) => item.status === 'confirmed').length + hidden

  return (
    <div role="region" aria-label={t('conflict.title')} className="space-y-3 rounded-xl border border-amber-300 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-950/30">
      <p className="text-sm font-medium">{t('conflict.title', { count: left })}</p>
      <p className="text-sm">{t('conflict.hint')}</p>
      {hidden > 0 && <p className="text-sm">{t('conflict.more', { count: hidden })}</p>}
      <ul className="space-y-2">
        {items.map((item) => (
          <ReservationCard
            key={item.id}
            reservation={item}
            showDay
            onCancelled={(result) => {
              setItems((previous) => previous.map((entry) => (entry.id === result.reservation.id ? result.reservation : entry)))
              onChanged?.(result)
            }}
          />
        ))}
      </ul>
      {left === 0 && <p role="status" className={okClass}>{t('conflict.resolved')}</p>}
    </div>
  )
}

/** "HH:MM" for a time input from the server's "HH:MM:SS" (or a default). */
function timeValue(value: string | null | undefined, fallback: string): string {
  return value ? formatTime(value) : fallback
}

interface ExceptionFormProps {
  day: string
  /** The one-off change that exists for this day, if any. */
  existing: ExceptionDay | null
  /** Called with the saved change, or null when it was removed. */
  onSaved: (exception: ExceptionDay | null) => void
  /** Called when a reservation was cancelled on the way (the data around it is out of date). */
  onChanged?: () => void
  onClose?: () => void
}

/**
 * A one-off change of one date: closed (with a reason visitors see) or other
 * hours - and removing it again. A day with reservations cannot be closed or
 * shortened past them: the server answers 409 with the reservations and this
 * form shows them to be cancelled one by one (ConflictBox), after which the
 * pub saves the change again.
 */
export function ExceptionForm({ day, existing, onSaved, onChanged, onClose }: ExceptionFormProps) {
  const { t } = useTranslation('table_reservations')
  const errorText = useErrorText()
  const [closed, setClosed] = useState(existing ? existing.is_closed : true)
  const [opens, setOpens] = useState(timeValue(existing?.opens, '16:00'))
  const [closes, setCloses] = useState(timeValue(existing?.closes, '22:00'))
  const [reason, setReason] = useState(existing?.reason ?? '')
  const [busy, setBusy] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [general, setGeneral] = useState<string | null>(null)
  const [conflict, setConflict] = useState<{ id: number; data: Conflict } | null>(null)
  const [saved, setSaved] = useState(false)

  async function run(action: () => Promise<ExceptionDay | null>) {
    setBusy(true)
    setErrors({})
    setGeneral(null)
    setSaved(false)
    try {
      const result = await action()
      setConflict(null)
      setSaved(true)
      onSaved(result)
    } catch (err) {
      const found = conflictOf(err)
      if (found) {
        setConflict({ id: Date.now(), data: found })
      } else if (statusOf(err) === 422 && Object.keys(errorsOf(err)).length > 0) {
        setErrors(errorsOf(err))
      } else {
        setGeneral(t('errors.generic'))
      }
    } finally {
      setBusy(false)
    }
  }

  function save(event: FormEvent) {
    event.preventDefault()
    void run(() =>
      sendJson<ExceptionDay>(`${API_BASE}/manage/exceptions/${day}`, 'PUT', {
        is_closed: closed,
        opens: closed ? null : opens,
        closes: closed ? null : closes,
        reason: reason.trim() || null,
      }),
    )
  }

  function restore() {
    void run(async () => {
      await fetchJson<void>(`${API_BASE}/manage/exceptions/${day}`, { method: 'DELETE' })
      return null
    })
  }

  return (
    <div className="space-y-3">
      <form onSubmit={save} className="space-y-3">
        <fieldset className="space-y-2">
          <legend className="mb-1 text-sm font-medium">{t('exception.kind')}</legend>
          <label className="flex items-center gap-2 text-sm">
            <input type="radio" name={`exception-kind-${day}`} checked={closed} onChange={() => setClosed(true)} />
            {t('exception.closed')}
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="radio" name={`exception-kind-${day}`} checked={!closed} onChange={() => setClosed(false)} />
            {t('exception.otherHours')}
          </label>
        </fieldset>
        {!closed && (
          <div className="flex flex-wrap gap-3">
            <div>
              <label htmlFor={`exception-opens-${day}`} className={labelClass}>{t('hoursPage.opens')}</label>
              <input id={`exception-opens-${day}`} type="time" required value={opens} onChange={(e) => setOpens(e.target.value)} className={inputClass} aria-invalid={errors.opens ? true : undefined} />
              {errors.opens && <p role="alert" className={`mt-1 ${errorClass}`}>{errorText(errors.opens)}</p>}
            </div>
            <div>
              <label htmlFor={`exception-closes-${day}`} className={labelClass}>{t('hoursPage.closes')}</label>
              <input id={`exception-closes-${day}`} type="time" required value={closes} onChange={(e) => setCloses(e.target.value)} className={inputClass} aria-invalid={errors.closes ? true : undefined} />
              {errors.closes && <p role="alert" className={`mt-1 ${errorClass}`}>{errorText(errors.closes)}</p>}
            </div>
          </div>
        )}
        <div>
          <label htmlFor={`exception-reason-${day}`} className={labelClass}>{t('exception.reason')}</label>
          <input id={`exception-reason-${day}`} maxLength={200} value={reason} onChange={(e) => setReason(e.target.value)} placeholder={t('exception.reasonPlaceholder')} className={inputClass} />
          <p className={`mt-1 ${mutedClass}`}>{t('exception.reasonHint')}</p>
        </div>
        {errors.day && <p role="alert" className={errorClass}>{errorText(errors.day)}</p>}
        {general && <p role="alert" className={errorClass}>{general}</p>}
        {saved && !conflict && <p role="status" className={okClass}>{t('exception.saved')}</p>}
        <div className="flex flex-wrap gap-2">
          <button type="submit" disabled={busy} className={primaryButtonClass}>
            {busy ? t('common.saving') : closed ? t('exception.saveClosed') : t('exception.saveHours')}
          </button>
          {existing && (
            <button type="button" onClick={restore} disabled={busy} className={secondaryButtonClass}>
              {t('exception.restore')}
            </button>
          )}
          {onClose && (
            <button type="button" onClick={onClose} disabled={busy} className={secondaryButtonClass}>
              {t('common.close')}
            </button>
          )}
        </div>
      </form>
      {conflict && <ConflictBox key={conflict.id} conflict={conflict.data} onChanged={onChanged ? () => onChanged() : undefined} />}
    </div>
  )
}

/** A white card with a heading, for the sections of the administration pages. */
export function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className={`${cardClass} space-y-4`}>
      <h2 className="text-lg font-semibold">{title}</h2>
      {children}
    </section>
  )
}
