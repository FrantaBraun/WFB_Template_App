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

interface ArticleRow {
  id: string
  title: string
  status: 'draft' | 'published' | 'deleted'
  pinned: boolean
  event_date: string
  updated_at: string
}

export default function AdminArticlesList() {
  const { t } = useTranslation()
  usePageMeta({ title: t('admin.articles.title'), description: t('admin.pageDescription') })
  const { user, loading: authLoading } = useRequireAdmin()

  const [articles, setArticles] = useState<ArticleRow[] | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    if (!user?.is_admin) return
    apiFetch('/api/admin/articles/')
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setArticles)
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
        <h1 className="text-2xl font-semibold tracking-tight">{t('admin.articles.title')}</h1>
        <Link
          to="/admin/articles/new"
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-slate-100 dark:bg-slate-100 dark:text-slate-900"
        >
          {t('admin.articles.new')}
        </Link>
      </div>

      {error && <p className="text-sm text-red-600 dark:text-red-400">{t('admin.articles.loadError')}</p>}

      {articles && articles.length === 0 && (
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('admin.articles.empty')}</p>
      )}

      {articles && articles.length > 0 && (
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-slate-500 dark:border-slate-800 dark:text-slate-400">
              <th className="py-2 font-medium">{t('admin.articles.titleColumn')}</th>
              <th className="py-2 font-medium">{t('admin.articles.eventDateLabel')}</th>
              <th className="py-2 font-medium">{t('admin.articles.statusColumn')}</th>
              <th className="py-2" />
            </tr>
          </thead>
          <tbody>
            {articles.map((article) => (
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
