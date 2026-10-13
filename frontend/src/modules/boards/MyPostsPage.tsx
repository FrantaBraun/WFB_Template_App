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
  MY_PAYMENTS_PATH,
  RECEIPTS_PATH,
  categoryPath,
  fetchJson,
  formatUsd,
  postJson,
  usePaymentsInfo,
  type MyPost,
  type Page,
} from './api'
import BoostPanel from './BoostPanel'
import { card, primaryButton, secondaryButton } from './styles'

/**
 * The colour of a post's state label. "hidden" is the author's own doing;
 * "categoryBlocked" is a published post whose category an administrator blocked.
 */
const STATUS_CHIP = {
  published: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-300',
  hidden: 'bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200',
  categoryBlocked: 'bg-amber-100 text-amber-800 dark:bg-amber-500/20 dark:text-amber-200',
  blocked: 'bg-rose-100 text-rose-800 dark:bg-rose-500/20 dark:text-rose-300',
  removed: 'bg-rose-100 text-rose-800 dark:bg-rose-500/20 dark:text-rose-300',
}

/** Published, but its whole category was blocked: nobody can see it until the category is restored. */
function inBlockedCategory(post: MyPost): boolean {
  return post.status === 'published' && post.category_blocked
}

/**
 * /my-posts - the signed-in user's own posts in every state, since posts are
 * anonymous on the boards and this is where an author finds them again: to
 * see what a post is worth and what they paid for it, to raise its value, to
 * hide it or show it again, or to learn that it was blocked (and why).
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
  // The post a hide / show is under way for, and the one it failed for.
  const [changing, setChanging] = useState<string | null>(null)
  const [changeFailed, setChangeFailed] = useState<string | null>(null)
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

  async function changeVisibility(post: MyPost, action: 'hide' | 'show') {
    if (changing || (action === 'hide' && !window.confirm(t('myPosts.confirmHide')))) return
    setChanging(post.id)
    setChangeFailed(null)
    try {
      const updated = await postJson<MyPost>(`${API_BASE}/me/posts/${post.id}/${action}`)
      setItems((current) => (current ?? []).map((p) => (p.id === updated.id ? updated : p)))
      if (action === 'hide') setBoosting((current) => (current === post.id ? null : current))
    } catch {
      setChangeFailed(post.id)
    } finally {
      setChanging(null)
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-12 text-slate-900 dark:text-slate-100">
      <p className="mb-6 text-sm">
        <Link to={CATEGORIES_PATH} className="underline underline-offset-4 hover:no-underline">
          ← {t('category.back')}
        </Link>
      </p>
      <h1 className="mb-6 text-3xl font-extrabold tracking-tight">{t('myPosts.title')}</h1>

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
            <Link to={MY_PAYMENTS_PATH} className="underline underline-offset-4 hover:no-underline">
              {t('myPosts.payments')}
            </Link>
            {' · '}
            <Link to={RECEIPTS_PATH} className="underline underline-offset-4 hover:no-underline">
              {t('myPosts.receipts')}
            </Link>
          </p>
          {error && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{t('myPosts.error')}</p>}
          {items === null ? (
            !error && <p className="text-slate-500 dark:text-slate-400">{t('common.loading')}</p>
          ) : items.length === 0 ? (
            <p className="rounded-2xl border border-dashed border-slate-300 p-8 text-center text-slate-500 dark:border-slate-700 dark:text-slate-400">
              {t('myPosts.empty')}
            </p>
          ) : (
            <ul className="space-y-4">
              {items.map((post) => (
                <li key={post.id} className={`p-5 ${card}`}>
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <h2 className="break-words text-lg font-bold">{post.title}</h2>
                    <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${STATUS_CHIP[inBlockedCategory(post) ? 'categoryBlocked' : post.status]}`}>
                      {t(`myPosts.status.${inBlockedCategory(post) ? 'categoryBlocked' : post.status}`)}
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

                  {inBlockedCategory(post) && <p className="mt-2 text-sm">{t('myPosts.categoryBlockedNote')}</p>}
                  {post.status === 'hidden' && <p className="mt-2 text-sm">{t('myPosts.hiddenNote')}</p>}
                  {post.status !== 'published' && post.moderation_reason && (
                    <p className="mt-2 text-sm">
                      <strong>{t('myPosts.reason')}:</strong>{' '}
                      {t(`admin.reason.${post.moderation_reason}`, { defaultValue: post.moderation_reason })}
                    </p>
                  )}

                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    {post.status === 'published' && !post.category_blocked && payments?.enabled && boosting !== post.id && (
                      <button type="button" onClick={() => setBoosting(post.id)} className={secondaryButton}>
                        {t('boost.open')}
                      </button>
                    )}
                    {post.status === 'published' && (
                      <button
                        type="button"
                        onClick={() => changeVisibility(post, 'hide')}
                        disabled={changing !== null}
                        className={secondaryButton}
                      >
                        {t('myPosts.hide')}
                      </button>
                    )}
                    {post.status === 'hidden' && (
                      <button
                        type="button"
                        onClick={() => changeVisibility(post, 'show')}
                        disabled={changing !== null}
                        className={primaryButton}
                      >
                        {t('myPosts.show')}
                      </button>
                    )}
                    {changeFailed === post.id && (
                      <span role="alert" className="text-sm text-red-600 dark:text-red-400">
                        {t('myPosts.visibilityError')}
                      </span>
                    )}
                  </div>
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
                className={secondaryButton}
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
