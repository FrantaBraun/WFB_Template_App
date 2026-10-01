/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { apiFetch } from '../api/client'
import { EventCalendar } from '../modules/event_calendar'
import { API_BASE as EVENTS_API, eventPath, parseEventDate, type EventTeaser as ArticleTeaser } from '../modules/event_calendar/api'

interface Dashboard {
  upcoming: ArticleTeaser | null
  pinned: ArticleTeaser[]
  recent_past: ArticleTeaser[]
}

/** Same open-book mark as Layout.tsx's nav badge, at hero size - see that file's BookIcon for why this is duplicated rather than shared. */
function BookIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      <path d="M12 5.5c-1.8-1.4-4.2-2-6.5-1.7v13c2.3-0.3 4.7 0.3 6.5 1.7 1.8-1.4 4.2-2 6.5-1.7v-13c-2.3-0.3-4.7 0.3-6.5 1.7z" />
      <path d="M12 5.5v13" />
    </svg>
  )
}

/** The single nearest-upcoming article - a bigger, date-badge led card, distinct from the grid teasers below it. */
function UpcomingCard({ article }: { article: ArticleTeaser }) {
  const date = parseEventDate(article.event_date)
  return (
    <Link
      to={eventPath(article.slug)}
      className="flex items-start gap-4 rounded-2xl border-2 border-ink bg-white p-5 transition-transform hover:-translate-y-0.5 dark:border-ink-dark/30 dark:bg-card-dark"
    >
      <div className="flex h-14 w-14 shrink-0 flex-col items-center justify-center rounded-xl bg-mustard/25 font-display text-ink dark:bg-mustard-dark/20 dark:text-ink-dark">
        <span className="text-xl font-bold leading-none">{date.getDate()}</span>
        <span className="text-[10px] font-semibold uppercase">{date.toLocaleDateString(undefined, { month: 'short' })}</span>
      </div>
      <div>
        <h3 className="font-display font-semibold text-ink dark:text-ink-dark">{article.title}</h3>
        <p className="mt-1 text-sm text-ink-soft dark:text-ink-soft-dark">{article.short_description}</p>
      </div>
    </Link>
  )
}

/**
 * Grid teaser used for pinned articles, recent-past articles and search
 * results - three visually distinct treatments sharing one layout: pinned
 * gets a small rotated corner accent (alternating teal/coral by position),
 * past is a muted dashed card (nothing to feature), default (search) is a
 * plain solid card.
 */
function TeaserCard({
  article,
  variant = 'default',
  accentIndex = 0,
}: {
  article: ArticleTeaser
  variant?: 'default' | 'pinned' | 'past'
  accentIndex?: number
}) {
  if (variant === 'past') {
    return (
      <Link
        to={eventPath(article.slug)}
        className="block rounded-2xl border border-dashed border-ink/25 p-4 hover:border-ink/45 dark:border-ink-dark/25 dark:hover:border-ink-dark/45"
      >
        <p className="text-xs text-ink-muted dark:text-ink-muted-dark">{parseEventDate(article.event_date).toLocaleDateString()}</p>
        <h4 className="mt-1 font-display text-sm font-semibold text-ink-soft dark:text-ink-soft-dark">{article.title}</h4>
      </Link>
    )
  }

  return (
    <Link
      to={eventPath(article.slug)}
      className="relative block rounded-2xl border-2 border-ink bg-white p-5 transition-transform hover:-translate-y-0.5 dark:border-ink-dark/30 dark:bg-card-dark"
    >
      {variant === 'pinned' && (
        <span
          aria-hidden="true"
          className={`absolute -top-2 right-5 h-4 w-4 rotate-45 ${accentIndex % 2 === 0 ? 'bg-teal' : 'bg-coral dark:bg-coral-dark'}`}
        />
      )}
      <p className="text-sm text-ink-muted dark:text-ink-muted-dark">{parseEventDate(article.event_date).toLocaleDateString()}</p>
      <h3 className="mt-1 font-display font-semibold text-ink dark:text-ink-dark">{article.title}</h3>
      <p className="mt-1 text-sm text-ink-soft dark:text-ink-soft-dark">{article.short_description}</p>
    </Link>
  )
}

/** Public landing page - fetches the event_calendar module's dashboard once and
 * renders its three groups (nearest upcoming, pinned, last 5 non-pinned
 * past), each teaser linking through to /events/:slug. */
