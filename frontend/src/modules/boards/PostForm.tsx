/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useLayoutEffect, useRef, useState, type FormEvent } from 'react'
import { Trans, useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import {
  API_BASE,
  RULES_PATH,
  POST_BODY_MAX,
  POST_TITLE_MAX,
  ApiError,
  charCount,
  errorDetail,
  postJson,
  type Assessment,
  type Post,
} from './api'
import AssessmentPanel from './AssessmentPanel'

const EMOJI = ['😀', '😂', '🙂', '😍', '🤔', '😢', '😡', '👍', '👎', '🙏', '💡', '❤️', '🔥', '🎉', '✨', '🤝']

/** A "n / max" counter that turns red once the text is over its limit. */
export function Counter({ count, max }: { count: number; max: number }) {
  const { t } = useTranslation('boards')
  return (
    <span className={count > max ? 'text-red-600 dark:text-red-400' : 'text-slate-500 dark:text-slate-400'}>
      {t('form.counter', { current: count, max })}
    </span>
  )
}

/**
 * The form for a new post: a title and a text, nothing else - text only,
 * with emoji allowed (typed, pasted, or inserted from the row below).
 * Limits are counted like the backend counts them (see charCount), and the
 * textarea has no maxLength: that counts UTF-16 units, so it would cut an
 * emoji-heavy text short of the real limit.
 *
 * Publishing goes through the content check: the draft is checked first and
 * published straight away only when there is nothing to report; otherwise
 * the verdict is shown with its reasons - a warning to edit, a risk to
 * confirm ("publish anyway"), or a refusal. Editing the text dismisses it.
 */
export default function PostForm({ slug, onPosted }: { slug: string; onPosted: (post: Post) => void }) {
  const { t } = useTranslation('boards')
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<{ kind: 'ok' | 'error'; key: string } | null>(null)
  const [review, setReview] = useState<Assessment | null>(null)
  const bodyRef = useRef<HTMLTextAreaElement>(null)
  const caretAfterInsert = useRef<number | null>(null)

  const titleLength = charCount(title)
  const bodyLength = charCount(body)
  const valid = titleLength > 0 && titleLength <= POST_TITLE_MAX && bodyLength > 0 && bodyLength <= POST_BODY_MAX

  function insertEmoji(emoji: string) {
    const field = bodyRef.current
    const start = field?.selectionStart ?? body.length
    const end = field?.selectionEnd ?? body.length
    setBody(body.slice(0, start) + emoji + body.slice(end))
    setReview(null)
    caretAfterInsert.current = start + emoji.length
  }

  // Put the caret after the inserted emoji once React has re-rendered the
  // value (a layout effect, so it doesn't depend on a frame being painted).
  useLayoutEffect(() => {
    const caret = caretAfterInsert.current
    if (caret === null) return
    caretAfterInsert.current = null
    bodyRef.current?.focus()
    bodyRef.current?.setSelectionRange(caret, caret)
  }, [body])

  async function publish(confirmRisk: boolean) {
    const post = await postJson<Post>(`${API_BASE}/categories/${slug}/posts`, { title, body, confirm_risk: confirmRisk })
    setTitle('')
    setBody('')
    setReview(null)
    setMessage({ kind: 'ok', key: 'form.published' })
    onPosted(post)
  }

  function explain(err: unknown) {
    const detail = errorDetail(err)
    if (detail?.assessment) {
      setReview(detail.assessment) // the server's verdict differs from the draft check's - show the current one
    } else if (detail?.code === 'account_blocked') {
      setMessage({ kind: 'error', key: 'form.accountBlocked' })
    } else {
      setMessage({ kind: 'error', key: err instanceof ApiError && err.status === 422 ? 'form.invalid' : 'form.error' })
    }
  }

  async function run(action: () => Promise<void>) {
    setBusy(true)
    setMessage(null)
    try {
      await action()
    } catch (err) {
      explain(err)
    } finally {
      setBusy(false)
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!valid || busy) return
    setReview(null)
    run(async () => {
      const assessment = await postJson<Assessment>(`${API_BASE}/categories/${slug}/posts/check`, { title, body })
      if (assessment.level === 'ok') await publish(false)
      else setReview(assessment)
    })
  }

  const input =
    'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100'

  return (
    <form onSubmit={submit} className="mb-8 space-y-3">
      <h2 className="text-lg font-semibold">{t('form.heading')}</h2>

      <div>
        <label htmlFor="post-title" className="mb-1 block text-sm font-medium">
          {t('form.title')}
        </label>
        <input
          id="post-title"
          type="text"
          value={title}
          onChange={(e) => {
            setTitle(e.target.value)
            setReview(null)
          }}
          className={input}
        />
        <div className="mt-1 text-right text-xs">
          <Counter count={titleLength} max={POST_TITLE_MAX} />
        </div>
      </div>

      <div>
        <label htmlFor="post-body" className="mb-1 block text-sm font-medium">
          {t('form.body')}
        </label>
        <textarea
          id="post-body"
          ref={bodyRef}
          rows={6}
          value={body}
          onChange={(e) => {
            setBody(e.target.value)
            setReview(null)
          }}
          className={input}
        />
        <div className="mt-1 flex flex-wrap items-center justify-between gap-2 text-xs">
          <div role="group" aria-label={t('form.emoji')} className="flex flex-wrap gap-1">
            {EMOJI.map((emoji) => (
              <button
                key={emoji}
                type="button"
                onClick={() => insertEmoji(emoji)}
                className="rounded px-1.5 py-0.5 text-base hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                {emoji}
              </button>
            ))}
          </div>
          <Counter count={bodyLength} max={POST_BODY_MAX} />
        </div>
      </div>

      {review && (
        <AssessmentPanel assessment={review} subject="post">
          {review.level !== 'blocked' && (
            <button
              type="button"
              disabled={busy}
              onClick={() => run(() => publish(review.level === 'risk'))}
              className="rounded-lg bg-slate-900 px-4 py-2 font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
            >
              {busy ? t('form.publishing') : t('moderation.publishAnyway')}
            </button>
          )}
          <button
            type="button"
            onClick={() => {
              setReview(null)
              bodyRef.current?.focus()
            }}
            className="rounded-lg border border-slate-300 px-4 py-2 hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
          >
            {t('moderation.edit')}
          </button>
        </AssessmentPanel>
      )}

      <p className="text-xs text-slate-500 dark:text-slate-400">
        <Trans
          t={t}
          i18nKey="form.rulesNotice"
          components={{ rules: <Link to={RULES_PATH} className="underline underline-offset-4 hover:no-underline" /> }}
        />
      </p>

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={!valid || busy}
          className="rounded-lg bg-slate-900 px-4 py-2 font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
        >
          {busy ? t('form.checking') : t('form.publish')}
        </button>
        {message && (
          <span
            role="status"
            className={message.kind === 'error' ? 'text-sm text-red-600 dark:text-red-400' : 'text-sm text-slate-600 dark:text-slate-400'}
          >
            {t(message.key)}
          </span>
        )}
      </div>
    </form>
  )
}
