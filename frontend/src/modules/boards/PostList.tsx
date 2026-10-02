/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { API_BASE, fetchJson, type Page, type Post } from './api'
import PostCard from './PostCard'

/**
 * A category's posts, highest value first, loaded page by page as the
 * reader scrolls: an IntersectionObserver on a sentinel below the last
 * post asks for the next page shortly before it comes into view. Mount it
 * with a `key` that changes when the list must start over (another
 * category, a new post) - a fresh instance is the reset.
 */
export default function PostList({ slug }: { slug: string }) {
  const { t } = useTranslation('boards')
  const [items, setItems] = useState<Post[]>([])
  const [hasMore, setHasMore] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)
  const sentinel = useRef<HTMLDivElement>(null)
  // Rows the server has handed us - the next offset (not items.length: a
  // post that shifted between two pages is dropped as a repeat below, but
  // the offset still has to move past it).
  const offset = useRef(0)
  const busy = useRef(false)
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  const loadNext = useCallback(async () => {
    if (busy.current) return
    busy.current = true
    setLoading(true)
    setError(false)
    try {
      const page = await fetchJson<Page<Post>>(`${API_BASE}/categories/${slug}/posts?offset=${offset.current}`)
      if (!mounted.current) return
      offset.current += page.items.length
      setItems((current) => {
        const seen = new Set(current.map((p) => p.id))
        return [...current, ...page.items.filter((p) => !seen.has(p.id))]
      })
      setHasMore(page.has_more)
    } catch {
      if (mounted.current) setError(true)
    } finally {
      busy.current = false
      if (mounted.current) setLoading(false)
    }
  }, [slug])

  // (Re)observing after every page makes a sentinel that is still in view
  // - a short first page on a tall screen - trigger the next load at once.
  // No observing while an error is shown, so a failing request isn't
  // retried in a loop; the retry button asks again.
  useEffect(() => {
    const node = sentinel.current
    if (!node || !hasMore || error) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) loadNext()
      },
      { rootMargin: '400px' },
    )
    observer.observe(node)
    return () => observer.disconnect()
  }, [hasMore, error, items.length, loadNext])

  function replace(updated: Post) {
    setItems((current) => current.map((p) => (p.id === updated.id ? updated : p)))
  }

  return (
    <div>
      {items.length > 0 && (
        <div className="divide-y divide-slate-200 border-y border-slate-200 dark:divide-slate-800 dark:border-slate-800">
          {items.map((post) => (
            <PostCard key={post.id} post={post} onChange={replace} />
          ))}
        </div>
      )}

      {!hasMore && items.length === 0 && !error && (
        <p className="rounded-lg border border-dashed border-slate-300 p-8 text-center text-slate-500 dark:border-slate-700 dark:text-slate-400">
          {t('category.empty')}
        </p>
      )}

      {error && (
        <p className="py-4 text-sm text-red-600 dark:text-red-400">
          {t('category.error')}{' '}
          <button type="button" onClick={loadNext} className="underline">
            {t('common.retry')}
          </button>
        </p>
      )}

      {loading && <p className="py-4 text-center text-sm text-slate-500 dark:text-slate-400">{t('common.loading')}</p>}

      {/* The scroll trigger; kept in the DOM while there may be more. */}
      {hasMore && <div ref={sentinel} aria-hidden="true" className="h-px" />}
    </div>
  )
}
