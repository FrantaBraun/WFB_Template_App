/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import usePageMeta from '../../hooks/usePageMeta'
import useRequireAdmin from '../../hooks/useRequireAdmin'

export default function AdminHome() {
  const { t } = useTranslation()
  usePageMeta({ title: t('admin.pageTitle'), description: t('admin.pageDescription') })
  const { user, loading } = useRequireAdmin()

  if (loading || !user?.is_admin) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-900 dark:text-slate-100">
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('common.loading')}</p>
      </div>
    )
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 px-6 py-16 text-slate-900 dark:text-slate-100">
      <h1 className="text-2xl font-semibold tracking-tight">{t('admin.dashboardTitle')}</h1>
      <div className="grid grid-cols-2 gap-4">
        <Link
          to="/admin/pages"
          className="rounded-2xl border border-slate-200 bg-white p-6 font-medium hover:border-slate-300 dark:border-slate-800 dark:bg-slate-900 dark:hover:border-slate-700"
        >
          {t('admin.pagesLink')}
        </Link>
        <Link
          to="/admin/articles"
          className="rounded-2xl border border-slate-200 bg-white p-6 font-medium hover:border-slate-300 dark:border-slate-800 dark:bg-slate-900 dark:hover:border-slate-700"
        >
          {t('admin.articlesLink')}
        </Link>
      </div>
    </div>
  )
}
