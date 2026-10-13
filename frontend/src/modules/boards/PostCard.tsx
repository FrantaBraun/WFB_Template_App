/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../context/AuthContext'
import { API_BASE, ApiError, formatUsd, postJson, usePaymentsInfo, type Post } from './api'
import BoostPanel from './BoostPanel'
import { accentChip, tierOf } from './styles'

/**
 * One post as an entry in the ranking: its place (a medal for the podium,
 * "#4" below it), a bold title, the text, and its current value as the score.
 * Still no author. `trend` is how many places it has climbed (positive) or
 * lost (negative) among the posts already on the board since the list was
 * last refreshed, 0 when it stayed. A signed-in visitor can resonate once;
 * the server answers with the updated post.
 */
export default function PostCard({
  post,
  rank,
  trend,
  onChange,
}: {
  post: Post
  rank: number
  trend: number
  onChange: (post: Post) => void
}) {
  const { t, i18n } = useTranslation('boards')
  const { user } = useAuth()
  const payments = usePaymentsInfo()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(false)
  const [boosting, setBoosting] = useState(false)
  const tier = tierOf(rank)

  async function resonate() {
    setBusy(true)
    setError(false)
    try {
      onChange(await postJson<Post>(`${API_BASE}/posts/${post.id}/resonance`))
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        // Already counted (another tab, say) - just show it as resonated.
        onChange({ ...post, resonated_by_me: true })
      } else {
        setError(true)
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <article
      className={`flex gap-3 p-4 transition motion-safe:hover:-translate-y-0.5 hover:shadow-md sm:gap-4 sm:p-5 ${tier.card}`}
    >
      <div className="flex w-11 shrink-0 flex-col items-center gap-1.5 text-center sm:w-12">
        {tier.medal ? (
          <span role="img" aria-label={t('post.rank', { rank })} className="text-3xl leading-none sm:text-4xl">
            {tier.medal}
          </span>
        ) : (
          <span
            aria-label={t('post.rank', { rank })}
            className="text-base font-extrabold tabular-nums text-slate-500 dark:text-slate-400 sm:text-lg"
          >
            #{rank}
          </span>
        )}
        {trend !== 0 && (
          <span
            title={t(trend > 0 ? 'post.climbed' : 'post.fell', { count: Math.abs(trend) })}
            className={`rounded-full px-1.5 text-xs font-bold tabular-nums ${
              trend > 0
                ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300'
                : 'bg-rose-100 text-rose-700 dark:bg-rose-500/20 dark:text-rose-300'
            }`}
          >
            {trend > 0 ? '▲' : '▼'} {Math.abs(trend)}
          </span>
        )}
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-3">
          <h3 className={`break-words font-bold leading-snug ${tier.title}`}>{post.title}</h3>
          <div className="shrink-0 text-right leading-none">
            <span className="block text-[10px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              {t('post.value')}
            </span>
            <span className={`text-2xl font-extrabold tabular-nums sm:text-3xl ${tier.score}`}>
              {post.value.toLocaleString(i18n.language)}
            </span>
          </div>
        </div>

        <p className="mt-2 whitespace-pre-wrap break-words text-slate-700 dark:text-slate-300">{post.body}</p>

        <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-2 text-sm text-slate-600 dark:text-slate-400">
          <button
            type="button"
            onClick={resonate}
            disabled={!user || post.resonated_by_me || busy}
            title={user ? undefined : t('post.loginToResonate')}
            className={
              post.resonated_by_me
                ? 'inline-flex items-center gap-1.5 rounded-full border border-violet-200 bg-violet-50 px-3.5 py-1.5 text-sm font-semibold text-violet-800 dark:border-violet-500/30 dark:bg-violet-500/15 dark:text-violet-200'
                : 'inline-flex items-center gap-1.5 rounded-full bg-violet-600 px-3.5 py-1.5 text-sm font-semibold text-white shadow-sm transition hover:bg-violet-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-500 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-violet-600 dark:hover:bg-violet-500'
            }
          >
            <span aria-hidden="true">{post.resonated_by_me ? '✓' : '✨'}</span>
            {post.resonated_by_me ? t('post.resonated') : t('post.resonate')}
          </button>
          <span>{t('post.resonances', { count: post.resonance_count })}</span>
          {error && <span className="text-red-600 dark:text-red-400">{t('post.resonateError')}</span>}
          {post.mine && (
            <span className={accentChip}>
              {t('post.yours')}
              {post.paid_cents ? ` · ${t('post.paidByYou', { amount: formatUsd(post.paid_cents, i18n.language) })}` : ''}
            </span>
          )}
          {post.mine && payments?.enabled && !boosting && (
            <button
              type="button"
              onClick={() => setBoosting(true)}
              className="inline-flex items-center rounded-full border border-slate-300 px-3 py-1 text-sm font-medium transition hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
            >
              {t('boost.open')}
            </button>
          )}
        </div>

        {boosting && (
          <div className="mt-4">
            <BoostPanel post={post} onClose={() => setBoosting(false)} />
          </div>
        )}
      </div>
    </article>
  )
}