export default function HomePage() {
  const { t } = useTranslation()
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [showMobileCalendar, setShowMobileCalendar] = useState(false)
  const [query, setQuery] = useState('')
  const [searchResults, setSearchResults] = useState<ArticleTeaser[] | null>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    apiFetch(`${EVENTS_API}/dashboard`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setDashboard)
      .catch(() => setDashboard({ upcoming: null, pinned: [], recent_past: [] }))
  }, [])

  // Debounced search - clearing the query restores the normal dashboard
  // view (searchResults null) rather than showing an empty results list.
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    const trimmed = query.trim()
    if (!trimmed) {
      setSearchResults(null)
      return
    }
    debounceRef.current = setTimeout(() => {
      apiFetch(`${EVENTS_API}/search?q=${encodeURIComponent(trimmed)}`)
        .then((r) => (r.ok ? r.json() : []))
        .then(setSearchResults)
        .catch(() => setSearchResults([]))
    }, 300)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [query])

  const isEmpty = dashboard && !dashboard.upcoming && dashboard.pinned.length === 0 && dashboard.recent_past.length === 0

  return (
    <div className="mx-auto max-w-6xl px-6 py-16">
      <div className="flex flex-col items-center gap-4 text-center">
        <div className="rounded-2xl border-[3px] border-ink bg-white p-4 shadow-[6px_6px_0_var(--color-ink)] dark:border-ink-dark/25 dark:bg-card-dark dark:shadow-lg dark:shadow-black/40">
          <BookIcon className="h-9 w-9 text-teal dark:text-teal-dark" />
        </div>
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{t('home.title')}</h1>
      </div>

      <div className="mx-auto mt-8 max-w-md">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t('home.searchPlaceholder')}
          className="w-full rounded-lg border-2 border-ink bg-white px-4 py-2 text-ink placeholder:text-ink-muted dark:border-ink-dark/30 dark:bg-card-dark dark:text-ink-dark dark:placeholder:text-ink-muted-dark"
        />
      </div>

      {/* Calendar sidebar lives on the home page only - a right-hand column
          at md: and up; below that it's hidden behind an expand button that
          opens the same EventCalendar full-screen instead of cramming it
          into a narrow single-column layout. */}
      <div className="mt-10 flex flex-col gap-10 md:flex-row md:items-start">
        <div className="flex flex-1 flex-col gap-10">
          {searchResults !== null ? (
            <section>
              <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-ink-muted dark:text-ink-muted-dark">
                {t('home.searchResults')}
              </h2>
              {searchResults.length === 0 ? (
                <p className="text-ink-soft dark:text-ink-soft-dark">{t('home.searchNoResults')}</p>
              ) : (
                <div className="grid gap-4 sm:grid-cols-2">
                  {searchResults.map((article) => (
                    <TeaserCard key={article.id} article={article} />
                  ))}
                </div>
              )}
            </section>
          ) : (
            <>
              {dashboard?.upcoming && (
                <section>
                  <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-ink-muted dark:text-ink-muted-dark">
                    {t('home.upcoming')}
                  </h2>
                  <UpcomingCard article={dashboard.upcoming} />
                </section>
              )}

              {dashboard && dashboard.pinned.length > 0 && (
                <section>
                  <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-ink-muted dark:text-ink-muted-dark">
                    {t('home.pinned')}
                  </h2>
                  <div className="grid gap-4 sm:grid-cols-2">
                    {dashboard.pinned.map((article, index) => (
                      <TeaserCard key={article.id} article={article} variant="pinned" accentIndex={index} />
                    ))}
                  </div>
                </section>
              )}

              {dashboard && dashboard.recent_past.length > 0 && (
                <section>
                  <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-ink-muted dark:text-ink-muted-dark">
                    {t('home.recentPast')}
                  </h2>
                  <div className="grid gap-4 sm:grid-cols-2">
                    {dashboard.recent_past.map((article) => (
                      <TeaserCard key={article.id} article={article} variant="past" />
                    ))}
                  </div>
                </section>
              )}

              {isEmpty && <p className="text-ink-soft dark:text-ink-soft-dark">{t('home.empty')}</p>}
            </>
          )}
        </div>

        <div className="hidden md:block md:w-72 md:shrink-0">
          <EventCalendar />
        </div>
      </div>

      <div className="mt-6 flex justify-center md:hidden">
        <button
          type="button"
          onClick={() => setShowMobileCalendar(true)}
          className="rounded-lg border-2 border-ink px-4 py-2 text-sm font-medium text-ink dark:border-ink-dark/30 dark:text-ink-dark"
        >
          {t('calendar.showButton')}
        </button>
      </div>

      {showMobileCalendar && (
        <div className="fixed inset-0 z-50 flex flex-col overflow-y-auto bg-paper p-4 text-ink dark:bg-paper-dark dark:text-ink-dark md:hidden">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold">{t('calendar.title')}</h2>
            <button
              type="button"
              onClick={() => setShowMobileCalendar(false)}
              className="rounded-lg border-2 border-ink px-3 py-1.5 text-sm dark:border-ink-dark/30"
            >
              {t('calendar.close')}
            </button>
          </div>
          <EventCalendar />
        </div>
      )}
    </div>
  )
}
