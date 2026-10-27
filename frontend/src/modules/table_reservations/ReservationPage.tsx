/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import usePageMeta from '../../hooks/usePageMeta'
import {
  API_BASE,
  RESERVATIONS_PATH,
  errorsOf,
  fetchJson,
  formatDay,
  formatDuration,
  formatTime,
  fromMinutes,
  isoMonth,
  query,
  sendJson,
  statusOf,
  toMinutes,
  type Availability,
  type Created,
  type DayInfo,
  type Info,
  type Kind,
} from './api'
import MonthGrid from './MonthGrid'
import { HoursList } from './OpeningHours'
import { PageMessage, cardClass, errorClass, inputClass, labelClass, mutedClass, okClass, primaryButtonClass, secondaryButtonClass } from './ui'

/**
 * /reservations - the public page: the opening hours, and a form to reserve a
 * table (the pub picks which, from the number of people) or the whole pub from a
 * time until closing. Anyone may reserve, signed in or not. What is free is read
 * from the server as the guest chooses; whether a time still works is decided
 * again when the form is sent (somebody may have taken it meanwhile).
 */
export default function ReservationPage() {
  const { t } = useTranslation('table_reservations')
  usePageMeta({ title: t('page.title'), description: t('page.description') })
  const [info, setInfo] = useState<Info | null>(null)
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [done, setDone] = useState<Created | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchJson<Info>(`${API_BASE}/info`)
      .then((found) => {
        if (cancelled) return
        setInfo(found)
        setState('ready')
      })
      .catch(() => !cancelled && setState('error'))
    return () => {
      cancelled = true
    }
  }, [])

  if (state === 'loading') return <PageMessage>{t('common.loading')}</PageMessage>
  if (state === 'error' || !info) return <PageMessage>{t('page.loadError')}</PageMessage>

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 text-slate-900 sm:px-6 sm:py-12 dark:text-slate-100">
      <h1 className="mb-2 text-2xl font-semibold tracking-tight sm:text-3xl">{t('page.title')}</h1>
      <p className={`mb-8 max-w-2xl ${mutedClass}`}>{t('page.intro')}</p>
      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_19rem]">
        <div>
          {done ? (
            <Confirmation created={done} onAnother={() => setDone(null)} />
          ) : info.can_reserve ? (
            <ReservationForm info={info} onDone={setDone} />
          ) : (
            <p className={cardClass}>{t('page.unavailable')}</p>
          )}
        </div>
        <HoursCard info={info} />
      </div>
    </div>
  )
}

function HoursCard({ info }: { info: Info }) {
  const { t } = useTranslation('table_reservations')
  return (
    <aside className={`${cardClass} h-fit space-y-4`}>
      <h2 className="text-lg font-semibold">{t('hours.title')}</h2>
      <HoursList info={info} />
    </aside>
  )
}

function Confirmation({ created, onAnother }: { created: Created; onAnother: () => void }) {
  const { t, i18n } = useTranslation('table_reservations')
  const language = i18n.resolvedLanguage ?? i18n.language
  const cancelUrl = `${window.location.origin}${RESERVATIONS_PATH}/cancel/${created.cancel_token}`
  return (
    <div className={`${cardClass} space-y-3`} role="status">
      <h2 className="text-xl font-semibold">{t('confirmation.title')}</h2>
      <p>
        {t(created.kind === 'table' ? 'confirmation.summaryTable' : 'confirmation.summaryWhole', {
          date: formatDay(created.day, language),
          start: formatTime(created.start_time),
          end: formatTime(created.end_time),
        })}
      </p>
      <p className={mutedClass}>{t('confirmation.mailHint')}</p>
      <p className="text-sm">
        {t('confirmation.cancelHint')}{' '}
        <Link to={`${RESERVATIONS_PATH}/cancel/${created.cancel_token}`} className="break-all underline">
          {cancelUrl}
        </Link>
      </p>
      <button type="button" onClick={onAnother} className={secondaryButtonClass}>
        {t('confirmation.another')}
      </button>
    </div>
  )
}

