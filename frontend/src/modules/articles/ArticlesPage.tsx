/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import usePageMeta from '../../hooks/usePageMeta'
import { useAuth } from '../../context/AuthContext'
import { Link } from 'react-router-dom'
import ArticleCard from './ArticleCard'
import { API_BASE, ARTICLES_PATH, fetchJson, formatDate, type ArticleTeaser, type ArticleType, type Page } from './api'
import { inputClass, secondaryButtonClass } from './ui'

const PAGE_SIZE = 12

/** /articles - newest first, with a type filter and search over title, perex and full text (archived articles included in search). */
export default function ArticlesPage() {
  const { t, i18n } = useTranslation('articles')
  const { user } = useAuth()
  usePageMeta({ title: t('list.title'), description: t('list.description') })

  const [types, setTypes] = useState<ArticleType[]>([])
  const [typeId, setTypeId] = useState('')
  const [includeArchived, setIncludeArchived] = useState(false)
  const [query, setQuery] = useState('')
  const [searchText, setSearchText] = useState('')
  const [items, setItems] = useState<ArticleTeaser[] | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const [error, setError] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)

  useEffect(() => {
    fetchJson<ArticleType[]>(`${API_BASE}/types`)
      .then(setTypes)
      .catch(() => {})
  }, [])

  // Typing doesn't search on every key stroke.
  useEffect(() => {
    const timer = setTimeout(() => setSearchText(query.trim()), 300)
    return () => clearTimeout(timer)
  }, [query])

  const load = useCallback(
    async (offset: number): Promise<{ items: ArticleTeaser[]; hasMore: boolean }> => {
      if (searchText) {
        // The search endpoint also finds archived articles; it is not paged.
        const found = await fetchJson<ArticleTeaser[]>(`${API_BASE}/search?q=${encodeURIComponent(searchText)}`)
        return { items: typeId ? found.filter((a) => a.type?.id === typeId) : found, hasMore: false }
      }
      const params = new URLSearchParams({ offset: String(offset), limit: String(PAGE_SIZE) })
      if (typeId) params.set('type_id', typeId)
      if (includeArchived) params.set('include_archived', 'true')
      const page = await fetchJson<Page<ArticleTeaser>>(`${API_BASE}?${params}`)
      return { items: page.items, hasMore: page.has_more }
    },
    [searchText, typeId, includeArchived],
  )

  useEffect(() => {
    let cancelled = false
    setItems(null)
    setError(false)
    load(0)
      .then((result) => {
        if (cancelled) return
        setItems(result.items)
        setHasMore(result.hasMore)
      })
      .catch(() => !cancelled && setError(true))
    return () => {
      cancelled = true
    }
  }, [load])

  async function loadMore() {
    if (!items) return
    setLoadingMore(true)
    try {
      const result = await load(items.length)
      setItems([...items, ...result.items])
      setHasMore(result.hasMore)
    } catch {
      setError(true)
    } finally {
      setLoadingMore(false)
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-6 py-12 text-slate-900 dark:text-slate-100">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-3xl font-semibold tracking-tight">{t('list.title')}</h1>
        {user?.is_admin === true && (
          <Link to={`${ARTICLES_PATH}/manage`} className={secondaryButtonClass}>
            {t('list.manage')}
          </Link>
        )}
      </div>

      <div className="mb-6 grid gap-3 sm:grid-cols-[1fr_auto]">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t('list.searchPlaceholder')}
          aria-label={t('list.searchPlaceholder')}
          className={inputClass}
        />
        {types.length > 0 && (
          <select value={typeId} onChange={(e) => setTypeId(e.target.value)} aria-label={t('list.typeFilter')} className={`${inputClass} sm:w-56`}>
            <option value="">{t('list.allTypes')}</option>
            {types.map((type) => (
              <option key={type.id} value={type.id}>
                {type.name}
              </option>
            ))}
          </select>
        )}
        {!searchText && (
          <label className="flex items-center gap-2 text-sm text-slate-600 sm:col-span-2 dark:text-slate-300">
            <input type="checkbox" checked={includeArchived} onChange={(e) => setIncludeArchived(e.target.checked)} />
            {t('list.includeArchived')}
          </label>
        )}
      </div>

      {error && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{t('list.error')}</p>}
      {items === null && !error && <p className="text-slate-500 dark:text-slate-400">{t('common.loading')}</p>}
      {items && items.length === 0 && (
        <p className="text-slate-500 dark:text-slate-400">{searchText ? t('list.noResults') : t('list.empty')}</p>
      )}

      {items && items.length > 0 && (
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((article) => (
            <li key={article.id}>
              <ArticleCard article={article} meta={<span>{formatDate(article.created_at, i18n.language)}</span>} />
            </li>
          ))}
        </ul>
      )}

      {hasMore && (
        <div className="mt-6 text-center">
          <button type="button" onClick={loadMore} disabled={loadingMore} className={secondaryButtonClass}>
            {loadingMore ? t('common.loading') : t('list.loadMore')}
          </button>
        </div>
      )}
    </div>
  )
}
