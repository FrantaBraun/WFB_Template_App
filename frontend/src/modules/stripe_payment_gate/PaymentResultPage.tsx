/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../api/client'
import usePageMeta from '../../hooks/usePageMeta'
import { API_BASE, formatAmount, type Payment } from './checkout'

const POLL_INTERVAL_MS = 2000
const MAX_POLLS = 15

type LoadState = 'loading' | 'ready' | 'notFound' | 'error'

/**
 * Where Stripe returns the payer (success_url / cancel_url, both carrying
 * ?payment_id=...; cancel adds &canceled=1). Stripe's redirect can beat
 * its own webhook, so a still-pending payment is polled for a while - each
 * poll also makes the backend re-check the session with Stripe directly.
 * A canceled return leaves the payment pending on Stripe's side until the
 * session expires, so "canceled" is shown from the URL flag rather than
 * from the stored status.
 */
export default function PaymentResultPage() {
  const { t, i18n } = useTranslation('stripe_payment_gate')
  usePageMeta({ title: t('result.title') })
  const [params] = useSearchParams()
  const paymentId = params.get('payment_id')
  const canceled = params.get('canceled') === '1'

  const [payment, setPayment] = useState<Payment | null>(null)
  const [loadState, setLoadState] = useState<LoadState>(paymentId ? 'loading' : 'notFound')
  const [polls, setPolls] = useState(0)

  const fetchPayment = useCallback(async () => {
    if (!paymentId) return
    try {
      const resp = await apiFetch(`${API_BASE}/payments/${encodeURIComponent(paymentId)}`)
      if (resp.status === 404 || resp.status === 422) {
        setLoadState('notFound')
        return
      }
      if (!resp.ok) throw new Error()
      setPayment(await resp.json())
      setLoadState('ready')
    } catch {
      setLoadState('error')
    }
  }, [paymentId])

  useEffect(() => {
    fetchPayment()
  }, [fetchPayment])

  const waiting = !canceled && payment?.status === 'pending' && polls < MAX_POLLS
  useEffect(() => {
    if (!waiting) return
    const timer = window.setTimeout(() => {
      setPolls((n) => n + 1)
      fetchPayment()
    }, POLL_INTERVAL_MS)
    return () => window.clearTimeout(timer)
  }, [waiting, polls, fetchPayment])

  function retry() {
    setPolls(0)
    fetchPayment()
  }

  let heading: string
  let message: string
  let tone: 'success' | 'neutral' | 'error' = 'neutral'
  if (loadState === 'loading') {
    heading = t('result.loading')
    message = ''
  } else if (loadState === 'notFound') {
    heading = t('result.notFoundTitle')
    message = t('result.notFoundMessage')
    tone = 'error'
  } else if (loadState === 'error' || !payment) {
    heading = t('result.errorTitle')
    message = t('result.errorMessage')
    tone = 'error'
  } else if (payment.status === 'paid') {
    heading = t('result.paidTitle')
    message = t('result.paidMessage')
    tone = 'success'
  } else if (payment.status === 'failed') {
    heading = t('result.failedTitle')
    message = t('result.failedMessage')
    tone = 'error'
  } else if (payment.status === 'expired') {
    heading = t('result.expiredTitle')
    message = t('result.expiredMessage')
    tone = 'error'
  } else if (canceled) {
    heading = t('result.canceledTitle')
    message = t('result.canceledMessage')
  } else if (waiting) {
    heading = t('result.pendingTitle')
    message = t('result.pendingMessage')
  } else {
    heading = t('result.stillPendingTitle')
    message = t('result.stillPendingMessage')
  }

  const toneClass = {
    success: 'border-emerald-200 bg-emerald-50 dark:border-emerald-900 dark:bg-emerald-950',
    neutral: 'border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900',
    error: 'border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950',
  }[tone]

  const continuePath = payment?.status === 'paid' && payment.return_path ? payment.return_path : '/'
  const showRetry = loadState === 'error' || (payment?.status === 'pending' && !canceled && !waiting)

  return (
    <div className="mx-auto max-w-lg px-6 py-16 text-slate-900 dark:text-slate-100">
      <div className={`space-y-4 rounded-2xl border p-6 ${toneClass}`}>
        <h1 className="text-2xl font-semibold tracking-tight">{heading}</h1>
        {message && <p className="text-slate-600 dark:text-slate-400">{message}</p>}

        {payment && (
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
            <dt className="text-slate-500 dark:text-slate-400">{t('result.description')}</dt>
            <dd>{payment.description}</dd>
            <dt className="text-slate-500 dark:text-slate-400">{t('result.amount')}</dt>
            <dd className="font-medium">{formatAmount(payment.amount, payment.currency, i18n.language)}</dd>
          </dl>
        )}

        <div className="flex flex-wrap gap-3 pt-2">
          {showRetry && (
            <button
              type="button"
              onClick={retry}
              className="rounded-lg border border-slate-300 px-4 py-2 font-medium dark:border-slate-700"
            >
              {t('result.retry')}
            </button>
          )}
          {loadState !== 'loading' && !waiting && (
            <Link
              to={continuePath}
              className="rounded-lg bg-slate-900 px-4 py-2 font-medium text-slate-100 dark:bg-slate-100 dark:text-slate-900"
            >
              {payment?.status === 'paid' && payment.return_path ? t('result.continue') : t('result.backHome')}
            </Link>
          )}
        </div>
      </div>
    </div>
  )
}