function ReservationForm({ info, onDone }: { info: Info; onDone: (created: Created) => void }) {
  const { t, i18n } = useTranslation('table_reservations')
  const language = i18n.resolvedLanguage ?? i18n.language
  const today = useMemo(() => new Date(), [])
  const limit = useMemo(() => {
    const date = new Date()
    date.setDate(date.getDate() + info.max_days_ahead)
    return date
  }, [info.max_days_ahead])

  const [kind, setKind] = useState<Kind>('table')
  const [party, setParty] = useState('2')
  const [view, setView] = useState({ year: today.getFullYear(), month: today.getMonth() })
  const [days, setDays] = useState<Record<string, DayInfo>>({})
  const [daysFailed, setDaysFailed] = useState(false)
  const [day, setDay] = useState<string | null>(null)
  const [duration, setDuration] = useState(info.default_duration)
  const [availability, setAvailability] = useState<Availability | null>(null)
  const [availabilityState, setAvailabilityState] = useState<'idle' | 'loading' | 'error'>('idle')
  const [start, setStart] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [note, setNote] = useState('')
  const [consent, setConsent] = useState(false)
  const [fax, setFax] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [general, setGeneral] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

  const partyNumber = Number.parseInt(party, 10)
  const maxParty = kind === 'table' ? info.max_party_size : info.max_whole_venue_party
  const partyKnown = Number.isInteger(partyNumber) && partyNumber >= 1
  const partyTooLarge = partyKnown && kind === 'table' && partyNumber > info.max_party_size

  useEffect(() => {
    let cancelled = false
    fetchJson<{ days: DayInfo[] }>(`${API_BASE}/days${query({ month: isoMonth(view.year, view.month) })}`)
      .then((found) => {
        if (cancelled) return
        setDays((previous) => ({ ...previous, ...Object.fromEntries(found.days.map((entry) => [entry.day, entry])) }))
        setDaysFailed(false)
      })
      .catch(() => !cancelled && setDaysFailed(true))
    return () => {
      cancelled = true
    }
  }, [view.year, view.month, reloadKey])

  useEffect(() => {
    if (!day || !partyKnown || partyNumber > info.max_whole_venue_party) {
      setAvailability(null)
      setAvailabilityState('idle')
      return
    }
    let cancelled = false
    setAvailabilityState('loading')
    // A short pause, so typing "12" does not ask about 1 first.
    const handle = window.setTimeout(() => {
      fetchJson<Availability>(`${API_BASE}/availability${query({ day, party_size: partyNumber, duration })}`)
        .then((found) => {
          if (cancelled) return
          setAvailability(found)
          setAvailabilityState('idle')
        })
        .catch(() => !cancelled && setAvailabilityState('error'))
    }, 250)
    return () => {
      cancelled = true
      window.clearTimeout(handle)
    }
  }, [day, partyKnown, partyNumber, duration, reloadKey, info.max_whole_venue_party])

  const times = useMemo(() => {
    if (!availability || !availability.bookable) return []
    if (kind === 'table') return partyTooLarge ? [] : availability.starts.map(formatTime)
    if (!availability.whole_venue_from || !availability.closes) return []
    const last = toMinutes(availability.closes) - info.min_duration
    const out: string[] = []
    for (let minutes = toMinutes(availability.whole_venue_from); minutes <= last; minutes += info.step_minutes) out.push(fromMinutes(minutes))
    return out
  }, [availability, kind, partyTooLarge, info.min_duration, info.step_minutes])

  useEffect(() => {
    if (start && !times.includes(start)) setStart(null)
  }, [times, start])

  const end =
    start && availability?.closes
      ? fromMinutes(Math.min(toMinutes(start) + (kind === 'table' ? duration : 24 * 60), toMinutes(availability.closes)))
      : null

  const monthIndex = view.year * 12 + view.month
  const firstMonth = today.getFullYear() * 12 + today.getMonth()
  const lastMonth = limit.getFullYear() * 12 + limit.getMonth()

  function moveMonth(delta: number) {
    const next = new Date(view.year, view.month + delta, 1)
    setView({ year: next.getFullYear(), month: next.getMonth() })
  }

  function errorText(code: string): string {
    return t(`errors.codes.${code}`, { defaultValue: t('errors.unknown', { code }) })
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!day || !start) {
      setErrors({ start_time: 'pick_time' })
      return
    }
    setSubmitting(true)
    setErrors({})
    setGeneral(null)
    try {
      const created = await sendJson<Created>(`${API_BASE}/reservations`, 'POST', {
        kind,
        day,
        start_time: start,
        duration_minutes: kind === 'table' ? duration : undefined,
        party_size: partyNumber,
        name: name.trim(),
        email: email.trim(),
        phone: phone.trim() || undefined,
        note: note.trim() || undefined,
        consent,
        language,
        fax,
      })
      onDone(created)
    } catch (err) {
      const found = errorsOf(err)
      if (Object.keys(found).length > 0) {
        setErrors(found)
        if (statusOf(err) === 409 || found.day || found.start_time) {
          setStart(null) // what was free has changed
          setReloadKey((key) => key + 1)
        }
      } else {
        setGeneral(t('errors.generic'))
      }
    } finally {
      setSubmitting(false)
    }
  }

  const sectionTitle = 'mb-2 text-lg font-semibold'

  /** Why no time is offered: the party is too big for a table, or the reason the server gave. */
  function noTimesText(): string {
    if (partyTooLarge) return t('form.partyTooLargeForTable')
    const reason = kind === 'table' ? availability?.table_reason : availability?.whole_venue_reason
    return t(`form.noTimes.${reason ?? 'default'}`, { defaultValue: t('form.noTimes.default') })
  }

  return (
    <form onSubmit={submit} className="space-y-8">
      <fieldset className="space-y-2">
        <legend className={sectionTitle}>{t('form.kindTitle')}</legend>
        {(['table', 'whole_venue'] as const).map((value) => (
          <label key={value} className={`flex cursor-pointer items-start gap-3 rounded-xl border p-3 ${kind === value ? 'border-slate-900 dark:border-slate-100' : 'border-slate-200 dark:border-slate-800'}`}>
            <input
              type="radio"
              name="kind"
              value={value}
              checked={kind === value}
              onChange={() => {
                setKind(value)
                setStart(null)
              }}
              className="mt-1"
            />
            <span>
              <span className="block font-medium">{t(value === 'table' ? 'form.kindTable' : 'form.kindWhole')}</span>
              <span className={mutedClass}>{t(value === 'table' ? 'form.kindTableHint' : 'form.kindWholeHint')}</span>
            </span>
          </label>
        ))}
      </fieldset>

      <div>
        <label htmlFor="reservation-party" className={`${sectionTitle} block`}>
          {t('form.partyTitle')}
        </label>
        <input
          id="reservation-party"
          type="number"
          inputMode="numeric"
          min={1}
          max={maxParty}
          required
          value={party}
          onChange={(e) => {
            setParty(e.target.value)
            setErrors((previous) => ({ ...previous, party_size: '' }))
          }}
          aria-invalid={errors.party_size ? true : undefined}
          aria-describedby="reservation-party-hint"
          className={`${inputClass} max-w-32`}
        />
        <p id="reservation-party-hint" className={`mt-1 ${mutedClass}`}>
          {kind === 'table' ? t('form.partyHintTable', { count: info.max_party_size }) : t('form.partyHintWhole', { max: info.max_whole_venue_party })}
        </p>
        {partyKnown && partyNumber > maxParty && <p role="alert" className={`mt-1 ${errorClass}`}>{t('errors.codes.party_too_large')}</p>}
        {partyTooLarge && partyNumber <= info.max_whole_venue_party && (
          <p role="status" className={`mt-1 ${errorClass}`}>
            {t('form.partyTooLargeForTable')}{' '}
            <button type="button" className="underline" onClick={() => setKind('whole_venue')}>
              {t('form.switchToWhole')}
            </button>
          </p>
        )}
        {errors.party_size && <p role="alert" className={`mt-1 ${errorClass}`}>{errorText(errors.party_size)}</p>}
      </div>

      <div>
        <h2 className={sectionTitle}>{t('form.dayTitle')}</h2>
        <div className="max-w-sm">
          <MonthGrid
            year={view.year}
            month={view.month}
            selected={day}
            onSelect={(iso) => {
              setDay(iso)
              setStart(null)
              setErrors((previous) => ({ ...previous, day: '' }))
            }}
            isSelectable={(iso) => days[iso]?.bookable === true}
            describe={(iso) => {
              const entry = days[iso]
              if (!entry) return ''
              if (!entry.is_open) return entry.reason ? `${t('hours.closed')} – ${entry.reason}` : t('hours.closed')
              return entry.bookable ? '' : t('picker.notBookable')
            }}
            onPrevious={() => moveMonth(-1)}
            onNext={() => moveMonth(1)}
            canPrevious={monthIndex > firstMonth}
            canNext={monthIndex < lastMonth}
          />
        </div>
        <p className={`mt-2 ${mutedClass}`}>{day && days[day]?.opens && days[day]?.closes ? t('form.dayOpen', { date: formatDay(day, language), opens: formatTime(days[day].opens!), closes: formatTime(days[day].closes!) }) : t('form.dayHint')}</p>
        {daysFailed && <p role="alert" className={`mt-1 ${errorClass}`}>{t('form.daysError')}</p>}
        {errors.day && <p role="alert" className={`mt-1 ${errorClass}`}>{errorText(errors.day)}</p>}
      </div>

      {kind === 'table' && (
        <div>
          <label htmlFor="reservation-duration" className={`${sectionTitle} block`}>
            {t('form.durationTitle')}
          </label>
          <select
            id="reservation-duration"
            value={duration}
            onChange={(e) => setDuration(Number(e.target.value))}
            className={`${inputClass} max-w-48`}
          >
            {info.duration_options.map((minutes) => (
              <option key={minutes} value={minutes}>
                {formatDuration(minutes)}
              </option>
            ))}
          </select>
          <p className={`mt-1 ${mutedClass}`}>{t('form.durationHint')}</p>
          {errors.duration_minutes && <p role="alert" className={`mt-1 ${errorClass}`}>{errorText(errors.duration_minutes)}</p>}
        </div>
      )}

      <div>
        <h2 className={sectionTitle}>{t('form.timeTitle')}</h2>
        {!day ? (
          <p className={mutedClass}>{t('form.pickDayFirst')}</p>
        ) : !partyKnown || partyNumber > info.max_whole_venue_party ? (
          <p className={mutedClass}>{t('form.pickPartyFirst')}</p>
        ) : availabilityState === 'loading' && !availability ? (
          <p className={mutedClass}>{t('common.loading')}</p>
        ) : availabilityState === 'error' ? (
          <p role="alert" className={errorClass}>{t('form.timesError')}</p>
        ) : !availability ? null : !availability.is_open ? (
          <p className={mutedClass}>
            {t('form.dayClosed')}
            {availability.reason && ` ${availability.reason}`}
          </p>
        ) : times.length === 0 ? (
          <p role="status" className={mutedClass + ' font-bold p-3 border border-red-800 rounded-lg bg-red-100 dark:bg-purple-100'}>{noTimesText()}</p>
        ) : (
          <div role="radiogroup" aria-label={t('form.timeTitle')} className="flex flex-wrap gap-2">
            {times.map((time) => (
              <button
                key={time}
                type="button"
                role="radio"
                aria-checked={start === time}
                onClick={() => {
                  setStart(time)
                  setErrors((previous) => ({ ...previous, start_time: '' }))
                }}
                className={`rounded-lg border px-3 py-1.5 text-sm ${
                  start === time
                    ? 'border-slate-900 bg-slate-900 text-slate-100 dark:border-slate-100 dark:bg-slate-100 dark:text-slate-900'
                    : 'border-slate-200 hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800'
                }`}
              >
                {time}
              </button>
            ))}
          </div>
        )}
        {kind === 'whole_venue' && times.length > 0 && <p className={`mt-2 ${mutedClass}`}>{t('form.wholeUntilClosing')}</p>}
        {start && end && <p className={`mt-2 text-sm ${okClass}`}>{t(kind === 'table' ? 'form.summaryTable' : 'form.summaryWhole', { start, end, count: partyNumber })}</p>}
        {errors.start_time && <p role="alert" className={`mt-1 ${errorClass}`}>{errorText(errors.start_time)}</p>}
      </div>

      <div className="space-y-4">
        <h2 className={sectionTitle}>{t('form.detailsTitle')}</h2>
        <div>
          <label htmlFor="reservation-name" className={labelClass}>{t('form.name')}</label>
          <input id="reservation-name" required maxLength={200} autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} className={inputClass} aria-invalid={errors.name ? true : undefined} />
          {errors.name && <p role="alert" className={`mt-1 ${errorClass}`}>{errorText(errors.name)}</p>}
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="reservation-email" className={labelClass}>{t('form.email')}</label>
            <input id="reservation-email" type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} className={inputClass} aria-invalid={errors.email ? true : undefined} />
            {errors.email && <p role="alert" className={`mt-1 ${errorClass}`}>{errorText(errors.email)}</p>}
          </div>
          <div>
            <label htmlFor="reservation-phone" className={labelClass}>{t('form.phone')}</label>
            <input id="reservation-phone" type="tel" maxLength={40} autoComplete="tel" value={phone} onChange={(e) => setPhone(e.target.value)} className={inputClass} aria-invalid={errors.phone ? true : undefined} />
            {errors.phone && <p role="alert" className={`mt-1 ${errorClass}`}>{errorText(errors.phone)}</p>}
          </div>
        </div>
        <div>
          <label htmlFor="reservation-note" className={labelClass}>{t('form.note')}</label>
          <textarea id="reservation-note" rows={3} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} className={inputClass} aria-invalid={errors.note ? true : undefined} />
          <p className={`mt-1 ${mutedClass}`}>{t('form.noteHint')}</p>
          {errors.note && <p role="alert" className={`mt-1 ${errorClass}`}>{errorText(errors.note)}</p>}
        </div>

        <div aria-hidden="true" className="absolute -left-[10000px] h-0 w-0 overflow-hidden">
          <label>
            Fax
            <input type="text" name="fax" tabIndex={-1} autoComplete="off" value={fax} onChange={(e) => setFax(e.target.value)} />
          </label>
        </div>

        <div>
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" required checked={consent} onChange={(e) => setConsent(e.target.checked)} aria-invalid={errors.consent ? true : undefined} className="mt-1" />
            <span>
              {t('form.consent')}
              {info.privacy_url && (
                <>
                  {' '}
                  {info.privacy_url.startsWith('/') ? (
                    <Link to={info.privacy_url} className="underline">{t('form.consentLink')}</Link>
                  ) : (
                    <a href={info.privacy_url} className="underline" target="_blank" rel="noreferrer">{t('form.consentLink')}</a>
                  )}
                </>
              )}
            </span>
          </label>
          {errors.consent && <p role="alert" className={`mt-1 ${errorClass}`}>{errors.consent === 'required' ? t('errors.consentRequired') : errorText(errors.consent)}</p>}
        </div>
      </div>

      {general && <p role="alert" className={errorClass}>{general}</p>}
      {errors._form && <p role="alert" className={errorClass}>{errorText(errors._form)}</p>}
      <button type="submit" disabled={submitting || !start} className={primaryButtonClass}>
        {submitting ? t('form.submitting') : t('form.submit')}
      </button>
    </form>
  )
}
