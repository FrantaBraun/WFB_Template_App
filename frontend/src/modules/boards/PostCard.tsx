/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../context/AuthContext'
import { API_BASE, ApiError, postJson, type Post } from './api'

/**
 * One post, deliberately plain: a bold title, the text, then its current
 * value and how many resonated. No author and no colors. A signed-in
 * visitor can resonate once; the server answers with the updated post.
 */
export default function PostCard({ post, onChange }: { post: Post; onChange: (post: Post) => void }) {
  const { t, i18n } = useTranslation('boards')
  const { user } = useAuth()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(false)

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
    <article className="py-5">
      <h3 className="break-words font-bold">{post.title}</h3>
      <p className="mt-2 whitespace-pre-wrap break-words">{post.body}</p>
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-600 dark:text-slate-400">
        <span>
          {t('post.value')}: <strong>{post.value.toLocaleString(i18n.language)}</strong>
        </span>
        <span>{t('post.resonances', { count: post.resonance_count })}</span>
        <button
          type="button"
          onClick={resonate}
          disabled={!user || post.resonated_by_me || busy}
          title={user ? undefined : t('post.loginToResonate')}
          className="rounded border border-slate-300 px-2 py-0.5 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:hover:bg-slate-800"
        >
          {post.resonated_by_me ? t('post.resonated') : t('post.resonate')}
        </button>
        {error && <span className="text-red-600 dark:text-red-400">{t('post.resonateError')}</span>}
      </div>
    </article>
  )
}
