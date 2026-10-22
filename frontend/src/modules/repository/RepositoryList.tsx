/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { API_BASE, AREA_PATH, fetchJson, repositoryPath, type Repository } from './api'
import { DEFAULT_SCHEME, schemeClass } from './schemes'
import { PageMessage, primaryButtonClass } from './ui'

/**
 * The signed-in user's repositories as blocks - name, description, how many
 * tables and records, and an Open button - framed in each repository's own
 * colour scheme, with a button for a new one. Exported for an application's
 * own home page (see src/pages/HomePage.tsx); it renders nothing but this,
 * so the page decides what surrounds it and that the user is signed in.
 */
export default function RepositoryList() {
  const { t } = useTranslation('repository')
  const [repositories, setRepositories] = useState<Repository[] | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let cancelled = false
    fetchJson<Repository[]>(`${API_BASE}/repositories`)
      .then((found) => !cancelled && setRepositories(found))
      .catch(() => !cancelled && setError(true))
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <section className={`${schemeClass(DEFAULT_SCHEME)} text-slate-900 dark:text-slate-100`} aria-labelledby="repository-list-title">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h2 id="repository-list-title" className="text-2xl font-semibold tracking-tight">
          {t('home.yourRepositories')}
        </h2>
        <Link to={`${AREA_PATH}/new`} className={primaryButtonClass}>
          {t('home.newRepository')}
        </Link>
      </div>

      {error && <PageMessage error>{t('home.loadError')}</PageMessage>}
      {repositories === null && !error && <p className="text-slate-500 dark:text-slate-400">{t('common.loading')}</p>}
      {repositories && repositories.length === 0 && (
        <p className="rounded-2xl border border-dashed border-slate-300 p-8 text-center text-slate-600 dark:border-slate-700 dark:text-slate-400">
          {t('home.empty')}
        </p>
      )}

      {repositories && repositories.length > 0 && (
        <ul className="grid gap-4 sm:grid-cols-2">
          {repositories.map((repository) => (
            <li key={repository.id} className={`${schemeClass(repository.color_scheme)} repo-card flex flex-col gap-3 rounded-2xl p-4`}>
              <div className="min-w-0 flex-1">
                <h3 className="truncate text-lg font-semibold">{repository.name}</h3>
                {repository.description && (
                  <p className="mt-1 line-clamp-3 whitespace-pre-line text-sm text-slate-600 dark:text-slate-300">{repository.description}</p>
                )}
              </div>
              <p className="text-sm text-slate-600 dark:text-slate-300">
                {t('home.tableCount', { count: repository.table_count })} · {t('home.recordCount', { count: repository.record_count })}
              </p>
              <Link to={repositoryPath(repository.slug)} className={`${primaryButtonClass} self-start`}>
                {t('home.open')}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
