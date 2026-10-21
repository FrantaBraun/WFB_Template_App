/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { rememberReturnPath } from '../../utils/returnPath'
import { FormRenderer, collectAnswers, type FormValues } from '../forms'
import SlotPicker, { type SlotChoice } from './SlotPicker'
import {
  API_BASE,
  BOOKINGS_PATH,
  errorsOf,
  fetchJson,
  formatSlot,
  sendJson,
  statusOf,
  stringErrors,
  type BookingCreated,
  type FreeDay,
  type RegistrationBrief,
  type RegistrationPublic,
  type SlotInfo,
} from './api'
import { errorClass, inputClass, labelClass, mutedClass, primaryButtonClass, secondaryButtonClass } from './ui'

/** Names of the field errors the server answers with, as the translation keys that explain them. */
const FIELD_ERROR_KEYS: Record<string, string> = {
  'consent:required': 'errors.consentRequired',
  'slot:not_offered': 'errors.slotNotOffered',
  'slot:full': 'errors.slotFull',
  'email:too_many': 'errors.emailTooMany',
  '_form:closed': 'errors.closed',
  'email:invalid': 'errors.emailInvalid',
  'name:invalid': 'errors.nameInvalid',
}

function withToken(path: string, params: Record<string, string | undefined>, token: string | null): string {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) if (value) query.set(key, value)
  if (token) query.set('token', token)
  const text = query.toString()
  return text ? `${path}?${text}` : path
}

/**
 * The registration of an event, on the article page under each date
 * (contributed to the calendar's "event.actions" slot; context `{ event }`).
 * Renders nothing for an event without a registration - and for one that is
 * reached only by a secret link, unless the page was opened with it (the
 * `?r=` of the address) - so a page looks the same until there is something to
 * offer. Booking is a button that opens the form: pick a day (and a time),
 * fill in name, e-mail, consent and the questions.
 */
export default function BookingPanel({ context }: { context: { event: { id: string } } }) {
  const { t } = useTranslation('event_booking')
  const { user, loading } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [params] = useSearchParams()
  const token = params.get('r')
  const [brief, setBrief] = useState<RegistrationBrief | null>(null)
  const [phase, setPhase] = useState<'idle' | 'form' | 'done'>('idle')
  const [created, setCreated] = useState<BookingCreated | null>(null)

  useEffect(() => {
    let cancelled = false
    setBrief(null)
    fetchJson<RegistrationBrief[]>(withToken(`${API_BASE}/by-events`, { ids: context.event.id }, token))
      .then((found) => !cancelled && setBrief(found[0] ?? null))
      .catch(() => !cancelled && setBrief(null))
    return () => {
      cancelled = true
    }
  }, [context.event.id, token])

  if (!brief) return null

  function signIn() {
    rememberReturnPath(location.pathname + location.search)
    navigate('/login')
  }

  return (
    <section aria-label={brief.name} className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3 text-slate-900 sm:p-4 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100">
      <p className="font-medium">{brief.name}</p>
      {brief.description && <p className="mt-1 whitespace-pre-line text-sm text-slate-600 dark:text-slate-300">{brief.description}</p>}

      {!brief.is_open && <p className={`mt-2 ${mutedClass}`}>{t('panel.closed')}</p>}

      {brief.is_open && brief.requires_login && !user && phase !== 'form' && (
        <div className="mt-3 space-y-2">
          <p className={mutedClass}>{loading ? t('common.loading') : t('panel.loginNeeded')}</p>
          {!loading && (
            <button type="button" onClick={signIn} className={primaryButtonClass}>
              {t('panel.login')}
            </button>
          )}
        </div>
      )}

      {brief.is_open && phase === 'idle' && (!brief.requires_login || user) && (
        <button type="button" onClick={() => setPhase('form')} className={`mt-3 ${primaryButtonClass}`}>
          {t('panel.book')}
        </button>
      )}

      {brief.is_open && phase === 'form' && (
        <BookingForm
          registrationId={brief.registration_id}
          token={token}
          onCancel={() => setPhase('idle')}
          onNeedLogin={signIn}
          onClosed={() => {
            setPhase('idle')
            setBrief({ ...brief, is_open: false })
          }}
          onDone={(booking) => {
            setCreated(booking)
            setPhase('done')
          }}
        />
      )}

      {phase === 'done' && created && <Confirmation booking={created} onClose={() => setPhase('idle')} />}
    </section>
  )
}

