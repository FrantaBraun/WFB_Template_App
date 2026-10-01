/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'
import usePageMeta from '../../hooks/usePageMeta'
import {
  API_BASE,
  EVENTS_PATH,
  eventPath,
  fetchJson,
  formatEventDate,
  monthName,
  useIsEditor,
  type ArchiveYear,
  type EventTeaser,
} from './api'
import EventCalendar from './EventCalendar'

/** One listing row: thumbnail, date, title, short description - the whole card links to the event page. */
export function EventCard({ event }: { event: EventTeaser }) {
  const { t, i18n } = useTranslation('event_calendar')
  return (
    <Link
      to={eventPath(event.slug)}
      className="flex gap-4 rounded-2xl border border-slate-200 bg-white p-4 transition hover:border-slate-300 hover:shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:hover:border-slate-700"
    >
      <div className="h-24 w-24 shrink-0 overflow-hidden rounded-xl bg-slate-100 sm:h-28 sm:w-36 dark:bg-slate-800">
        {event.image_url ? (
          <img src={event.image_url} alt="" loading="lazy" className="h-full w-full object-cover" />
        ) : (
          <div aria-hidden="true" className="flex h-full w-full items-center justify-center text-3xl text-slate-300 dark:text-slate-600">
            📅
          </div>
        )}
      </div>
      <div className="min-w-0 space-y-1">
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {formatEventDate(event.event_date, i18n.language)}
          {event.pinned && (
            <span className="ml-2 rounded-full bg-violet-100 px-2 py-0.5 text-xs font-medium text-violet-800 dark:bg-violet-900/60 dark:text-violet-200">
              {t('list.pinned')}
            </span>
          )}
        </p>
        <h2 className="text-lg font-semibold leading-snug">{event.title}</h2>
        {event.short_description && (
          <p className="line-clamp-3 text-sm text-slate-600 dark:text-slate-300">{event.short_description}</p>
        )}
      </div>
    </Link>
  )
}

