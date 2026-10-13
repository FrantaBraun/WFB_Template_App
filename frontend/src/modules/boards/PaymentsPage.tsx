/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useRef, useState } from 'react'
import { Trans, useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import usePageMeta from '../../hooks/usePageMeta'
import {
  API_BASE,
  MY_POSTS_PATH,
  RECEIPTS_PATH,
  RULES_PATH,
  fetchJson,
  formatMoney,
  type Payment,
  type PaymentHistory,
  type PaymentSummary,
} from './api'
import { card, secondaryButton } from './styles'

/** The colour of a payment's status label. */
const STATUS_CHIP = {
  paid: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-300',
  pending: 'bg-amber-100 text-amber-800 dark:bg-amber-500/20 dark:text-amber-200',
  failed: 'bg-rose-100 text-rose-800 dark:bg-rose-500/20 dark:text-rose-300',
  expired: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300',
}

/** What the post became, as a key under `payments.postState`; null when there is nothing to add. */
function postStateKey(payment: Payment): string | null {
  if (payment.post_status === null) return 'gone'
  if (payment.post_status !== 'published') return payment.post_status
  return payment.category_blocked ? 'categoryBlocked' : null
}

/**
 * /my-payments - the signed-in user's payment overview: the total they have
 * paid, then every payment they started for their posts, newest first,
 * whatever became of it (only a completed one counts as paid), with what the
 * post is now and a link to the document issued for it. Posts are anonymous,
 * so this is also where an author sees which of their posts a payment went to.
 */
export default function PaymentsPage() {
  const { t, i18n } = useTranslation('boards')
  const { user, loading } = useAuth()
  const [summary, setSummary] = useState<PaymentSummary | null>(null)
  const [items, setItems] = useState<Payment[] | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState(false)
  // Rows handed over so far - the next offset, assigned from the page shown.
  const fetched = useRef(0)
  const language = i18n.resolvedLanguage ?? i18n.language

  usePageMeta({ title: t('payments.title') })

  useEffect(() => {
    if (loading || !user) return
    let cancelled = false
    fetchJson<PaymentHistory>(`${API_BASE}/me/payments?offset=0`)
      .then((page) => {
        if (cancelled) return
        fetched.current = page.items.length
        setSummary(page.summary)
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
      const page = await fetchJson<PaymentHistory>(`${API_BASE}/me/payments?offset=${fetched.current}`)
      fetched.current += page.items.length
      setSummary(page.summary)
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
        <Link to={MY_POSTS_PATH} className="underline underline-offset-4 hover:no-underline">
          ← {t('myPosts.title')}
        </Link>
      </p>
      <h1 className="mb-6 text-3xl font-extrabold tracking-tight">{t('payments.title')}</h1>

      {loading ? (
        <p className="text-slate-500 dark:text-slate-400">{t('common.loading')}</p>
      ) : !user ? (
        <p>
          <Link to="/login" className="font-medium underline underline-offset-4 hover:no-underline">
            {t('payments.loginRequired')}
          </Link>
        </p>
      ) : (
        <>
          <p className="mb-6 text-sm text-slate-600 dark:text-slate-400">
            {t('payments.explain')}{' '}
            <Link to={RECEIPTS_PATH} className="underline underline-offset-4 hover:no-underline">
              {t('payments.receipts')}
            </Link>
          </p>
          {error && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{t('payments.error')}</p>}

          {summary && (
            <p className="mb-6 rounded-2xl border border-amber-300 bg-gradient-to-br from-amber-50 via-white to-white p-5 shadow-sm dark:border-amber-400/40 dark:from-amber-400/10 dark:via-slate-900/70 dark:to-slate-900/70">
              <span className="block text-sm text-slate-600 dark:text-slate-400">{t('payments.total')}</span>
              <strong className="text-3xl font-extrabold tabular-nums text-amber-600 dark:text-amber-300">{formatMoney(summary.paid_cents, summary.currency, language)}</strong>
              <span className="ml-2 text-sm text-slate-600 dark:text-slate-400">
                {t('payments.count', { count: summary.paid_count })}
              </span>
            </p>
          )}

          {items === null ? (
            !error && <p className="text-slate-500 dark:text-slate-400">{t('common.loading')}</p>
          ) : items.length === 0 ? (
            <p className="rounded-2xl border border-dashed border-slate-300 p-8 text-center text-slate-500 dark:border-slate-700 dark:text-slate-400">
              {t('payments.empty')}
            </p>
          ) : (
            <>
              <ul className="space-y-4">
                {items.map((payment) => {
                  const state = postStateKey(payment)
                  return (
                    <li key={payment.id} className={`p-4 text-sm sm:p-5 ${card}`}>
                      <div className="flex flex-wrap items-baseline justify-between gap-2">
                        <p className="min-w-0 break-words font-bold">
                          {payment.post_title ?? t('payments.postState.gone')}
                        </p>
                        <p className={payment.status === 'paid' ? 'font-bold' : 'text-slate-500 dark:text-slate-400'}>
                          {formatMoney(payment.amount, payment.currency, language)}
                        </p>
                      </div>
                      <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                        {new Date(payment.created_at).toLocaleString(language)}
                        {' · '}
                        <span className={`rounded-full px-2 py-0.5 font-semibold ${STATUS_CHIP[payment.status]}`}>{t(`payments.status.${payment.status}`)}</span>
                        {payment.status === 'paid' && <> · {t('payments.points', { points: payment.points.toLocaleString(language) })}</>}
                      </p>
                      {payment.status === 'pending' && (
                        <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">{t('payments.pendingNote')}</p>
                      )}
                      {state && state !== 'gone' && (
                        <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">{t(`payments.postState.${state}`)}</p>
                      )}
                      {payment.receipt_id && (
                        <p className="mt-1 text-xs">
                          <Link
                            to={`${RECEIPTS_PATH}?receipt=${payment.receipt_id}`}
                            className="underline underline-offset-4 hover:no-underline"
                          >
                            {t('payments.document', { number: payment.receipt_number })}
                          </Link>
                        </p>
                      )}
                    </li>
                  )
                })}
              </ul>
              <p className="mt-4 text-xs text-slate-500 dark:text-slate-400">
                <Trans
                  t={t}
                  i18nKey="payments.noRefund"
                  components={{ rules: <Link to={RULES_PATH} className="underline underline-offset-4 hover:no-underline" /> }}
                />
              </p>
            </>
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
