/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { API_BASE, categoryPath, fetchJson, postJson, type AdminCategory, type Page } from './api'
import ReasonForm from './ReasonForm'

interface Filters {
  q: string
  status: 'published' | 'blocked' | 'all'
}

const INITIAL: Filters = { q: '', status: 'all' }

function query(filters: Filters, offset: number): string {
  const params = new URLSearchParams({ status: filters.status, offset: String(offset) })
  if (filters.q.trim()) params.set('q', filters.q.trim())
  return params.toString()
}

const field =
  'rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100'

/**
 * Every category, blocked ones included (the public list leaves them out):
 * block one with a reason its creator is sent - the board and everything in
 * it disappears for visitors, nothing is deleted - or restore a blocked one.
 */
export default function ModerationCategories({ onEditRules }: { onEditRules: (slug: string) => void }) {
  const { t } = useTranslation('boards')
  const [draft, setDraft] = useState<Filters>(INITIAL)
  const [applied, setApplied] = useState<Filters>(INITIAL)
  const [items, setItems] = useState<AdminCategory[] | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState(false)
  // Rows handed over so far - the next offset, assigned from the page shown.
  const fetched = useRef(0)

  useEffect(() => {
    let cancelled = false
    setItems(null)
    setError(false)
    fetchJson<Page<AdminCategory>>(`${API_BASE}/manage/categories?${query(applied, 0)}`)
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
      const page = await fetchJson<Page<AdminCategory>>(`${API_BASE}/manage/categories?${query(applied, fetched.current)}`)
      fetched.current += page.items.length
      setItems((current) => {
        const seen = new Set((current ?? []).map((c) => c.id))
        return [...(current ?? []), ...page.items.filter((c) => !seen.has(c.id))]
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
    setApplied(draft)
  }

  function replace(updated: AdminCategory) {
    setItems((current) => (current ?? []).map((c) => (c.id === updated.id ? updated : c)))
  }

  return (
    <div>
      <p className="mb-4 text-sm text-slate-600 dark:text-slate-400">{t('admin.categories.explain')}</p>
      <form onSubmit={search} className="mb-6 flex flex-wrap items-end gap-3 text-sm">
        <label className="flex flex-col gap-1">
          {t('admin.categories.search')}
          <input value={draft.q} onChange={(e) => setDraft({ ...draft, q: e.target.value })} className={`${field} w-56`} />
        </label>
        <label className="flex flex-col gap-1">
          {t('admin.posts.status')}
          <select
            value={draft.status}
            onChange={(e) => setDraft({ ...draft, status: e.target.value as Filters['status'] })}
            className={field}
          >
            {(['all', 'published', 'blocked'] as const).map((status) => (
              <option key={status} value={status}>
                {t(`admin.status.${status}`)}
              </option>
            ))}
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
          {t('admin.categories.empty')}
        </p>
      ) : (
        <ul className="divide-y divide-slate-200 border-y border-slate-200 dark:divide-slate-800 dark:border-slate-800">
          {items.map((category) => (
            <CategoryRow key={category.id} category={category} onChange={replace} onEditRules={onEditRules} />
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

function CategoryRow({
  category,
  onChange,
  onEditRules,
}: {
  category: AdminCategory
  onChange: (category: AdminCategory) => void
  onEditRules: (slug: string) => void
}) {
  const { t } = useTranslation('boards')
  const [blocking, setBlocking] = useState(false)
  const [busy, setBusy] = useState(false)
  const [outcome, setOutcome] = useState<{ ok: boolean; key: string } | null>(null)
  const base = `${API_BASE}/manage/categories/${encodeURIComponent(category.slug)}`
  const blocked = category.status === 'blocked'

  async function block(reason: string) {
    try {
      onChange(await postJson<AdminCategory>(`${base}/block`, { reason }))
      setBlocking(false)
      setOutcome({ ok: true, key: 'admin.categories.blockedDone' })
    } catch {
      setOutcome({ ok: false, key: 'admin.error' })
    }
  }

  async function restore() {
    if (busy || !window.confirm(t('admin.categories.confirmRestore'))) return
    setBusy(true)
    try {
      onChange(await postJson<AdminCategory>(`${base}/restore`))
      setOutcome({ ok: true, key: 'admin.categories.restoredDone' })
    } catch {
      setOutcome({ ok: false, key: 'admin.error' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <li className="py-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="break-words font-bold">
          {blocked ? (
            category.title
          ) : (
            <Link to={categoryPath(category.slug)} className="underline underline-offset-4 hover:no-underline">
              {category.title}
            </Link>
          )}
        </h3>
        <span className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">{t(`admin.status.${category.status}`)}</span>
      </div>
      <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
        <code>{category.slug}</code>
        {' · '}
        {t('list.posts', { count: category.post_count })}
        {' · '}
        {t('admin.categories.created', { date: new Date(category.created_at).toLocaleString(), score: category.violation_score })}
      </p>
      <p className="mt-2 whitespace-pre-wrap break-words text-sm">{category.description}</p>
      <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
        {t('admin.categories.creator')}: <code>{category.created_by_id}</code>
      </p>

      {blocked && category.moderation_reason && (
        <p className="mt-2 text-sm">
          <strong>{t('admin.posts.reason')}:</strong> {category.moderation_reason}
          {category.moderated_at && (
            <span className="text-xs text-slate-500 dark:text-slate-400"> · {new Date(category.moderated_at).toLocaleString()}</span>
          )}
        </p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
        {!blocked && !blocking && (
          <button
            type="button"
            onClick={() => {
              setBlocking(true)
              setOutcome(null)
            }}
            className="rounded border border-slate-300 px-3 py-1 hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
          >
            {t('admin.categories.block')}
          </button>
        )}
        {blocked && (
          <button
            type="button"
            onClick={restore}
            disabled={busy}
            className="rounded border border-slate-300 px-3 py-1 hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:hover:bg-slate-800"
          >
            {t('admin.categories.restore')}
          </button>
        )}
        <button type="button" onClick={() => onEditRules(category.slug)} className="underline underline-offset-4 hover:no-underline">
          {t('admin.posts.editRules')}
        </button>
        {outcome && (
          <span role={outcome.ok ? 'status' : 'alert'} className={outcome.ok ? '' : 'text-red-600 dark:text-red-400'}>
            {t(outcome.key)}
          </span>
        )}
      </div>

      {blocking && (
        <ReasonForm
          id={`category-reason-${category.id}`}
          label={t('admin.categories.reasonLabel')}
          hint={t('admin.categories.reasonHint')}
          submitLabel={t('admin.categories.confirmBlock')}
          onSubmit={block}
          onCancel={() => setBlocking(false)}
        />
      )}
    </li>
  )
}