/** Sidebar tree: each year expands to its months that have events; a month links to its full listing. */
function ArchiveTree({ selected }: { selected: { year: number; month: number } | null }) {
  const { t, i18n } = useTranslation('event_calendar')
  const [archive, setArchive] = useState<ArchiveYear[] | null>(null)
  const [openYears, setOpenYears] = useState<Set<number>>(new Set())

  useEffect(() => {
    fetchJson<ArchiveYear[]>(`${API_BASE}/archive`)
      .then(setArchive)
      .catch(() => setArchive([]))
  }, [])

  // Keep the year of the shown month (or the current year) expanded.
  useEffect(() => {
    const year = selected?.year ?? new Date().getFullYear()
    setOpenYears((current) => (current.has(year) ? current : new Set(current).add(year)))
  }, [selected?.year])

  function toggle(year: number) {
    setOpenYears((current) => {
      const next = new Set(current)
      if (next.has(year)) next.delete(year)
      else next.add(year)
      return next
    })
  }

  return (
    <nav aria-label={t('archive.title')} className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <h2 className="mb-2 text-lg font-semibold tracking-tight">{t('archive.title')}</h2>
      {archive === null ? (
        <p className="text-sm text-slate-500 dark:text-slate-400">{t('common.loading')}</p>
      ) : archive.length === 0 ? (
        <p className="text-sm text-slate-500 dark:text-slate-400">{t('archive.empty')}</p>
      ) : (
        <ul className="space-y-1 text-sm">
          {archive.map(({ year, months }) => {
            const open = openYears.has(year)
            return (
              <li key={year}>
                <button
                  type="button"
                  onClick={() => toggle(year)}
                  aria-expanded={open}
                  className="flex w-full items-center gap-2 rounded px-1 py-1 text-left font-medium hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  <span aria-hidden="true" className={`inline-block text-xs transition-transform ${open ? 'rotate-90' : ''}`}>▶</span>
                  {year}
                </button>
                {open && (
                  <ul className="ml-5 mt-1 space-y-0.5">
                    {months.map(({ month, count }) => {
                      const active = selected?.year === year && selected.month === month
                      return (
                        <li key={month}>
                          <Link
                            to={`${EVENTS_PATH}?year=${year}&month=${month}`}
                            aria-current={active ? 'page' : undefined}
                            className={`flex justify-between rounded px-2 py-0.5 capitalize ${
                              active
                                ? 'bg-slate-900 text-slate-100 dark:bg-slate-100 dark:text-slate-900'
                                : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
                            }`}
                          >
                            <span>{monthName(year, month, i18n.language)}</span>
                            <span className="opacity-60">{count}</span>
                          </Link>
                        </li>
                      )
                    })}
                  </ul>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </nav>
  )
}

function parseMonthParams(params: URLSearchParams): { year: number; month: number } | null {
  const year = Number(params.get('year'))
  const month = Number(params.get('month'))
  if (!Number.isInteger(year) || !Number.isInteger(month) || year < 1 || month < 1 || month > 12) return null
  return { year, month }
}

/**
 * /events - the next upcoming events (with "Load more"), or with
 * ?year=&month= every visible event of that month. Sidebar: the calendar
 * and the year/month archive tree.
 */
export default function EventsPage() {
  const { t, i18n } = useTranslation('event_calendar')
  const [params] = useSearchParams()
  const selected = parseMonthParams(params)
  const isEditor = useIsEditor()

  const [items, setItems] = useState<EventTeaser[] | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState(false)

  const heading = selected
    ? t('list.monthTitle', { month: monthName(selected.year, selected.month, i18n.language), year: selected.year })
    : t('list.title')
  usePageMeta({ title: heading })

  const selectedKey = selected ? `${selected.year}-${selected.month}` : 'upcoming'
  useEffect(() => {
    let cancelled = false
    setItems(null)
    setError(false)
    const request = selected
      ? fetchJson<EventTeaser[]>(`${API_BASE}/month?year=${selected.year}&month=${selected.month}`).then((list) => ({ items: list, has_more: false }))
      : fetchJson<{ items: EventTeaser[]; has_more: boolean }>(API_BASE)
    request
      .then((page) => {
        if (cancelled) return
        setItems(page.items)
        setHasMore(page.has_more)
      })
      .catch(() => !cancelled && setError(true))
    return () => {
      cancelled = true
    }
    // selectedKey captures `selected` by value.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedKey])

  async function loadMore() {
    if (!items) return
    setLoadingMore(true)
    try {
      const page = await fetchJson<{ items: EventTeaser[]; has_more: boolean }>(`${API_BASE}?offset=${items.length}`)
      setItems([...items, ...page.items])
      setHasMore(page.has_more)
    } catch {
      setError(true)
    } finally {
      setLoadingMore(false)
    }
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-12 text-slate-900 dark:text-slate-100">
      <div className="grid gap-8 lg:grid-cols-[1fr_20rem]">
        <section className="min-w-0">
          <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
            <h1 className="text-3xl font-semibold tracking-tight first-letter:uppercase">{heading}</h1>
            <div className="flex gap-2 text-sm">
              {selected && (
                <Link to={EVENTS_PATH} className="rounded-lg border border-slate-200 px-3 py-1.5 hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800">
                  {t('list.backToUpcoming')}
                </Link>
              )}
              {isEditor && (
                <Link to={`${EVENTS_PATH}/manage`} className="rounded-lg bg-slate-900 px-3 py-1.5 font-medium text-slate-100 dark:bg-slate-100 dark:text-slate-900">
                  {t('list.manage')}
                </Link>
              )}
            </div>
          </div>

          {error && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{t('list.error')}</p>}
          {items === null && !error ? (
            <p className="text-slate-500 dark:text-slate-400">{t('common.loading')}</p>
          ) : items && items.length === 0 ? (
            <p className="rounded-2xl border border-dashed border-slate-300 p-8 text-center text-slate-500 dark:border-slate-700 dark:text-slate-400">
              {selected ? t('list.emptyMonth') : t('list.emptyUpcoming')}
            </p>
          ) : (
            <div className="space-y-4">
              {items?.map((event) => <EventCard key={event.id} event={event} />)}
            </div>
          )}

          {!selected && hasMore && (
            <div className="mt-6 flex justify-center">
              <button
                type="button"
                onClick={loadMore}
                disabled={loadingMore}
                className="rounded-lg border border-slate-300 px-5 py-2 font-medium hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:hover:bg-slate-800"
              >
                {loadingMore ? t('common.loading') : t('list.loadMore')}
              </button>
            </div>
          )}
        </section>

        <aside className="space-y-6">
          <EventCalendar />
          <ArchiveTree selected={selected} />
        </aside>
      </div>
    </div>
  )
}
