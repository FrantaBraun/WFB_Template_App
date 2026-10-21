/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  API_BASE,
  fetchJson,
  formatDay,
  formatTime,
  isoDay,
  isoMonth,
  query,
  type CancelResult,
  type DayInfo,
  type ExceptionDay,
  type ReservationAdmin,
} from './api'
import { ExceptionForm, ReservationCard, Section } from './admin'
import MonthGrid from './MonthGrid'
import { cardClass, errorClass, mutedClass, okClass, secondaryButtonClass, ManageShell } from './ui'

/**
 * /reservations/manage - the calendar of reservations for the pub's administrators:
 * a month with the number of confirmed reservations of each day (closed days are
 * marked), and for the chosen day its hours, a way to close it or change its hours,
 * and every reservation with the means to cancel it with a message to the guest.
 */
export default function CalendarPage() {
  const { t } = useTranslation('table_reservations')
  return (
    <ManageShell title={t('manage.title')}>
      <Calendar />
    </ManageShell>
  )
}

function Calendar() {
  const { t, i18n } = useTranslation('table_reservations')
  const language = i18n.resolvedLanguage ?? i18n.language
  const todayIso = useMemo(() => isoDay(new Date()), [])
  const [view, setView] = useState(() => ({ year: Number(todayIso.slice(0, 4)), month: Number(todayIso.slice(5, 7)) - 1 }))
  const [selected, setSelected] = useState(todayIso)
  const [days, setDays] = useState<Record<string, DayInfo>>({})
  const [exceptions, setExceptions] = useState<Record<string, ExceptionDay>>({})
  const [reservations, setReservations] = useState<ReservationAdmin[]>([])
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    const first = isoDay(new Date(view.year, view.month, 1))
    const last = isoDay(new Date(view.year, view.month + 1, 0))
    Promise.all([
      fetchJson<{ days: DayInfo[] }>(`${API_BASE}/days${query({ month: isoMonth(view.year, view.month) })}`),
      fetchJson<ExceptionDay[]>(`${API_BASE}/manage/exceptions${query({ date_from: first })}`),
      fetchJson<ReservationAdmin[]>(`${API_BASE}/manage/reservations${query({ date_from: first, date_to: last })}`),
    ])
      .then(([dayList, exceptionList, reservationList]) => {
        if (cancelled) return
        setDays(Object.fromEntries(dayList.days.map((entry) => [entry.day, entry])))
        setExceptions(Object.fromEntries(exceptionList.map((entry) => [entry.day, entry])))
        setReservations(reservationList)
        setState('ready')
      })
      .catch(() => !cancelled && setState('error'))
    return () => {
      cancelled = true
    }
  }, [view.year, view.month, reloadKey])

  const confirmedPerDay = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const reservation of reservations) {
      if (reservation.status === 'confirmed') counts[reservation.day] = (counts[reservation.day] ?? 0) + 1
    }
    return counts
  }, [reservations])

  function moveMonth(delta: number) {
    const next = new Date(view.year, view.month + delta, 1)
    setView({ year: next.getFullYear(), month: next.getMonth() })
    setSelected(isoDay(next))
  }

  function goToToday() {
    setView({ year: Number(todayIso.slice(0, 4)), month: Number(todayIso.slice(5, 7)) - 1 })
    setSelected(todayIso)
  }

  function replaceReservation(result: CancelResult) {
    setReservations((previous) => previous.map((entry) => (entry.id === result.reservation.id ? result.reservation : entry)))
  }

  if (state === 'error') return <p role="alert" className={errorClass}>{t('manage.loadError')}</p>

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)]">
      <div className="space-y-3">
        <div className={cardClass}>
          <MonthGrid
            year={view.year}
            month={view.month}
            selected={selected}
            onSelect={setSelected}
            describe={(iso) => {
              const info = days[iso]
              const count = confirmedPerDay[iso] ?? 0
              return [info && !info.is_open ? t('hours.closed') : '', count ? t('calendar.count', { count }) : ''].filter(Boolean).join(', ')
            }}
            renderBadge={(iso) => {
              const info = days[iso]
              const count = confirmedPerDay[iso] ?? 0
              if (info && !info.is_open) return <span className="text-slate-500 dark:text-slate-400">{t('calendar.closedShort')}</span>
              return count > 0 ? <span className="rounded-full bg-emerald-100 px-1.5 font-medium text-emerald-900 dark:bg-emerald-900 dark:text-emerald-100">{count}</span> : null
            }}
            dayClass={(iso) => (iso === todayIso && selected !== iso ? 'ring-1 ring-slate-400 dark:ring-slate-500' : '')}
            onPrevious={() => moveMonth(-1)}
            onNext={() => moveMonth(1)}
            canPrevious
            canNext
            roomy
          />
        </div>
        <button type="button" onClick={goToToday} className={secondaryButtonClass}>
          {t('calendar.today')}
        </button>
        <p className={mutedClass}>{t('calendar.legend')}</p>
        {state === 'loading' && <p className={mutedClass}>{t('common.loading')}</p>}
      </div>

      <DayPanel
        day={selected}
        today={todayIso}
        language={language}
        info={days[selected]}
        exception={exceptions[selected] ?? null}
        reservations={reservations.filter((entry) => entry.day === selected)}
        onCancelled={replaceReservation}
        onHoursChanged={() => setReloadKey((key) => key + 1)}
      />
    </div>
  )
}

