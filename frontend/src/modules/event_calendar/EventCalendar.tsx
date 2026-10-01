/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { API_BASE, eventPath, fetchJson, type EventTeaser } from './api'

/** Monday-first weekday abbreviations via Intl (2024-01-01 was a Monday). */
function weekdayLabels(language: string): string[] {
  const formatter = new Intl.DateTimeFormat(language, { weekday: 'short' })
  return Array.from({ length: 7 }, (_, i) => formatter.format(new Date(2024, 0, 1 + i)))
}

/** 0 = Monday .. 6 = Sunday, for the month's first day. */
function mondayFirstWeekday(year: number, month: number): number {
  return (new Date(year, month - 1, 1).getDay() + 6) % 7
}

/**
 * Browsable month calendar marking days that have a visible event - days
 * with a pinned one stand out in a second color. Hovering or clicking a
 * marked day opens that day's event links; both set the same "open day"
 * state, so leaving with the mouse closes it while a tap on touch devices
 * keeps it open until another day is tapped. Exported for applications
 * that want it elsewhere too (e.g. a home page sidebar).
 */
export default function EventCalendar() {
  const { t, i18n } = useTranslation('event_calendar')
  const today = new Date()
  const [year, setYear] = useState(today.getFullYear())
  const [month, setMonth] = useState(today.getMonth() + 1)
  const [eventsByDay, setEventsByDay] = useState<Map<number, EventTeaser[]>>(new Map())
  const [openDay, setOpenDay] = useState<number | null>(null)

  useEffect(() => {
    let cancelled = false
    setOpenDay(null)
    fetchJson<EventTeaser[]>(`${API_BASE}/month?year=${year}&month=${month}`)
      .then((events) => {
        if (cancelled) return
        const grouped = new Map<number, EventTeaser[]>()
        for (const event of events) {
          const day = Number(event.event_date.slice(8, 10))
          grouped.set(day, [...(grouped.get(day) ?? []), event])
        }
        setEventsByDay(grouped)
      })
      .catch(() => !cancelled && setEventsByDay(new Map()))
    return () => {
      cancelled = true
    }
  }, [year, month])

  const labels = useMemo(() => weekdayLabels(i18n.language), [i18n.language])
  const monthLabel = useMemo(
    () => new Intl.DateTimeFormat(i18n.language, { month: 'long', year: 'numeric' }).format(new Date(year, month - 1, 1)),
    [year, month, i18n.language],
  )
  const leadingBlanks = mondayFirstWeekday(year, month)
  const totalDays = new Date(year, month, 0).getDate()
  const isCurrentMonth = year === today.getFullYear() && month === today.getMonth() + 1

  function shiftMonth(delta: number) {
    const shifted = new Date(year, month - 1 + delta, 1)
    setYear(shifted.getFullYear())
    setMonth(shifted.getMonth() + 1)
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <h2 className="mb-3 text-lg font-semibold tracking-tight">{t('calendar.title')}</h2>
      <div className="mb-3 flex items-center justify-between">
        <button type="button" onClick={() => shiftMonth(-1)} aria-label={t('calendar.previous')} className="rounded px-2 py-1 text-sm text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800">
          ‹
        </button>
        <span className="text-sm font-semibold capitalize">{monthLabel}</span>
        <button type="button" onClick={() => shiftMonth(1)} aria-label={t('calendar.next')} className="rounded px-2 py-1 text-sm text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800">
          ›
        </button>
      </div>

      <div className="grid grid-cols-7 gap-1 text-center text-xs text-slate-500 dark:text-slate-400">
        {labels.map((label) => (
          <div key={label} className="py-1 capitalize">{label}</div>
        ))}
        {Array.from({ length: leadingBlanks }, (_, i) => (
          <div key={`blank-${i}`} />
        ))}
        {Array.from({ length: totalDays }, (_, i) => i + 1).map((day) => {
          const dayEvents = eventsByDay.get(day) ?? []
          const hasEvents = dayEvents.length > 0
          const hasPinned = dayEvents.some((event) => event.pinned)
          const isOpen = openDay === day
          const isToday = isCurrentMonth && day === today.getDate()

          const tone = hasPinned
            ? 'bg-violet-200 font-semibold text-violet-950 hover:bg-violet-300 dark:bg-violet-900/60 dark:text-violet-100 dark:hover:bg-violet-800/70'
            : hasEvents
              ? 'bg-sky-100 font-semibold text-sky-950 hover:bg-sky-200 dark:bg-sky-900/50 dark:text-sky-100 dark:hover:bg-sky-800/60'
              : 'text-slate-600 dark:text-slate-300'

          return (
            <div
              key={day}
              className="relative"
              onMouseEnter={hasEvents ? () => setOpenDay(day) : undefined}
              onMouseLeave={hasEvents ? () => setOpenDay(null) : undefined}
            >
              <button
                type="button"
                onClick={hasEvents ? () => setOpenDay(isOpen ? null : day) : undefined}
                aria-label={hasEvents ? t('calendar.dayWithEvents', { day, count: dayEvents.length }) : undefined}
                className={`aspect-square w-full rounded-lg text-sm ${hasEvents ? 'cursor-pointer' : 'cursor-default'} ${tone}`}
              >
                <span className={isToday ? 'font-bold underline' : ''}>{day}</span>
              </button>

              {isOpen && hasEvents && (
                <div className="absolute left-1/2 top-full z-10 w-52 -translate-x-1/2 rounded-lg border border-slate-200 bg-white p-1 text-left shadow-lg dark:border-slate-700 dark:bg-slate-800">
                  {dayEvents.map((event) => (
                    <Link
                      key={event.id}
                      to={eventPath(event.slug)}
                      className="block truncate rounded px-2 py-1.5 text-xs text-slate-800 hover:bg-slate-100 dark:text-slate-100 dark:hover:bg-slate-700"
                    >
                      {event.pinned && <span aria-hidden="true">📌 </span>}
                      {event.title}
                    </Link>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-xs text-slate-500 dark:text-slate-400">
        <span className="inline-flex items-center gap-1.5"><span className="h-3 w-3 rounded bg-sky-100 dark:bg-sky-900/50" />{t('calendar.legendEvent')}</span>
        <span className="inline-flex items-center gap-1.5"><span className="h-3 w-3 rounded bg-violet-200 dark:bg-violet-900/60" />{t('calendar.legendPinned')}</span>
      </div>
      {eventsByDay.size === 0 && (
        <p className="mt-2 text-center text-xs text-slate-500 dark:text-slate-400">{t('calendar.noEvents')}</p>
      )}
      {!isCurrentMonth && (
        <div className="mt-3 flex justify-center">
          <button
            type="button"
            onClick={() => {
              setYear(today.getFullYear())
              setMonth(today.getMonth() + 1)
            }}
            className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
          >
            {t('calendar.today')}
          </button>
        </div>
      )}
    </div>
  )
}
