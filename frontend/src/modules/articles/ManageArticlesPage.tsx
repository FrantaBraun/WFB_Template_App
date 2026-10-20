/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import usePageMeta from '../../hooks/usePageMeta'
import { API_BASE, ARTICLES_PATH, fetchJson, formatDate, type ArticleAdminListItem, type ArticleStatus, type Page } from './api'
import { ArticlesGate, inputClass, primaryButtonClass, secondaryButtonClass, STATUS_STYLES } from './ui'

const PAGE_SIZE = 30

function ManageList() {
  const { t, i18n } = useTranslation('articles')
  const [status, setStatus] = useState<ArticleStatus | ''>('')
  const [query, setQuery] = useState('')
  const [searchText, setSearchText] = useState('')
  const [items, setItems] = useState<ArticleAdminListItem[] | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const [error, setError] = useState(false)

  useEffect(() => {
    const timer = setTimeout(() => setSearchText(query.trim()), 300)
    return () => clearTimeout(timer)
  }, [query])

  const load = useCallback(
    (offset: number) => {
      const params = new URLSearchParams({ offset: String(offset), limit: String(PAGE_SIZE) })
      if (status) params.set('status', status)
      if (searchText) params.set('q', searchText)
      return fetchJson<Page<ArticleAdminListItem>>(`${API_BASE}/manage?${params}`)
    },
    [status, searchText],
  )

  useEffect(() => {
    let cancelled = false
    setItems(null)
    setError(false)
    load(0)
      .then((page) => {
        if (cancelled) return
        setItems(page.items)
        setHasMore(page.has_more)
      })
      .catch(() => !cancelled && setError(true))
    return () => {
      cancelled = true
    }
  }, [load])

  async function loadMore() {
    if (!items) return
    try {
      const page = await load(items.length)
      setItems([...items, ...page.items])
      setHasMore(page.has_more)
    } catch {
      setError(true)
    }
  }

  return (
    <div className="mx-auto max-w-4xl px-6 py-12 text-slate-900 dark:text-slate-100">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-3xl font-semibold tracking-tight">{t('manage.title')}</h1>
        <div className="flex gap-2">
          <Link to={`${ARTICLES_PATH}/manage/types`} className={secondaryButtonClass}>
            {t('manage.types')}
          </Link>
          <Link to={`${ARTICLES_PATH}/manage/new`} className={primaryButtonClass}>
            {t('manage.new')}
          </Link>
        </div>
      </div>

      <div className="mb-4 grid gap-3 sm:grid-cols-[1fr_auto]">
        <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t('list.searchPlaceholder')} aria-label={t('list.searchPlaceholder')} className={inputClass} />
        <select value={status} onChange={(e) => setStatus(e.target.value as ArticleStatus | '')} aria-label={t('manage.statusFilter')} className={`${inputClass} sm:w-48`}>
          <option value="">{t('manage.allStatuses')}</option>
          {(['draft', 'published', 'archived'] as const).map((s) => (
            <option key={s} value={s}>
              {t(`status.${s}`)}
            </option>
          ))}
        </select>
      </div>

      {error && <p className="text-sm text-red-600 dark:text-red-400">{t('list.error')}</p>}
      {items === null && !error && <p className="text-slate-500 dark:text-slate-400">{t('common.loading')}</p>}
      {items && items.length === 0 && <p className="text-slate-500 dark:text-slate-400">{t('manage.empty')}</p>}

      {items && items.length > 0 && (
        <ul className="divide-y divide-slate-200 overflow-hidden rounded-2xl border border-slate-200 bg-white dark:divide-slate-800 dark:border-slate-800 dark:bg-slate-900">
          {items.map((article) => (
            <li key={article.id}>
              <Link to={`${ARTICLES_PATH}/manage/${article.id}`} className="flex flex-wrap items-center gap-3 px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-800/60">
                <span className="w-32 shrink-0 text-sm text-slate-500 dark:text-slate-400">{formatDate(article.created_at, i18n.language)}</span>
                <span className="min-w-0 flex-1 truncate font-medium">
                  {article.pinned && <span aria-label={t('card.pinned')}>📌 </span>}
                  {article.title}
                </span>
                {article.type && <span className="rounded-full border border-slate-300 px-2 py-0.5 text-xs dark:border-slate-600">{article.type.name}</span>}
                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[article.status]}`}>{t(`status.${article.status}`)}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}

      {hasMore && (
        <div className="mt-6 text-center">
          <button type="button" onClick={loadMore} className={secondaryButtonClass}>
            {t('list.loadMore')}
          </button>
        </div>
      )}
    </div>
  )
}

/** /articles/manage - every article in every status, for administrators. */
export default function ManageArticlesPage() {
  const { t } = useTranslation('articles')
  usePageMeta({ title: t('manage.title') })
  return (
    <ArticlesGate>
      <ManageList />
    </ArticlesGate>
  )
}
