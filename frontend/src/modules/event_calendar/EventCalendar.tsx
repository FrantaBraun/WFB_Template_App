/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import '../articles/articles.css'
import { API_BASE, eventPath, fetchJson, parseEventDate, typeStyle, type EventTeaser } from './api'

/** Monday-first weekday abbreviations via Intl (2024-01-01 was a Monday). */
function weekdayLabels(language: string): string[] {
  const formatter = new Intl.DateTimeFormat(language, { weekday: 'short' })
  return Array.from({ length: 7 }, (_, i) => formatter.format(new Date(2024, 0, 1 + i)))
}

/** 0 = Monday .. 6 = Sunday, for the month's first day. */
function mondayFirstWeekday(year: number, month: number): number {
  return (new Date(year, month - 1, 1).getDay() + 6) % 7
}

/** Events by day of the month; one that runs over several days is on every one of them (clipped to the month). */
function groupByDay(events: EventTeaser[], year: number, month: number): Map<number, EventTeaser[]> {
  const lastDayOfMonth = new Date(year, month, 0).getDate()
  const grouped = new Map<number, EventTeaser[]>()
  for (const event of events) {
    const start = parseEventDate(event.start_date)
    const end = parseEventDate(event.end_date ?? event.start_date)
    const first = start.getFullYear() === year && start.getMonth() + 1 === month ? start.getDate() : 1
    const last = end.getFullYear() === year && end.getMonth() + 1 === month ? end.getDate() : lastDayOfMonth
    for (let day = first; day <= last; day++) grouped.set(day, [...(grouped.get(day) ?? []), event])
  }
  return grouped
}

/**
 * Where a day's popup sits relative to its cell, by weekday column (0 = Monday): centred in the
 * middle of the week, but growing rightwards from the first two columns and leftwards from the
 * last two, so it never runs off the edge of a narrow screen.
 */
function popupPosition(column: number): string {
  if (column <= 1) return 'left-0'
  if (column >= 5) return 'right-0'
  return 'left-1/2 -translate-x-1/2'
}

const NEUTRAL_DAY ='bg-sky-100 font-semibold text-sky-950 hover:bg-sky-200 dark:bg-sky-900/50 dark:text-sky-100 dark:hover:bg-sky-800/60'

/**
 * Browsable month calendar marking the days that have an event, in the colours of the type of the
 * event's article (neutral blue when it has none); a day with a pinned article carries a 📌.
 * Hovering or clicking a marked day opens that day's events - each a link to its article - and
 * pointing at (or tabbing to) one of them shows its short description, the one of up to 128
 * characters. Hover and click set the same "open day" state, so leaving with the mouse closes it
 * while a tap on a touch device keeps it open until another day is tapped. Exported for
 * applications that want it elsewhere too (e.g. a home page sidebar).
 */
export default function EventCalendar() {
  const { t, i18n } = useTranslation('event_calendar')
  const today = new Date()
  const [year, setYear] = useState(today.getFullYear())
  const [month, setMonth] = useState(today.getMonth() + 1)
  const [events, setEvents] = useState<EventTeaser[]>([])
  const [openDay, setOpenDay] = useState<number | null>(null)
  const [described, setDescribed] = useState<EventTeaser | null>(null)

  useEffect(() => {
    let cancelled = false
    setOpenDay(null)
    fetchJson<EventTeaser[]>(`${API_BASE}/month?year=${year}&month=${month}`)
      .then((found) => !cancelled && setEvents(found))
      .catch(() => !cancelled && setEvents([]))
    return () => {
      cancelled = true
    }
  }, [year, month])

  const eventsByDay = useMemo(() => groupByDay(events, year, month), [events, year, month])
  const typesInMonth = useMemo(() => {
    const byId = new Map<string, NonNullable<EventTeaser['article']['type']>>()
    for (const event of events) if (event.article.type) byId.set(event.article.type.id, event.article.type)
    return [...byId.values()]
  }, [events])
  const anyPinned = events.some((event) => event.article.pinned)

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
          const hasPinned = dayEvents.some((event) => event.article.pinned)
          const dayType = dayEvents.find((event) => event.article.type)?.article.type ?? null
          const isOpen = openDay === day
          const isToday = isCurrentMonth && day === today.getDate()

          const tone = hasEvents
            ? dayType
              ? 'article-typed border-2 font-semibold text-slate-900 dark:text-slate-100'
              : NEUTRAL_DAY
            : 'text-slate-600 dark:text-slate-300'

          return (
            <div
              key={day}
              className="relative"
              onMouseEnter={hasEvents ? () => setOpenDay(day) : undefined}
              onMouseLeave={hasEvents ? () => { setOpenDay(null); setDescribed(null) } : undefined}
            >
              <button
                type="button"
                onClick={hasEvents ? () => setOpenDay(isOpen ? null : day) : undefined}
                aria-label={hasEvents ? t('calendar.dayWithEvents', { day, count: dayEvents.length }) : undefined}
                aria-expanded={hasEvents ? isOpen : undefined}
                style={dayType ? typeStyle(dayType) : undefined}
                className={`aspect-square w-full rounded-lg text-sm ${hasEvents ? 'cursor-pointer' : 'cursor-default'} ${tone}`}
              >
                <span className={isToday ? 'font-bold underline' : ''}>{day}</span>
                {hasPinned && <span aria-hidden="true" className="absolute right-0.5 top-0 text-[10px] leading-none">📌</span>}
              </button>

              {isOpen && hasEvents && (
                <div className={`absolute top-full z-10 w-60 max-w-[calc(100vw-2rem)] rounded-lg border border-slate-200 bg-white p-1 text-left shadow-lg dark:border-slate-700 dark:bg-slate-800 ${popupPosition((leadingBlanks + day - 1) % 7)}`}>
                  {dayEvents.map((event) => (
                    <Link
                      key={event.id}
                      to={eventPath(event)}
                      style={typeStyle(event.article.type)}
                      aria-describedby={described?.id === event.id ? `event-description-${day}` : undefined}
                      onMouseEnter={() => setDescribed(event)}
                      onFocus={() => setDescribed(event)}
                      onBlur={() => setDescribed(null)}
                      className={`block truncate rounded border-l-4 px-2 py-1.5 text-xs text-slate-800 hover:bg-slate-100 dark:text-slate-100 dark:hover:bg-slate-700 ${
                        event.article.type ? 'article-typed' : 'border-slate-300 dark:border-slate-600'
                      }`}
                    >
                      {event.article.pinned && <span aria-hidden="true">📌 </span>}
                      {event.title}
                    </Link>
                  ))}
                  {described && described.short_description && dayEvents.some((event) => event.id === described.id) && (
                    <p id={`event-description-${day}`} role="tooltip" className="mt-1 rounded bg-slate-100 px-2 py-1.5 text-xs text-slate-700 dark:bg-slate-900 dark:text-slate-200">
                      {described.short_description}
                    </p>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-xs text-slate-500 dark:text-slate-400">
        {typesInMonth.length === 0 && events.length > 0 && (
          <span className="inline-flex items-center gap-1.5"><span className="h-3 w-3 rounded bg-sky-100 dark:bg-sky-900/50" />{t('calendar.legendEvent')}</span>
        )}
        {typesInMonth.map((type) => (
          <span key={type.id} style={typeStyle(type)} className="inline-flex items-center gap-1.5">
            <span className="article-typed h-3 w-3 rounded border-2" />
            {type.name}
          </span>
        ))}
        {anyPinned && <span className="inline-flex items-center gap-1.5"><span aria-hidden="true">📌</span>{t('calendar.legendPinned')}</span>}
      </div>
      {events.length === 0 && (
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
