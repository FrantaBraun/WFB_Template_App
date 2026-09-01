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

interface PageRow {
  id: string
  heading: string
  status: 'draft' | 'published'
  updated_at: string
}

type SortColumn = 'heading' | 'status' | 'updated_at'

export default function AdminPagesList() {
  const { t } = useTranslation()
  usePageMeta({ title: t('admin.pages.title'), description: t('admin.pageDescription') })
  const { user, loading: authLoading } = useRequireAdmin()

  const [pages, setPages] = useState<PageRow[] | null>(null)
  const [error, setError] = useState(false)
  const [filterText, setFilterText] = useState('')
  const [statusFilter, setStatusFilter] = useState<'all' | 'draft' | 'published'>('all')
  const [sortColumn, setSortColumn] = useState<SortColumn>('updated_at')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc')

  useEffect(() => {
    if (!user?.is_admin) return
    apiFetch('/api/admin/pages/')
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setPages)
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

  const visiblePages = useMemo(() => {
    if (!pages) return []
    return pages
      .filter((page) => page.heading.toLowerCase().includes(filterText.toLowerCase()))
      .filter((page) => statusFilter === 'all' || page.status === statusFilter)
      .sort((a, b) => {
        const [aVal, bVal] = [a[sortColumn], b[sortColumn]]
        if (aVal === bVal) return 0
        const cmp = aVal < bVal ? -1 : 1
        return sortDirection === 'asc' ? cmp : -cmp
      })
  }, [pages, filterText, statusFilter, sortColumn, sortDirection])

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
        <h1 className="text-2xl font-semibold tracking-tight">{t('admin.pages.title')}</h1>
        <Link
          to="/admin/pages/new"
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-slate-100 dark:bg-slate-100 dark:text-slate-900"
        >
          {t('admin.pages.new')}
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
          onChange={(e) => setStatusFilter(e.target.value as typeof statusFilter)}
          className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
        >
          <option value="all">{t('admin.statusFilterAll')}</option>
          <option value="draft">{t('admin.status.draft')}</option>
          <option value="published">{t('admin.status.published')}</option>
        </select>
      </div>

      {error && <p className="text-sm text-red-600 dark:text-red-400">{t('admin.pages.loadError')}</p>}

      {pages && pages.length === 0 && (
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('admin.pages.empty')}</p>
      )}

      {pages && pages.length > 0 && (
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-slate-500 dark:border-slate-800 dark:text-slate-400">
              <SortableColumnHeader label={t('admin.pages.headingColumn')} column="heading" activeColumn={sortColumn} direction={sortDirection} onSort={handleSort} />
              <SortableColumnHeader label={t('admin.pages.statusColumn')} column="status" activeColumn={sortColumn} direction={sortDirection} onSort={handleSort} />
              <SortableColumnHeader label={t('admin.pages.updatedColumn')} column="updated_at" activeColumn={sortColumn} direction={sortDirection} onSort={handleSort} />
              <th className="py-2" />
            </tr>
          </thead>
          <tbody>
            {visiblePages.map((page) => (
              <tr key={page.id} className="border-b border-slate-100 dark:border-slate-900">
                <td className="py-2">{page.heading}</td>
                <td className="py-2">{t(`admin.status.${page.status}`)}</td>
                <td className="py-2 text-slate-500 dark:text-slate-400">
                  {new Date(page.updated_at).toLocaleDateString()}
                </td>
                <td className="py-2 text-right">
                  <Link to={`/admin/pages/${page.id}/edit`} className="text-slate-600 underline dark:text-slate-400">
                    {t('admin.pages.editLink')}
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
