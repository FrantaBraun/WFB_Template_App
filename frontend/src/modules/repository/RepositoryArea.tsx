/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, Route, Routes, useLocation, useParams } from 'react-router-dom'
import { AreaContext } from './areaContext'
import {
  errorStatus,
  fetchJson,
  repositoryApi,
  repositoryPath,
  tablePath,
  tablesPath,
  type RepositoryDetail,
} from './api'
import RecordFormPage from './RecordFormPage'
import RecordPage from './RecordPage'
import RepositoryPage from './RepositoryPage'
import TableFormPage from './TableFormPage'
import TablePage from './TablePage'
import TablesPage from './TablesPage'
import { schemeClass } from './schemes'
import { PageMessage, RepositoryGate } from './ui'

function SideMenu({ repository }: { repository: RepositoryDetail }) {
  const { t } = useTranslation('repository')
  const { pathname } = useLocation()
  const [open, setOpen] = useState(false)

  const base = repositoryPath(repository.slug)
  const itemClass = (active: boolean) =>
    `repo-focus flex items-center justify-between gap-2 rounded-lg px-3 py-2 text-sm text-slate-800 hover:bg-white/60 dark:text-slate-200 dark:hover:bg-white/10 ${active ? 'repo-selected font-medium' : ''}`

  return (
    <nav aria-label={t('area.menu')} className="md:w-64 md:shrink-0">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="repo-focus mb-2 flex w-full items-center justify-between rounded-lg border repo-border px-3 py-2 text-sm font-medium text-slate-800 dark:text-slate-200 md:hidden"
      >
        {t('area.tablesMenu')}
        <span aria-hidden="true">{open ? '▴' : '▾'}</span>
      </button>
      <div className={`${open ? 'block' : 'hidden'} space-y-1 rounded-2xl border repo-border repo-tint-strong-bg p-2 md:block`}>
        <Link to={base} className={itemClass(pathname === base)}>
          <span className="truncate font-semibold">{repository.name}</span>
        </Link>
        <p className="px-3 pt-2 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">{t('area.tables')}</p>
        {repository.tables.length === 0 && <p className="px-3 py-1 text-sm text-slate-500 dark:text-slate-400">{t('area.noTables')}</p>}
        {repository.tables.map((table) => {
          const path = tablePath(repository.slug, table.slug)
          return (
            <Link key={table.id} to={path} className={itemClass(pathname === path || pathname.startsWith(`${path}/`))}>
              <span className="truncate">{table.name}</span>
              <span className="shrink-0 text-xs text-slate-500 dark:text-slate-400">{table.record_count}</span>
            </Link>
          )
        })}
        <div className="border-t border-black/10 pt-1 dark:border-white/10">
          <Link to={tablesPath(repository.slug)} className={itemClass(pathname === tablesPath(repository.slug))}>
            {t('area.manageTables')}
          </Link>
        </div>
      </div>
    </nav>
  )
}

function AreaShell({ slug }: { slug: string }) {
  const { t } = useTranslation('repository')
  const [repository, setRepository] = useState<RepositoryDetail | null>(null)
  const [error, setError] = useState<'notFound' | 'error' | null>(null)

  const reload = useCallback(async () => {
    setRepository(await fetchJson<RepositoryDetail>(repositoryApi(slug)))
  }, [slug])

  useEffect(() => {
    let cancelled = false
    setRepository(null)
    setError(null)
    fetchJson<RepositoryDetail>(repositoryApi(slug))
      .then((found) => !cancelled && setRepository(found))
      .catch((e) => !cancelled && setError(errorStatus(e) === 404 ? 'notFound' : 'error'))
    return () => {
      cancelled = true
    }
  }, [slug])

  const value = useMemo(() => (repository ? { repository, reload } : null), [repository, reload])

  if (error) return <PageMessage error>{t(error === 'notFound' ? 'repository.notFound' : 'repository.loadError')}</PageMessage>
  if (!repository || !value) return <PageMessage>{t('common.loading')}</PageMessage>

  return (
    <AreaContext.Provider value={value}>
      <div className={`${schemeClass(repository.color_scheme)} repo-tint-bg min-h-[calc(100vh-8rem)] text-slate-900 dark:text-slate-100`}>
        <div className="mx-auto flex max-w-6xl flex-col gap-6 px-3 py-6 sm:px-6 md:flex-row md:items-start">
          <SideMenu repository={repository} />
          <div className="min-w-0 flex-1">
            <Routes>
              <Route index element={<RepositoryPage />} />
              <Route path="tables" element={<TablesPage />} />
              <Route path="table/new" element={<TableFormPage />} />
              <Route path="table/:table" element={<TablePage />} />
              <Route path="table/:table/edit" element={<TableFormPage />} />
              <Route path="table/:table/item/new" element={<RecordFormPage />} />
              <Route path="table/:table/item/:item" element={<RecordPage />} />
              <Route path="table/:table/item/:item/edit" element={<RecordFormPage />} />
              <Route path="*" element={<PageMessage error>{t('common.notFound')}</PageMessage>} />
            </Routes>
          </div>
        </div>
      </div>
    </AreaContext.Provider>
  )
}

/**
 * Everything under /repository/:repo - loads the repository, tints the page
 * with its colour scheme, shows its tables as a side menu and routes to the
 * pages inside it (see index.tsx for the paths).
 */
export default function RepositoryArea() {
  const { repo } = useParams()
  return (
    <RepositoryGate>
      <AreaShell key={repo} slug={repo ?? ''} />
    </RepositoryGate>
  )
}
