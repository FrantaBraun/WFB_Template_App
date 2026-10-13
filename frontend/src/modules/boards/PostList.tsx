/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { API_BASE, fetchJson, type Page, type Post } from './api'
import PostCard from './PostCard'

/** How long the list waits before fetching itself again, so a reader can watch the order change. */
const REFRESH_MS = 60_000

/**
 * A category's posts, highest value first, loaded page by page as the
 * reader scrolls: an IntersectionObserver on a sentinel below the last
 * post asks for the next page shortly before it comes into view. Mount it
 * with a `key` that changes when the list must start over (another
 * category, a new post) - a fresh instance is the reset.
 *
 * The order is not fixed: other readers' resonances and payments move posts
 * up and down, so the list fetches itself again - as many posts as the
 * reader has loaded, replacing what is shown - every minute while the tab is
 * visible, and at once after a change of the reader's own (a resonance).
 * A refresh is silent: if it fails the list stays as it was and the next one
 * tries again. Each refresh, whoever started it, restarts the minute.
 *
 * It is shown as a leaderboard: a post's place is its position in the list,
 * and after a refresh each card says how many places it climbed or lost among
 * the posts that were already there (see movesBetween) - a post that merely
 * got pushed down by a new one at the top has not lost anything.
 */
export default function PostList({ slug }: { slug: string }) {
  const { t, i18n } = useTranslation('boards')
  const [items, setItems] = useState<Post[]>([])
  const [hasMore, setHasMore] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)
  // When the list was last known to be current: its first page loaded, or the last refresh.
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null)
  // Bumped when a refresh ends, to make the scroll observer look again (below).
  const [revision, setRevision] = useState(0)
  // Places climbed (positive) or lost per post id, as of the last refresh.
  const [moves, setMoves] = useState<Record<string, number>>({})
  // What is shown, for a refresh to compare its result with.
  const shown = useRef<Post[]>([])
  const sentinel = useRef<HTMLDivElement>(null)
  // Rows the server has handed us - the next offset (not items.length: a
  // post that shifted between two pages is dropped as a repeat below, but
  // the offset still has to move past it).
  const offset = useRef(0)
  // One request sequence at a time: loading the next page and refreshing both
  // rewrite the list and the offset, so they must not overlap.
  const busy = useRef(false)
  // A refresh asked for while busy - run it as soon as the other one is done.
  const refreshAgain = useRef(false)
  const refreshTimer = useRef<number | undefined>(undefined)
  // The minute ran out while the tab was hidden: refresh when it is shown again.
  const stale = useRef(false)
  const refreshRef = useRef<() => void>(() => {})
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  const runPending = useCallback(() => {
    if (mounted.current && refreshAgain.current) {
      refreshAgain.current = false
      refreshRef.current()
    }
  }, [])

  const loadNext = useCallback(async () => {
    if (busy.current) return
    busy.current = true
    setLoading(true)
    setError(false)
    try {
      const first = offset.current === 0
      const page = await fetchJson<Page<Post>>(`${API_BASE}/categories/${slug}/posts?offset=${offset.current}`)
      if (!mounted.current) return
      offset.current += page.items.length
      setItems((current) => {
        const seen = new Set(current.map((p) => p.id))
        return [...current, ...page.items.filter((p) => !seen.has(p.id))]
      })
      setHasMore(page.has_more)
      if (first) setUpdatedAt(new Date())
    } catch {
      if (mounted.current) setError(true)
    } finally {
      busy.current = false
      if (mounted.current) setLoading(false)
      runPending()
    }
  }, [slug, runPending])

  /** Arms the timer for the next automatic refresh, replacing any earlier one. */
  const schedule = useCallback(() => {
    window.clearTimeout(refreshTimer.current)
    refreshTimer.current = window.setTimeout(() => {
      // A hidden tab has nobody to watch the order - catch up when it is shown.
      if (document.visibilityState === 'visible') refreshRef.current()
      else stale.current = true
    }, REFRESH_MS)
  }, [])

  const refresh = useCallback(async () => {
    if (busy.current) {
      refreshAgain.current = true
      return
    }
    busy.current = true
    window.clearTimeout(refreshTimer.current)
    stale.current = false
    try {
      // At least the first page, so an empty or not yet loaded list picks up new posts too.
      const wanted = Math.max(offset.current, 1)
      const fresh: Post[] = []
      const seen = new Set<string>()
      let handed = 0
      let more = true
      // Page by page, like the reader did; nothing is shown until all of it has arrived.
      while (handed < wanted && more) {
        const page = await fetchJson<Page<Post>>(`${API_BASE}/categories/${slug}/posts?offset=${handed}`)
        if (!mounted.current) return
        handed += page.items.length
        for (const post of page.items) {
          if (!seen.has(post.id)) {
            seen.add(post.id)
            fresh.push(post)
          }
        }
        more = page.has_more
        if (page.items.length === 0) break
      }
      offset.current = handed
      setMoves(movesBetween(shown.current, fresh))
      setItems(fresh)
      setHasMore(more)
      setError(false)
      setUpdatedAt(new Date())
    } catch {
      // Keep what is shown; the next refresh tries again.
    } finally {
      busy.current = false
      if (mounted.current) {
        setRevision((n) => n + 1)
        schedule()
        runPending()
      }
    }
  }, [slug, schedule, runPending])

  useEffect(() => {
    refreshRef.current = refresh
  }, [refresh])

  useEffect(() => {
    shown.current = items
  }, [items])

  useEffect(() => {
    schedule()
    function onVisible() {
      if (document.visibilityState === 'visible' && stale.current) refreshRef.current()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      window.clearTimeout(refreshTimer.current)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [schedule])

  // (Re)observing after every page makes a sentinel that is still in view
  // - a short first page on a tall screen - trigger the next load at once.
  // It also runs after a refresh: a load the reader's scrolling asked for
  // while the refresh was busy was skipped, and a sentinel that stays in view
  // fires no second event on its own. No observing while an error is shown,
  // so a failing request isn't retried in a loop; the retry button asks again.
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
  }, [hasMore, error, items.length, revision, loadNext])

  // The author hid a post: it leaves the board, and everybody below moves up - fetch the list again.
  function hidden(id: string) {
    setItems((current) => current.filter((p) => p.id !== id))
    void refresh()
  }

  function replace(updated: Post) {
    setItems((current) => current.map((p) => (p.id === updated.id ? updated : p)))
    // The change - a resonance - moves the post in the ranking: fetch the
    // list again so the reader sees the new order, not just the new number.
    void refresh()
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
        <h2 className="text-xl font-extrabold tracking-tight">
          <span aria-hidden="true">🏆</span> {t('board.title')}
        </h2>
        {updatedAt && (
          <p className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
            <span aria-hidden="true" className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75 motion-safe:animate-ping" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
            {t('category.refreshInfo', { time: updatedAt.toLocaleTimeString(i18n.resolvedLanguage ?? i18n.language) })}
          </p>
        )}
      </div>

      {items.length > 0 && (
        <div className="space-y-4">
          {items.map((post, index) => (
            <PostCard key={post.id} post={post} rank={index + 1} trend={moves[post.id] ?? 0} onChange={replace} onHidden={hidden} />
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

/**
 * Places climbed (positive) or lost (negative) per post id between two
 * orders of the board, counted among the posts present in both - one that
 * appeared or disappeared is nobody's overtaking. Posts that kept their
 * place among the others are left out.
 */
function movesBetween(before: Post[], after: Post[]): Record<string, number> {
  const inAfter = new Set(after.map((post) => post.id))
  const inBefore = new Set(before.map((post) => post.id))
  const earlier = new Map(before.filter((post) => inAfter.has(post.id)).map((post, index) => [post.id, index]))
  const moves: Record<string, number> = {}
  after
    .filter((post) => inBefore.has(post.id))
    .forEach((post, index) => {
      const climbed = (earlier.get(post.id) ?? index) - index
      if (climbed !== 0) moves[post.id] = climbed
    })
  return moves
}
