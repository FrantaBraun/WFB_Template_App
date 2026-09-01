/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { apiFetch } from '../api/client'

interface CalendarArticle {
  id: string
  title: string
  slug: string
  event_date: string
}

/** Monday-first weekday abbreviations, localized via Intl rather than
 * hardcoded translation keys - a known Mon..Sun week (2024-01-01 was a
 * Monday) formatted with the active i18n language. */
function weekdayLabels(language: string): string[] {
  const formatter = new Intl.DateTimeFormat(language, { weekday: 'short' })
  return Array.from({ length: 7 }, (_, i) => formatter.format(new Date(2024, 0, 1 + i)))
}

function daysInMonth(year: number, month: number): number {
  return new Date(year, month, 0).getDate()
}

/** 0 = Monday .. 6 = Sunday, for a date's first-of-month weekday. */
function mondayFirstWeekday(year: number, month: number): number {
  return (new Date(year, month - 1, 1).getDay() + 6) % 7
}

/**
 * Browsable month calendar marking days with a published, in-window
 * article. Hovering or clicking a marked day opens a list of that day's
 * article links - both interactions set the same "open day" state, so
 * moving the mouse away closes it (standard hover-dropdown behavior) while
 * a tap on touch devices (no hover) keeps it open until another day is
 * tapped. Used both as the home page's desktop sidebar and, unchanged, as
 * the mobile full-screen overlay's content.
 */
export default function EventCalendar() {
  const { t, i18n } = useTranslation()
  const today = new Date()
  const [year, setYear] = useState(today.getFullYear())
  const [month, setMonth] = useState(today.getMonth() + 1)
  const [articlesByDay, setArticlesByDay] = useState<Map<number, CalendarArticle[]>>(new Map())
  const [openDay, setOpenDay] = useState<number | null>(null)

  useEffect(() => {
    setOpenDay(null)
    apiFetch(`/api/articles/calendar?year=${year}&month=${month}`)
      .then((r) => (r.ok ? r.json() : []))
      .then((articles: CalendarArticle[]) => {
        const grouped = new Map<number, CalendarArticle[]>()
        for (const article of articles) {
          const day = Number(article.event_date.slice(8, 10))
          grouped.set(day, [...(grouped.get(day) ?? []), article])
        }
        setArticlesByDay(grouped)
      })
      .catch(() => setArticlesByDay(new Map()))
  }, [year, month])

  const labels = useMemo(() => weekdayLabels(i18n.language), [i18n.language])
  const monthLabel = useMemo(
    () => new Intl.DateTimeFormat(i18n.language, { month: 'long', year: 'numeric' }).format(new Date(year, month - 1, 1)),
    [year, month, i18n.language],
  )
  const leadingBlanks = mondayFirstWeekday(year, month)
  const totalDays = daysInMonth(year, month)

  function goToPreviousMonth() {
    if (month === 1) { setYear(year - 1); setMonth(12) } else { setMonth(month - 1) }
  }

  function goToNextMonth() {
    if (month === 12) { setYear(year + 1); setMonth(1) } else { setMonth(month + 1) }
  }

  return (
    <div className="rounded-2xl border-2 border-ink bg-white p-4 dark:border-ink-dark/30 dark:bg-card-dark">
      <h2 className="mb-3 hidden font-display text-lg font-semibold tracking-tight text-ink dark:text-ink-dark md:block">{t('calendar.title')}</h2>
      <div className="mb-3 flex items-center justify-between">
        <button type="button" onClick={goToPreviousMonth} className="rounded px-2 py-1 text-sm text-ink-muted hover:bg-ink/10 dark:text-ink-muted-dark dark:hover:bg-ink-dark/10">
          ‹
        </button>
        <span className="text-sm font-semibold capitalize text-ink dark:text-ink-dark">{monthLabel}</span>
        <button type="button" onClick={goToNextMonth} className="rounded px-2 py-1 text-sm text-ink-muted hover:bg-ink/10 dark:text-ink-muted-dark dark:hover:bg-ink-dark/10">
          ›
        </button>
      </div>

      <div className="grid grid-cols-7 gap-1 text-center text-xs text-ink-muted dark:text-ink-muted-dark">
        {labels.map((label) => (
          <div key={label} className="py-1 capitalize">{label}</div>
        ))}

        {Array.from({ length: leadingBlanks }, (_, i) => (
          <div key={`blank-${i}`} />
        ))}

        {Array.from({ length: totalDays }, (_, i) => i + 1).map((day) => {
          const dayArticles = articlesByDay.get(day) ?? []
          const hasArticles = dayArticles.length > 0
          const isOpen = openDay === day

          return (
            <div
              key={day}
              className="relative"
              onMouseEnter={hasArticles ? () => setOpenDay(day) : undefined}
              onMouseLeave={hasArticles ? () => setOpenDay(null) : undefined}
            >
              <button
                type="button"
                onClick={hasArticles ? () => setOpenDay(isOpen ? null : day) : undefined}
                className={`aspect-square w-full rounded-lg text-sm ${
                  hasArticles
                    ? 'cursor-pointer bg-mustard/30 font-semibold text-ink hover:bg-mustard/45 dark:bg-mustard-dark/20 dark:text-ink-dark dark:hover:bg-mustard-dark/30'
                    : 'text-ink-soft dark:text-ink-soft-dark'
                }`}
              >
                <span className={year === today.getFullYear() && month === today.getMonth() + 1 && day === today.getDate() ? 'underline font-bold' : ''}>
                  {day}
                </span>
              </button>

              {isOpen && hasArticles && (
                <div className="absolute left-1/2 top-full z-10 w-48 -translate-x-1/2 rounded-lg border-2 border-ink bg-white p-1 text-left shadow-lg dark:border-ink-dark/30 dark:bg-card-dark">
                  {dayArticles.map((article) => (
                    <Link
                      key={article.id}
                      to={`/clanek/${article.slug}`}
                      className="block truncate rounded px-2 py-1.5 text-xs text-ink hover:bg-ink/10 dark:text-ink-dark dark:hover:bg-ink-dark/10"
                    >
                      {article.title}
                    </Link>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {articlesByDay.size === 0 && (
        <p className="mt-3 text-center text-xs text-ink-muted dark:text-ink-muted-dark">{t('calendar.noEvents')}</p>
      )}
      <div className='flex justify-center'>
        <button className="mt-3 rounded-lg bg-teal px-4 py-2 text-sm font-semibold text-white hover:bg-teal-dark dark:hover:bg-teal/80" onClick={() => {
          const today = new Date()
          setYear(today.getFullYear())
          setMonth(today.getMonth() + 1)
        }}>
          {t('calendar.today')}
        </button>
      </div>
    </div>
  )
}
