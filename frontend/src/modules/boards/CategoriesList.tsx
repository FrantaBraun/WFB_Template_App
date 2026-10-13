/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import {
  API_BASE,
  CATEGORIES_PATH,
  MODERATION_PATH,
  categoryPath,
  fetchJson,
  useBoardsMe,
  type Category,
  type Page,
} from './api'
import { card, chip, primaryButton, secondaryButton } from './styles'

/**
 * The list of categories (boards), busiest first, with a "Load more"
 * button, plus the link to create a new one (or to sign in first).
 * Exported for applications that show it on other pages - the home page
 * does. `headingTag` is the heading level it renders its title as, so it
 * can be the page's own h1 or a section's h2.
 */
export default function CategoriesList({ headingTag: Heading = 'h2' }: { headingTag?: 'h1' | 'h2' }) {
  const { t } = useTranslation('boards')
  const { user } = useAuth()
  const me = useBoardsMe()
  const [items, setItems] = useState<Category[] | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState(false)
  // Rows the server has handed us so far - the next offset. Assigned from
  // the page that is shown, never accumulated per request: React StrictMode
  // runs the mount effect twice in development, and both runs must leave
  // the same offset behind.
  const fetched = useRef(0)
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    loadFirst()
    return () => {
      mounted.current = false
    }
  }, [])

  async function fetchPage(offset: number): Promise<Page<Category> | null> {
    try {
      const page = await fetchJson<Page<Category>>(`${API_BASE}/categories?offset=${offset}`)
      setError(false)
      return page
    } catch {
      setError(true)
      return null
    }
  }

  async function loadFirst() {
    const page = await fetchPage(0)
    if (!mounted.current || !page) return
    fetched.current = page.items.length
    setItems(page.items)
    setHasMore(page.has_more)
  }

  async function loadMore() {
    setLoadingMore(true)
    const page = await fetchPage(fetched.current)
    if (mounted.current && page) {
      fetched.current += page.items.length
      setItems((current) => {
        const seen = new Set((current ?? []).map((c) => c.id))
        return [...(current ?? []), ...page.items.filter((c) => !seen.has(c.id))]
      })
      setHasMore(page.has_more)
    }
    if (mounted.current) setLoadingMore(false)
  }

  return (
    <section>
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-3">
        <Heading className={Heading === 'h1' ? 'text-3xl font-extrabold tracking-tight' : 'text-2xl font-extrabold tracking-tight'}>
          <span aria-hidden="true">🏟️</span> {t('list.title')}
        </Heading>
        <div className="flex flex-wrap items-center gap-2">
          {me?.is_admin && (
            <Link to={MODERATION_PATH} className={secondaryButton}>
              {t('list.moderation')}
            </Link>
          )}
          <Link to={user ? `${CATEGORIES_PATH}/new` : '/login'} className={user ? primaryButton : secondaryButton}>
            {user ? t('list.create') : t('list.loginToCreate')}
          </Link>
        </div>
      </div>

      {error && (
        <p className="mb-4 text-sm text-red-600 dark:text-red-400">
          {t('list.error')}{' '}
          <button type="button" onClick={items === null ? loadFirst : loadMore} className="underline">
            {t('common.retry')}
          </button>
        </p>
      )}

      {items === null ? (
        !error && <p className="text-slate-500 dark:text-slate-400">{t('common.loading')}</p>
      ) : items.length === 0 ? (
        <p className="rounded-lg border border-dashed border-slate-300 p-8 text-center text-slate-500 dark:border-slate-700 dark:text-slate-400">
          {t('list.empty')}
        </p>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2">
          {items.map((category) => (
            <li key={category.id}>
              <Link
                to={categoryPath(category.slug)}
                className={`group flex h-full flex-col p-5 transition hover:border-violet-300 hover:shadow-md motion-safe:hover:-translate-y-0.5 dark:hover:border-violet-500/50 ${card}`}
              >
                <h3 className="break-words text-lg font-bold group-hover:text-violet-700 dark:group-hover:text-violet-300">
                  {category.title}
                </h3>
                <p className="mt-1 line-clamp-3 whitespace-pre-line break-words text-sm text-slate-600 dark:text-slate-400">
                  {category.description}
                </p>
                <p className="mt-auto pt-4">
                  <span className={chip}>{t('list.posts', { count: category.post_count })}</span>
                </p>
              </Link>
            </li>
          ))}
        </ul>
      )}

      {hasMore && (
        <div className="mt-6 flex justify-center">
          <button
            type="button"
            onClick={loadMore}
            disabled={loadingMore}
            className={secondaryButton}
          >
            {loadingMore ? t('common.loading') : t('common.loadMore')}
          </button>
        </div>
      )}
    </section>
  )
}
