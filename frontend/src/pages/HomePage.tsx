/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { apiFetch } from '../api/client'

interface ArticleTeaser {
  id: string
  title: string
  slug: string
  short_description: string
  event_date: string
}

interface Dashboard {
  upcoming: ArticleTeaser | null
  pinned: ArticleTeaser[]
  recent_past: ArticleTeaser[]
}

function TeaserCard({ article }: { article: ArticleTeaser }) {
  return (
    <Link
      to={`/clanek/${article.slug}`}
      className="block rounded-2xl border border-slate-200 bg-white p-5 hover:border-slate-300 dark:border-slate-800 dark:bg-slate-900 dark:hover:border-slate-700"
    >
      <p className="text-sm text-slate-500 dark:text-slate-400">
        {new Date(article.event_date).toLocaleDateString()}
      </p>
      <h3 className="mt-1 font-semibold text-slate-900 dark:text-slate-100">{article.title}</h3>
      <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{article.short_description}</p>
    </Link>
  )
}

/** Public landing page - fetches GET /api/articles/dashboard once and
 * renders its three groups (nearest upcoming, pinned, last 5 non-pinned
 * past), each teaser linking through to /clanek/:slug. */
export default function HomePage() {
  const { t } = useTranslation()
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)

  useEffect(() => {
    apiFetch('/api/articles/dashboard')
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setDashboard)
      .catch(() => setDashboard({ upcoming: null, pinned: [], recent_past: [] }))
  }, [])

  const isEmpty = dashboard && !dashboard.upcoming && dashboard.pinned.length === 0 && dashboard.recent_past.length === 0

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-10 px-6 py-16 text-slate-900 dark:text-slate-100">
      <div className="flex flex-col items-center gap-4 text-center">
        <div className="rounded-2xl bg-slate-100 p-4 shadow-lg dark:bg-slate-800">
          <img src="/logo.png" alt="Logo" className="h-12 w-auto object-contain" />
        </div>
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">{t('home.title')}</h1>
      </div>

      {dashboard?.upcoming && (
        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            {t('home.upcoming')}
          </h2>
          <TeaserCard article={dashboard.upcoming} />
        </section>
      )}

      {dashboard && dashboard.pinned.length > 0 && (
        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            {t('home.pinned')}
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {dashboard.pinned.map((article) => (
              <TeaserCard key={article.id} article={article} />
            ))}
          </div>
        </section>
      )}

      {dashboard && dashboard.recent_past.length > 0 && (
        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            {t('home.recentPast')}
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {dashboard.recent_past.map((article) => (
              <TeaserCard key={article.id} article={article} />
            ))}
          </div>
        </section>
      )}

      {isEmpty && <p className="text-center text-slate-600 dark:text-slate-400">{t('home.empty')}</p>}
    </div>
  )
}
