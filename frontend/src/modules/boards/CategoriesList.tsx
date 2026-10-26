/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
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

/** How long the reader has to stop typing before the list is fetched again. */
const SEARCH_DELAY_MS = 300
/** The backend refuses a longer query (422). */
const SEARCH_MAX_LENGTH = 100

const searchInput =
  'w-full rounded-full border border-slate-300 bg-white py-2 pl-10 pr-4 text-slate-900 focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-500/30 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100'

/**
 * The list of categories (boards), busiest first (most posts), with a search
 * box (title and description, ignoring case and diacritics - the backend
 * does the matching), a "Load more" button, and - for an administrator, the
 * only one who can create a category - the link to create a new one.
 * Exported for applications that show it on other pages - the home page
 * does. `headingTag` is the heading level it renders its title as, so it
 * can be the page's own h1 or a section's h2.
 *
 * The search text is the list's own state unless the page passes `query` and
 * `onQueryChange`, which is how /categories keeps it in the address
 * (`?q=`), so a search can be shared and survives a reload.
 */
export default function CategoriesList({
  headingTag: Heading = 'h2',
  query: controlledQuery,
  onQueryChange,
}: {
  headingTag?: 'h1' | 'h2'
  query?: string
  onQueryChange?: (query: string) => void
}) {
  const { t } = useTranslation('boards')
  const me = useBoardsMe()
  const [ownQuery, setOwnQuery] = useState('')
  const query = controlledQuery ?? ownQuery
  const setQuery = onQueryChange ?? setOwnQuery
  // What is actually searched for: `query` once the reader pauses typing.
  const [term, setTerm] = useState(query.trim())
  const [items, setItems] = useState<Category[] | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState(false)
  // Bumped by "Try again", to run the first-page effect once more.
  const [attempt, setAttempt] = useState(0)
  // Rows the server has handed us so far - the next offset. Assigned from
  // the page that is shown, never accumulated per request: React StrictMode
  // runs the mount effect twice in development, and both runs must leave
  // the same offset behind.
  const fetched = useRef(0)
  // The search the list on screen belongs to; an answer for another one is dropped.
  const shownTerm = useRef(term)
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  useEffect(() => {
    const wanted = query.trim()
    if (wanted === term) return
    const timer = setTimeout(() => setTerm(wanted), SEARCH_DELAY_MS)
    return () => clearTimeout(timer)
  }, [query, term])

  async function fetchPage(search: string, offset: number): Promise<Page<Category> | null> {
    const params = new URLSearchParams({ offset: String(offset) })
    if (search) params.set('q', search)
    try {
      const page = await fetchJson<Page<Category>>(`${API_BASE}/categories?${params}`)
      setError(false)
      return page
    } catch {
      setError(true)
      return null
    }
  }

  useEffect(() => {
    let cancelled = false
    shownTerm.current = term
    setSearching(true)
    fetchPage(term, 0).then((page) => {
      if (cancelled) return
      setSearching(false)
      if (!page) return
      fetched.current = page.items.length
      setItems(page.items)
      setHasMore(page.has_more)
    })
    return () => {
      cancelled = true
    }
  }, [term, attempt])

  async function loadMore() {
    const search = term
    setLoadingMore(true)
    const page = await fetchPage(search, fetched.current)
    if (mounted.current && page && shownTerm.current === search) {
      fetched.current += page.items.length
      setItems((current) => {
        const seen = new Set((current ?? []).map((c) => c.id))
        return [...(current ?? []), ...page.items.filter((c) => !seen.has(c.id))]
      })
      setHasMore(page.has_more)
    }
    if (mounted.current) setLoadingMore(false)
  }

  const searched = term !== ''

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
          {me?.is_admin && (
            <Link to={`${CATEGORIES_PATH}/new`} className={primaryButton}>
              {t('list.create')}
            </Link>
          )}
        </div>
      </div>

      <form role="search" onSubmit={(event) => event.preventDefault()} className="mb-5">
        <label htmlFor="category-search" className="sr-only">
          {t('list.searchLabel')}
        </label>
        <div className="relative">
          <span aria-hidden="true" className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-slate-400">
            🔍
          </span>
          <input
            id="category-search"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            maxLength={SEARCH_MAX_LENGTH}
            placeholder={t('list.searchPlaceholder')}
            autoComplete="off"
            enterKeyHint="search"
            className={searchInput}
          />
        </div>
        <p className="mt-2 px-1 text-xs text-slate-500 dark:text-slate-400">{t('list.sortedBy')}</p>
      </form>

      {error && (
        <p className="mb-4 text-sm text-red-600 dark:text-red-400">
          {t('list.error')}{' '}
          <button type="button" onClick={items === null ? () => setAttempt((n) => n + 1) : loadMore} className="underline">
            {t('common.retry')}
          </button>
        </p>
      )}

      <div aria-busy={searching}>
        {items === null ? (
          !error && <p className="text-slate-500 dark:text-slate-400">{t('common.loading')}</p>
        ) : items.length === 0 ? (
          <p className="rounded-lg border border-dashed border-slate-300 p-8 text-center text-slate-500 dark:border-slate-700 dark:text-slate-400">
            {searched ? t('list.noResults', { query: term }) : t('list.empty')}
            {searched && (
              <>
                {' '}
                <button type="button" onClick={() => setQuery('')} className="underline underline-offset-4 hover:no-underline">
                  {t('list.clearSearch')}
                </button>
              </>
            )}
          </p>
        ) : (
          <>
            {searched && (
              <p role="status" className="mb-3 text-sm text-slate-600 dark:text-slate-400">
                {hasMore ? t('list.foundMore', { shown: items.length }) : t('list.found', { count: items.length })}
              </p>
            )}
            <ul className={`grid gap-4 sm:grid-cols-2 ${searching ? 'opacity-60' : ''}`}>
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
          </>
        )}
      </div>

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
