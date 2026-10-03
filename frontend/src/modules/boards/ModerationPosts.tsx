/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { API_BASE, categoryPath, errorDetail, fetchJson, postJson, type AdminPost, type Page } from './api'
import ReasonForm from './ReasonForm'

interface Filters {
  q: string
  category: string
  status: 'published' | 'blocked' | 'removed' | 'all'
  minScore: string
  sort: 'new' | 'score'
}

const INITIAL: Filters = { q: '', category: '', status: 'published', minScore: '', sort: 'new' }

function query(filters: Filters, offset: number): string {
  const params = new URLSearchParams({ status: filters.status, sort: filters.sort, offset: String(offset) })
  if (filters.q.trim()) params.set('q', filters.q.trim())
  if (filters.category.trim()) params.set('category', filters.category.trim())
  if (filters.minScore.trim()) params.set('min_score', filters.minScore.trim())
  return params.toString()
}

const field =
  'rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100'

/** The administrators' post finder: filter, read the scores and findings, block a post with a reason. */
export default function ModerationPosts({ onEditRules }: { onEditRules: (slug: string) => void }) {
  const { t } = useTranslation('boards')
  const [draft, setDraft] = useState<Filters>(INITIAL)
  const [applied, setApplied] = useState<Filters>(INITIAL)
  const [items, setItems] = useState<AdminPost[] | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState(false)
  // Rows handed over so far - the next offset, assigned from the page shown.
  const fetched = useRef(0)

  useEffect(() => {
    let cancelled = false
    setItems(null)
    setError(false)
    fetchJson<Page<AdminPost>>(`${API_BASE}/manage/posts?${query(applied, 0)}`)
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
  }, [applied])

  async function loadMore() {
    setLoadingMore(true)
    try {
      const page = await fetchJson<Page<AdminPost>>(`${API_BASE}/manage/posts?${query(applied, fetched.current)}`)
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

  function search(event: FormEvent) {
    event.preventDefault()
    setApplied({ ...draft })
  }

  function replace(updated: AdminPost) {
    setItems((current) => (current ?? []).map((p) => (p.id === updated.id ? updated : p)))
  }

  return (
    <div>
      <form onSubmit={search} className="mb-6 flex flex-wrap items-end gap-3 text-sm">
        <label className="flex flex-col gap-1">
          {t('admin.posts.search')}
          <input value={draft.q} onChange={(e) => setDraft({ ...draft, q: e.target.value })} className={field} />
        </label>
        <label className="flex flex-col gap-1">
          {t('admin.posts.category')}
          <input
            value={draft.category}
            onChange={(e) => setDraft({ ...draft, category: e.target.value })}
            className={`${field} w-44`}
          />
        </label>
        <label className="flex flex-col gap-1">
          {t('admin.posts.status')}
          <select
            value={draft.status}
            onChange={(e) => setDraft({ ...draft, status: e.target.value as Filters['status'] })}
            className={field}
          >
            {(['published', 'blocked', 'removed', 'all'] as const).map((status) => (
              <option key={status} value={status}>
                {t(`admin.status.${status}`)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          {t('admin.posts.minScore')}
          <input
            type="number"
            min={0}
            max={100}
            value={draft.minScore}
            onChange={(e) => setDraft({ ...draft, minScore: e.target.value })}
            className={`${field} w-24`}
          />
        </label>
        <label className="flex flex-col gap-1">
          {t('admin.posts.sort')}
          <select
            value={draft.sort}
            onChange={(e) => setDraft({ ...draft, sort: e.target.value as Filters['sort'] })}
            className={field}
          >
            <option value="new">{t('admin.posts.sortNew')}</option>
            <option value="score">{t('admin.posts.sortScore')}</option>
          </select>
        </label>
        <button type="submit" className="rounded-lg bg-slate-900 px-4 py-1.5 font-medium text-slate-100 dark:bg-slate-100 dark:text-slate-900">
          {t('admin.posts.find')}
        </button>
      </form>

      {error && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{t('admin.error')}</p>}
      {items === null ? (
        !error && <p className="text-slate-500 dark:text-slate-400">{t('common.loading')}</p>
      ) : items.length === 0 ? (
        <p className="rounded-lg border border-dashed border-slate-300 p-8 text-center text-slate-500 dark:border-slate-700 dark:text-slate-400">
          {t('admin.posts.empty')}
        </p>
      ) : (
        <ul className="divide-y divide-slate-200 border-y border-slate-200 dark:divide-slate-800 dark:border-slate-800">
          {items.map((post) => (
            <PostRow key={post.id} post={post} onChange={replace} onEditRules={onEditRules} />
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
    </div>
  )
}

function PostRow({
  post,
  onChange,
  onEditRules,
}: {
  post: AdminPost
  onChange: (post: AdminPost) => void
  onEditRules: (slug: string) => void
}) {
  const { t } = useTranslation('boards')
  const [blocking, setBlocking] = useState(false)
  const [busy, setBusy] = useState(false)
  // What the last action did: a message key, and for a block whether it also blocked the account.
  const [outcome, setOutcome] = useState<{ ok: boolean; key: string; accountBlocked?: boolean } | null>(null)

  async function block(reason: string) {
    try {
      const result = await postJson<{ post: AdminPost; account_blocked: boolean }>(
        `${API_BASE}/manage/posts/${post.id}/block`,
        { reason },
      )
      onChange(result.post)
      setBlocking(false)
      setOutcome({ ok: true, key: 'admin.posts.blocked', accountBlocked: result.account_blocked })
    } catch {
      setOutcome({ ok: false, key: 'admin.error' })
    }
  }

  async function restore() {
    if (busy || !window.confirm(t('admin.posts.confirmRestore'))) return
    setBusy(true)
    try {
      onChange(await postJson<AdminPost>(`${API_BASE}/manage/posts/${post.id}/restore`))
      setOutcome({ ok: true, key: 'admin.posts.restoredDone' })
    } catch (err) {
      // A blocked account comes first: its posts stay down until it is unblocked.
      const authorBlocked = errorDetail(err)?.code === 'author_blocked'
      setOutcome({ ok: false, key: authorBlocked ? 'admin.posts.restoreAuthorBlocked' : 'admin.error' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <li className="py-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="break-words font-bold">{post.title}</h3>
        <span className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
          {t(`admin.status.${post.status}`)}
        </span>
      </div>
      <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
        <Link to={categoryPath(post.category_slug)} className="underline">
          {post.category_title}
        </Link>
        {' · '}
        {new Date(post.created_at).toLocaleString()}
        {' · '}
        {t('admin.posts.scores', { violation: post.violation_score, topic: post.topic_mismatch_score })}
        {' · '}
        {t('post.value')}: {post.value} · {t('post.resonances', { count: post.resonance_count })}
      </p>
      <p className="mt-2 whitespace-pre-wrap break-words text-sm">{post.body}</p>

      {post.findings.length > 0 && (
        <ul className="mt-2 list-disc pl-5 text-xs text-slate-600 dark:text-slate-400">
          {post.findings.map((finding, index) => (
            <li key={`${finding.code}-${index}`}>
              {t(`moderation.finding.${finding.code}`, { defaultValue: t('moderation.finding.unknown') })}
              {finding.matches.length > 0 && <> — {finding.matches.map((m) => `“${m}”`).join(', ')}</>}
            </li>
          ))}
        </ul>
      )}

      {post.moderation_reason && (
        <p className="mt-2 text-sm">
          <strong>{t('admin.posts.reason')}:</strong> {t(`admin.reason.${post.moderation_reason}`, { defaultValue: post.moderation_reason })}
        </p>
      )}

      <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
        {t('admin.posts.author')}: <code>{post.author_id}</code>
        {post.author_blocked && <strong> — {t('admin.posts.authorBlocked')}</strong>}
      </p>
      {post.category_blocked && (
        <p className="mt-1 text-xs">
          <strong>{t('admin.posts.categoryBlocked')}</strong>
        </p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
        {post.status === 'published' && !blocking && (
          <button
            type="button"
            onClick={() => {
              setBlocking(true)
              setOutcome(null)
            }}
            className="rounded border border-slate-300 px-3 py-1 hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
          >
            {t('admin.posts.block')}
          </button>
        )}
        <button type="button" onClick={() => onEditRules(post.category_slug)} className="underline underline-offset-4 hover:no-underline">
          {t('admin.posts.editRules')}
        </button>
        {post.status !== 'published' && (
          <button
            type="button"
            onClick={restore}
            disabled={busy}
            className="rounded border border-slate-300 px-3 py-1 hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:hover:bg-slate-800"
          >
            {t('admin.posts.restore')}
          </button>
        )}
        {outcome?.ok && (
          <span role="status">
            {t(outcome.key)}
            {outcome.accountBlocked && <strong> {t('admin.posts.accountBlocked')}</strong>}
          </span>
        )}
        {outcome && !outcome.ok && <span role="alert" className="text-red-600 dark:text-red-400">{t(outcome.key)}</span>}
      </div>

      {blocking && (
        <ReasonForm
          id={`reason-${post.id}`}
          label={t('admin.posts.reasonLabel')}
          hint={t('admin.posts.reasonHint')}
          submitLabel={t('admin.posts.confirmBlock')}
          onSubmit={block}
          onCancel={() => setBlocking(false)}
        />
      )}
    </li>
  )
}