function Confirmation({ booking, onClose }: { booking: BookingCreated; onClose: () => void }) {
  const { t, i18n } = useTranslation('event_booking')
  const cancelPath = `${BOOKINGS_PATH}/cancel/${booking.cancel_token}`
  return (
    <div role="status" className="mt-3 space-y-2 rounded-lg border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-100">
      <p className="font-medium">{t('confirmation.title')}</p>
      <p>{formatSlot(booking.slot_date, booking.slot_time, i18n.language, t('picker.allDay'))}</p>
      <p>
        {t('confirmation.cancelHint')}{' '}
        <Link to={cancelPath} className="break-all underline">
          {`${window.location.origin}${cancelPath}`}
        </Link>
      </p>
      <button type="button" onClick={onClose} className={secondaryButtonClass}>
        {t('confirmation.close')}
      </button>
    </div>
  )
}

function BookingForm({
  registrationId,
  token,
  onCancel,
  onNeedLogin,
  onClosed,
  onDone,
}: {
  registrationId: string
  token: string | null
  onCancel: () => void
  onNeedLogin: () => void
  onClosed: () => void
  onDone: (booking: BookingCreated) => void
}) {
  const { t, i18n } = useTranslation('event_booking')
  const { user } = useAuth()
  const [registration, setRegistration] = useState<RegistrationPublic | null>(null)
  const [loadFailed, setLoadFailed] = useState(false)
  const [slot, setSlot] = useState<SlotChoice | null>(null)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [consent, setConsent] = useState(false)
  const [fax, setFax] = useState('')
  const [values, setValues] = useState<FormValues>({})
  const [submitting, setSubmitting] = useState(false)
  const [errors, setErrors] = useState<Record<string, string | string[]>>({})
  const [general, setGeneral] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    fetchJson<RegistrationPublic>(withToken(`${API_BASE}/registrations/${registrationId}`, {}, token))
      .then((found) => !cancelled && setRegistration(found))
      .catch(() => !cancelled && setLoadFailed(true))
    return () => {
      cancelled = true
    }
  }, [registrationId, token])

  // A signed-in visitor's name and address are filled in for them (they can still change them).
  useEffect(() => {
    if (!user) return
    setName((current) => current || [user.first_name, user.last_name].filter(Boolean).join(' '))
    setEmail((current) => current || user.email || '')
  }, [user])

  const loadDays = useCallback(
    (month?: string) =>
      fetchJson<{ days: FreeDay[] }>(withToken(`${API_BASE}/registrations/${registrationId}/days`, { month }, token)).then((r) => r.days),
    [registrationId, token],
  )
  const loadSlots = useCallback(
    (date: string) =>
      fetchJson<{ slots: SlotInfo[] }>(withToken(`${API_BASE}/registrations/${registrationId}/slots`, { date }, token)).then((r) => r.slots),
    [registrationId, token],
  )

  function messageFor(field: string, code: string): string {
    const key = FIELD_ERROR_KEYS[`${field}:${code}`]
    return key ? t(key) : t('errors.unknown', { code })
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!registration) return
    setGeneral(null)
    setErrors({})
    if (!slot) {
      setErrors({ slot: 'required' })
      return
    }
    setSubmitting(true)
    try {
      const created = await sendJson<BookingCreated>(withToken(`${API_BASE}/registrations/${registrationId}/bookings`, {}, token), 'POST', {
        slot_date: slot.date,
        slot_time: slot.time ? slot.time.slice(0, 5) : null,
        name,
        email,
        consent,
        answers: collectAnswers(registration.questions, values),
        language: i18n.resolvedLanguage ?? i18n.language,
        fax,
      })
      onDone(created)
    } catch (err) {
      const status = statusOf(err)
      const found = errorsOf(err)
      if (status === 401) {
        onNeedLogin()
      } else if (status === 409 && found.slot === 'full') {
        setErrors({ slot: 'full' })
        setSlot(null)
        setReloadKey((key) => key + 1) // the days and times shown are out of date now
      } else if (status === 409 && found._form === 'closed') {
        onClosed()
      } else if ((status === 422 || status === 409) && Object.keys(found).length > 0) {
        setErrors(found)
      } else if (status === 422) {
        setGeneral(t('errors.invalid'))
      } else {
        setGeneral(t('errors.generic'))
      }
    } finally {
      setSubmitting(false)
    }
  }

  if (loadFailed) return <p role="alert" className={`mt-3 ${errorClass}`}>{t('form.loadError')}</p>
  if (!registration) return <p className={`mt-3 ${mutedClass}`}>{t('common.loading')}</p>

  const slotError = errors.slot ? (errors.slot === 'required' ? t('errors.slotRequired') : messageFor('slot', String(errors.slot))) : null
  const questionErrors = stringErrors(errors)
  const fieldError = (field: string) => (typeof errors[field] === 'string' ? messageFor(field, errors[field] as string) : null)
  const idPrefix = `booking-${registrationId}`

  return (
    <form onSubmit={submit} className="mt-3 space-y-4">
      <SlotPicker
        finiteDays={registration.finite_days}
        maxDaysAhead={registration.max_days_ahead}
        loadDays={loadDays}
        loadSlots={loadSlots}
        value={slot}
        onChange={setSlot}
        disabled={submitting}
        error={slotError}
        idPrefix={idPrefix}
        reloadKey={reloadKey}
      />

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor={`${idPrefix}-name`} className={labelClass}>{t('form.name')}</label>
          <input
            id={`${idPrefix}-name`}
            type="text"
            required
            maxLength={200}
            autoComplete="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={submitting}
            aria-invalid={fieldError('name') ? true : undefined}
            aria-describedby={fieldError('name') ? `${idPrefix}-name-error` : undefined}
            className={inputClass}
          />
          {fieldError('name') && <p id={`${idPrefix}-name-error`} role="alert" className={`mt-1 ${errorClass}`}>{fieldError('name')}</p>}
        </div>
        <div>
          <label htmlFor={`${idPrefix}-email`} className={labelClass}>{t('form.email')}</label>
          <input
            id={`${idPrefix}-email`}
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={submitting}
            aria-invalid={fieldError('email') ? true : undefined}
            aria-describedby={fieldError('email') ? `${idPrefix}-email-error` : undefined}
            className={inputClass}
          />
          {fieldError('email') && <p id={`${idPrefix}-email-error`} role="alert" className={`mt-1 ${errorClass}`}>{fieldError('email')}</p>}
        </div>
      </div>

      {registration.questions.length > 0 && (
        <FormRenderer questions={registration.questions} values={values} onChange={setValues} errors={questionErrors} disabled={submitting} idPrefix={idPrefix} />
      )}

      {/* The honeypot: invisible to people (and to screen readers), tempting to a bot that fills in every field. */}
      <div aria-hidden="true" className="absolute -left-[10000px] h-0 w-0 overflow-hidden">
        <label>
          Fax
          <input type="text" name="fax" tabIndex={-1} autoComplete="off" value={fax} onChange={(e) => setFax(e.target.value)} />
        </label>
      </div>

      <div>
        <label className="flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            required
            checked={consent}
            onChange={(e) => setConsent(e.target.checked)}
            disabled={submitting}
            aria-invalid={fieldError('consent') ? true : undefined}
            className="mt-1"
          />
          <span>
            {t('form.consent')}
            {registration.privacy_url && (
              <>
                {' '}
                <a href={registration.privacy_url} target="_blank" rel="noopener noreferrer" className="underline">
                  {t('form.consentLink')}
                </a>
              </>
            )}
          </span>
        </label>
        {fieldError('consent') && <p role="alert" className={`mt-1 ${errorClass}`}>{fieldError('consent')}</p>}
      </div>

      {(general || fieldError('_form')) && <p role="alert" className={errorClass}>{general ?? fieldError('_form')}</p>}

      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" disabled={submitting} className={primaryButtonClass}>
          {submitting ? t('form.submitting') : t('form.submit')}
        </button>
        <button type="button" onClick={onCancel} disabled={submitting} className={secondaryButtonClass}>
          {t('form.cancel')}
        </button>
      </div>
    </form>
  )
}
