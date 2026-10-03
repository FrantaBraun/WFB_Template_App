/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import usePageMeta from '../../hooks/usePageMeta'
import {
  API_BASE,
  CATEGORIES_PATH,
  RECEIPTS_PATH,
  categoryPath,
  fetchJson,
  formatUsd,
  usePaymentsInfo,
  type MyPost,
  type Page,
} from './api'
import BoostPanel from './BoostPanel'

/** Published, but its whole category was blocked: nobody can see it until the category is restored. */
function hidden(post: MyPost): boolean {
  return post.status === 'published' && post.category_blocked
}

/**
 * /my-posts - the signed-in user's own posts in every state, since posts are
 * anonymous on the boards and this is where an author finds them again: to
 * see what a post is worth and what they paid for it, to raise its value, or
 * to learn that it was blocked (and why).
 */
export default function MyPostsPage() {
  const { t, i18n } = useTranslation('boards')
  const { user, loading } = useAuth()
  const payments = usePaymentsInfo()
  const [items, setItems] = useState<MyPost[] | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState(false)
  const [boosting, setBoosting] = useState<string | null>(null)
  // Rows handed over so far - the next offset, assigned from the page shown.
  const fetched = useRef(0)

  usePageMeta({ title: t('myPosts.title') })

  useEffect(() => {
    if (loading || !user) return
    let cancelled = false
    fetchJson<Page<MyPost>>(`${API_BASE}/me/posts?offset=0`)
      .then((page) => {
        if (cancelled) return
        fetched.current = page.items.length
        setItems(page.items)
        setHasMore(page.has_more)
      })
      .catch(() => !cancelled && setError(true))
    return () => {
      cancelled = true
    }
  }, [user, loading])

  async function loadMore() {
    setLoadingMore(true)
    try {
      const page = await fetchJson<Page<MyPost>>(`${API_BASE}/me/posts?offset=${fetched.current}`)
      fetched.current += page.items.length
      setItems((current) => {
        const seen = new Set((current ?? []).map((p) => p.id))
        return [...(current ?? []), ...page.items.filter((p) => !seen.has(p.id))]
      })
      setHasMore(page.has_more)
    } catch {
      setError(true)
    } finally {
      setLoadingMore(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-12 text-slate-900 dark:text-slate-100">
      <p className="mb-6 text-sm">
        <Link to={CATEGORIES_PATH} className="underline underline-offset-4 hover:no-underline">
          ← {t('category.back')}
        </Link>
      </p>
      <h1 className="mb-6 text-3xl font-bold tracking-tight">{t('myPosts.title')}</h1>

      {loading ? (
        <p className="text-slate-500 dark:text-slate-400">{t('common.loading')}</p>
      ) : !user ? (
        <p>
          <Link to="/login" className="font-medium underline underline-offset-4 hover:no-underline">
            {t('myPosts.loginRequired')}
          </Link>
        </p>
      ) : (
        <>
          <p className="mb-6 text-sm text-slate-600 dark:text-slate-400">
            {t('myPosts.explain')}{' '}
            <Link to={RECEIPTS_PATH} className="underline underline-offset-4 hover:no-underline">
              {t('myPosts.receipts')}
            </Link>
          </p>
          {error && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{t('myPosts.error')}</p>}
          {items === null ? (
            !error && <p className="text-slate-500 dark:text-slate-400">{t('common.loading')}</p>
          ) : items.length === 0 ? (
            <p className="rounded-lg border border-dashed border-slate-300 p-8 text-center text-slate-500 dark:border-slate-700 dark:text-slate-400">
              {t('myPosts.empty')}
            </p>
          ) : (
            <ul className="divide-y divide-slate-200 border-y border-slate-200 dark:divide-slate-800 dark:border-slate-800">
              {items.map((post) => (
                <li key={post.id} className="py-5">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <h2 className="break-words font-bold">{post.title}</h2>
                    <span className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
                      {t(`myPosts.status.${hidden(post) ? 'hidden' : post.status}`)}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                    {post.category_blocked ? (
                      post.category_title
                    ) : (
                      <Link to={categoryPath(post.category_slug)} className="underline">
                        {post.category_title}
                      </Link>
                    )}
                    {' · '}
                    {new Date(post.created_at).toLocaleDateString(i18n.language)}
                  </p>
                  <p className="mt-2 whitespace-pre-wrap break-words">{post.body}</p>
                  <p className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-600 dark:text-slate-400">
                    <span>
                      {t('post.value')}: <strong>{post.value.toLocaleString(i18n.language)}</strong>
                    </span>
                    <span>{t('post.resonances', { count: post.resonance_count })}</span>
                    <span>{t('myPosts.paid', { amount: formatUsd(post.paid_cents, i18n.language) })}</span>
                  </p>

                  {hidden(post) && <p className="mt-2 text-sm">{t('myPosts.hiddenNote')}</p>}
                  {post.status !== 'published' && post.moderation_reason && (
                    <p className="mt-2 text-sm">
                      <strong>{t('myPosts.reason')}:</strong>{' '}
                      {t(`admin.reason.${post.moderation_reason}`, { defaultValue: post.moderation_reason })}
                    </p>
                  )}

                  {post.status === 'published' && !post.category_blocked && payments?.enabled && boosting !== post.id && (
                    <button
                      type="button"
                      onClick={() => setBoosting(post.id)}
                      className="mt-3 rounded border border-slate-300 px-3 py-1 text-sm hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
                    >
                      {t('boost.open')}
                    </button>
                  )}
                  {boosting === post.id && (
                    <div className="mt-4">
                      <BoostPanel post={post} onClose={() => setBoosting(null)} />
                    </div>
                  )}
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
                className="rounded-lg border border-slate-300 px-5 py-2 font-medium hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:hover:bg-slate-800"
              >
                {loadingMore ? t('common.loading') : t('common.loadMore')}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
