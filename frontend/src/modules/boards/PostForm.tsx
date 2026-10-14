/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useLayoutEffect, useRef, useState, type FormEvent } from 'react'
import { Trans, useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { startCheckout } from '../stripe_payment_gate/checkout'
import { LEGAL_PATHS } from '../stripe_payment_gate/LegalPages'
import {
  API_BASE,
  POST_BOOST,
  RULES_PATH,
  POST_BODY_MAX,
  POST_TITLE_MAX,
  ApiError,
  charCount,
  errorDetail,
  formatUsd,
  postJson,
  usePaymentsInfo,
  type Assessment,
  type Post,
} from './api'
import AssessmentPanel from './AssessmentPanel'
import PostBoostFields, { parseBoost } from './PostBoostFields'
import { card, primaryButton, secondaryButton } from './styles'

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
 *
 * Where payments are on, the form can also take an amount to pay with the
 * post (PostBoostFields): the post is checked and published first - the
 * content check always comes before any payment - and the author is then
 * sent straight to Stripe to pay for it. Publishing does not depend on the
 * payment: if it is abandoned or cannot be started, the post stays
 * published and its value can be raised later.
 */
export default function PostForm({ slug, onPosted }: { slug: string; onPosted: (post: Post) => void }) {
  const { t, i18n } = useTranslation('boards')
  const { t: tGate } = useTranslation('stripe_payment_gate')
  const payments = usePaymentsInfo()
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<{ kind: 'ok' | 'error'; key: string } | null>(null)
  const [review, setReview] = useState<Assessment | null>(null)
  // What to pay with the post, as typed (empty = nothing), and the consent to immediate performance that paying needs.
  const [amount, setAmount] = useState('')
  const [waiver, setWaiver] = useState(false)
  const [redirecting, setRedirecting] = useState(false)
  const bodyRef = useRef<HTMLTextAreaElement>(null)
  const caretAfterInsert = useRef<number | null>(null)

  const titleLength = charCount(title)
  const bodyLength = charCount(body)
  const valid = titleLength > 0 && titleLength <= POST_TITLE_MAX && bodyLength > 0 && bodyLength <= POST_BODY_MAX
  const boost = parseBoost(amount, payments)
  // A payment needs a valid amount and the consent; without an amount the form is the plain one.
  const canSubmit = valid && boost.kind !== 'invalid' && (boost.kind !== 'ok' || waiver)
  const payLabel = boost.kind === 'ok' ? formatUsd(boost.dollars * 100, i18n.language) : ''

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
    const paying = boost.kind === 'ok' ? boost.dollars : null
    setTitle('')
    setBody('')
    setReview(null)
    if (paying === null) {
      setMessage({ kind: 'ok', key: 'form.published' })
      onPosted(post)
      return
    }

    // The post is out; now the payment. startCheckout never resolves when it works
    // (the browser is on its way to Stripe), so this form stays busy until the page goes.
    setMessage({ kind: 'ok', key: 'form.publishedPaying' })
    setRedirecting(true)
    try {
      await startCheckout(
        POST_BOOST,
        { post_id: post.id, amount_usd: paying, language: i18n.resolvedLanguage ?? i18n.language },
        ['terms', 'digital_content_waiver'],
      )
    } catch {
      // Published all the same: say so, and let the author try again from the offer to raise its value.
      setRedirecting(false)
      setAmount('')
      setWaiver(false)
      setMessage({ kind: 'error', key: 'form.paymentNotStarted' })
      onPosted(post)
    }
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
    if (!canSubmit || busy) return
    setReview(null)
    run(async () => {
      const assessment = await postJson<Assessment>(`${API_BASE}/categories/${slug}/posts/check`, { title, body })
      if (assessment.level === 'ok') await publish(false)
      else setReview(assessment)
    })
  }

  const input =
    'w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-slate-900 focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-500/30 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100'

  return (
    <form onSubmit={submit} className={`mb-8 space-y-3 p-5 ${card}`} id="post-form">
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

      {payments?.enabled && (
        <PostBoostFields
          info={payments}
          amount={amount}
          onAmount={(next) => {
            setAmount(next)
            setReview(null)
          }}
          waiver={waiver}
          onWaiver={setWaiver}
          disabled={busy}
        />
      )}

      {review && (
        <AssessmentPanel assessment={review} subject="post">
          {review.level !== 'blocked' && (
            <button
              type="button"
              disabled={busy || !canSubmit}
              onClick={() => run(() => publish(review.level === 'risk'))}
              className={primaryButton}
            >
              {redirecting
                ? tGate('button.redirecting')
                : busy
                  ? t('form.publishing')
                  : boost.kind === 'ok'
                    ? t('moderation.publishAndPayAnyway', { amount: payLabel })
                    : t('moderation.publishAnyway')}
            </button>
          )}
          <button
            type="button"
            onClick={() => {
              setReview(null)
              bodyRef.current?.focus()
            }}
            className={secondaryButton}
          >
            {t('moderation.edit')}
          </button>
        </AssessmentPanel>
      )}

      <p className="text-xs text-slate-500 dark:text-slate-400">
        {boost.kind === 'ok' ? (
          // The submit button now also orders and pays: show the terms notice that goes with a payment button.
          <Trans
            t={tGate}
            i18nKey="button.termsNotice"
            components={{
              terms: <Link to={LEGAL_PATHS.terms} className="underline underline-offset-4 hover:no-underline" />,
              privacy: <Link to={LEGAL_PATHS.privacy} className="underline underline-offset-4 hover:no-underline" />,
            }}
          />
        ) : (
          <Trans
            t={t}
            i18nKey="form.rulesNotice"
            components={{ rules: <Link to={RULES_PATH} className="underline underline-offset-4 hover:no-underline" /> }}
          />
        )}
      </p>

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={!canSubmit || busy}
          className={primaryButton}
        >
          {redirecting
            ? tGate('button.redirecting')
            : busy
              ? t('form.checking')
              : boost.kind === 'ok'
                ? t('form.publishAndPay', { amount: payLabel })
                : t('form.publish')}
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