interface DayPanelProps {
  day: string
  today: string
  language: string
  info: DayInfo | undefined
  exception: ExceptionDay | null
  reservations: ReservationAdmin[]
  onCancelled: (result: CancelResult) => void
  onHoursChanged: () => void
}

function DayPanel({ day, today, language, info, exception, reservations, onCancelled, onHoursChanged }: DayPanelProps) {
  const { t } = useTranslation('table_reservations')
  const [editing, setEditing] = useState(false)
  const [showCancelled, setShowCancelled] = useState(false)
  const confirmed = reservations.filter((entry) => entry.status === 'confirmed')
  const cancelled = reservations.filter((entry) => entry.status === 'cancelled')
  const shown = showCancelled ? reservations : confirmed
  const editable = day >= today

  return (
    <div className="space-y-4">
      <Section title={formatDay(day, language)}>
        <div className="space-y-1 text-sm">
          {info ? (
            info.is_open && info.opens && info.closes ? (
              <p>
                {t('panel.open', { opens: formatTime(info.opens), closes: formatTime(info.closes) })}
                {exception && <span className={mutedClass}> ({t('panel.changed')})</span>}
              </p>
            ) : (
              <p className="font-medium">{t('panel.closed')}</p>
            )
          ) : null}
          {exception?.reason && <p className={mutedClass}>{t('panel.reason')}: {exception.reason}</p>}
        </div>
        {editable &&
          (editing ? (
            <ExceptionForm
              key={day}
              day={day}
              existing={exception}
              onSaved={() => {
                onHoursChanged()
                setEditing(false)
              }}
              onChanged={onHoursChanged}
              onClose={() => {
                setEditing(false)
                onHoursChanged()
              }}
            />
          ) : (
            <button type="button" onClick={() => setEditing(true)} className={secondaryButtonClass}>
              {info && !info.is_open ? t('panel.editClosed') : t('panel.closeOrChange')}
            </button>
          ))}
      </Section>

      <Section title={t('panel.reservations', { count: confirmed.length })}>
        {shown.length === 0 ? (
          <p className={mutedClass}>{t('panel.none')}</p>
        ) : (
          <ul className="space-y-2">
            {shown.map((entry) => (
              <ReservationCard key={entry.id} reservation={entry} onCancelled={onCancelled} />
            ))}
          </ul>
        )}
        {cancelled.length > 0 && (
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={showCancelled} onChange={(e) => setShowCancelled(e.target.checked)} />
            {t('panel.showCancelled', { count: cancelled.length })}
          </label>
        )}
        {confirmed.length === 0 && cancelled.length > 0 && !showCancelled && <p className={okClass}>{t('panel.allCancelled')}</p>}
      </Section>
    </div>
  )
}
