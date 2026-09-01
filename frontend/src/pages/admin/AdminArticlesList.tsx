/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../api/client'
import SortableColumnHeader from '../../components/SortableColumnHeader'
import usePageMeta from '../../hooks/usePageMeta'
import useRequireAdmin from '../../hooks/useRequireAdmin'

interface ArticleRow {
  id: string
  title: string
  status: 'draft' | 'published' | 'deleted'
  pinned: boolean
  event_date: string
  updated_at: string
}

type SortColumn = 'title' | 'event_date' | 'status'
type StatusFilter = 'all' | 'draft' | 'published' | 'deleted'

export default function AdminArticlesList() {
  const { t } = useTranslation()
  usePageMeta({ title: t('admin.articles.title'), description: t('admin.pageDescription') })
  const { user, loading: authLoading } = useRequireAdmin()

  const [articles, setArticles] = useState<ArticleRow[] | null>(null)
  const [error, setError] = useState(false)
  const [filterText, setFilterText] = useState('')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [sortColumn, setSortColumn] = useState<SortColumn>('event_date')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc')

  useEffect(() => {
    if (!user?.is_admin) return
    apiFetch('/api/admin/articles/')
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setArticles)
      .catch(() => setError(true))
  }, [user])

  function handleSort(column: SortColumn) {
    if (column === sortColumn) {
      setSortDirection((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortColumn(column)
      setSortDirection('asc')
    }
  }

  const visibleArticles = useMemo(() => {
    if (!articles) return []
    return articles
      .filter((article) => article.title.toLowerCase().includes(filterText.toLowerCase()))
      .filter((article) => statusFilter === 'all' || article.status === statusFilter)
      .sort((a, b) => {
        const [aVal, bVal] = [a[sortColumn], b[sortColumn]]
        if (aVal === bVal) return 0
        const cmp = aVal < bVal ? -1 : 1
        return sortDirection === 'asc' ? cmp : -cmp
      })
  }, [articles, filterText, statusFilter, sortColumn, sortDirection])

  if (authLoading || !user?.is_admin) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-900 dark:text-slate-100">
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('common.loading')}</p>
      </div>
    )
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-16 text-slate-900 dark:text-slate-100">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">{t('admin.articles.title')}</h1>
        <Link
          to="/admin/articles/new"
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-slate-100 dark:bg-slate-100 dark:text-slate-900"
        >
          {t('admin.articles.new')}
        </Link>
      </div>

      <div className="flex gap-3">
        <input
          type="text"
          value={filterText}
          onChange={(e) => setFilterText(e.target.value)}
          placeholder={t('admin.filterPlaceholder')}
          className="flex-1 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
          className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
        >
          <option value="all">{t('admin.statusFilterAll')}</option>
          <option value="draft">{t('admin.status.draft')}</option>
          <option value="published">{t('admin.status.published')}</option>
          <option value="deleted">{t('admin.status.deleted')}</option>
        </select>
      </div>

      {error && <p className="text-sm text-red-600 dark:text-red-400">{t('admin.articles.loadError')}</p>}

      {articles && articles.length === 0 && (
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('admin.articles.empty')}</p>
      )}

      {articles && articles.length > 0 && (
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-slate-500 dark:border-slate-800 dark:text-slate-400">
              <SortableColumnHeader label={t('admin.articles.titleColumn')} column="title" activeColumn={sortColumn} direction={sortDirection} onSort={handleSort} />
              <SortableColumnHeader label={t('admin.articles.eventDateLabel')} column="event_date" activeColumn={sortColumn} direction={sortDirection} onSort={handleSort} />
              <SortableColumnHeader label={t('admin.articles.statusColumn')} column="status" activeColumn={sortColumn} direction={sortDirection} onSort={handleSort} />
              <th className="py-2" />
            </tr>
          </thead>
          <tbody>
            {visibleArticles.map((article) => (
              <tr key={article.id} className="border-b border-slate-100 dark:border-slate-900">
                <td className="py-2">
                  {article.pinned && <span className="mr-1 text-amber-500" title={t('admin.articles.pinnedLabel')}>*</span>}
                  {article.title}
                </td>
                <td className="py-2 text-slate-500 dark:text-slate-400">{article.event_date}</td>
                <td className="py-2">{t(`admin.status.${article.status}`)}</td>
                <td className="py-2 text-right">
                  <Link to={`/admin/articles/${article.id}/edit`} className="text-slate-600 underline dark:text-slate-400">
                    {t('admin.articles.editLink')}
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <Link to="/admin" className="text-sm text-slate-500 underline dark:text-slate-400">
        {t('admin.backToDashboard')}
      </Link>
    </div>
  )
}
