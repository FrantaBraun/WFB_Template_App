/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../api/client'
import usePageMeta from '../../hooks/usePageMeta'
import useRequireAdmin from '../../hooks/useRequireAdmin'

interface PageRow {
  id: string
  heading: string
  status: 'draft' | 'published'
  updated_at: string
}

export default function AdminPagesList() {
  const { t } = useTranslation()
  usePageMeta({ title: t('admin.pages.title'), description: t('admin.pageDescription') })
  const { user, loading: authLoading } = useRequireAdmin()

  const [pages, setPages] = useState<PageRow[] | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    if (!user?.is_admin) return
    apiFetch('/api/admin/pages/')
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setPages)
      .catch(() => setError(true))
  }, [user])

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

      {error && <p className="text-sm text-red-600 dark:text-red-400">{t('admin.pages.loadError')}</p>}

      {pages && pages.length === 0 && (
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('admin.pages.empty')}</p>
      )}

      {pages && pages.length > 0 && (
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-slate-500 dark:border-slate-800 dark:text-slate-400">
              <th className="py-2 font-medium">{t('admin.pages.headingColumn')}</th>
              <th className="py-2 font-medium">{t('admin.pages.statusColumn')}</th>
              <th className="py-2 font-medium">{t('admin.pages.updatedColumn')}</th>
              <th className="py-2" />
            </tr>
          </thead>
          <tbody>
            {pages.map((page) => (
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
