/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useState } from 'react'
import { Trans, useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import PayButton from '../stripe_payment_gate/PayButton'
import { POST_BOOST, RULES_PATH, formatUsd, usePaymentsInfo } from './api'

/**
 * Pay to raise the value of one of your own posts: a whole number of US
 * dollars, shown as the points it buys, then the gateway's pay button. The
 * payer chooses the amount, but the backend re-checks it (range, whole
 * dollars, that the post is theirs and still published) and the value only
 * rises once Stripe has confirmed the payment. The button carries the
 * consent to immediate performance, which the backend insists on.
 * Renders nothing where payments are not switched on.
 */
export default function BoostPanel({
  post,
  intro,
  onClose,
}: {
  post: { id: string; title: string }
  /** Shown above the form - e.g. "your post was published". */
  intro?: string
  onClose: () => void
}) {
  const { t, i18n } = useTranslation('boards')
  const info = usePaymentsInfo()
  const [amount, setAmount] = useState('5')

  if (!info?.enabled) return null

  const dollars = Number(amount)
  const valid = amount.trim() !== '' && Number.isInteger(dollars) && dollars >= info.min_amount_usd && dollars <= info.max_amount_usd
  const label = t('boost.pay', { amount: valid ? formatUsd(dollars * 100, i18n.language) : '' }).trim()

  return (
    <section aria-label={t('boost.heading')} className="mb-8 space-y-3 rounded-lg border border-slate-300 p-4 text-sm dark:border-slate-700">
      {intro && <p className="font-medium">{intro}</p>}
      <h3 className="font-semibold">{t('boost.heading')}</h3>
      <p className="text-slate-600 dark:text-slate-400">{t('boost.explain', { points: info.points_per_usd })}</p>

      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1">
          {t('boost.amount', { min: info.min_amount_usd, max: info.max_amount_usd })}
          <input
            type="number"
            inputMode="numeric"
            min={info.min_amount_usd}
            max={info.max_amount_usd}
            step={1}
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="w-32 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          />
        </label>
        <p aria-live="polite" className="pb-2 font-medium">
          {valid ? t('boost.points', { points: dollars * info.points_per_usd }) : t('boost.invalid', { min: info.min_amount_usd, max: info.max_amount_usd })}
        </p>
      </div>

      <p className="text-xs text-slate-500 dark:text-slate-400">
        <Trans
          t={t}
          i18nKey="boost.noRefund"
          components={{ rules: <Link to={RULES_PATH} className="underline underline-offset-4 hover:no-underline" /> }}
        />
      </p>

      <div className="flex flex-wrap items-start gap-3">
        {valid ? (
          // The button appears only for a valid amount; changing the amount
          // remounts it, so the consent checkbox starts unticked again.
          <PayButton key={dollars} purpose={POST_BOOST} payload={{ post_id: post.id, amount_usd: dollars }} digitalContent>
            {label}
          </PayButton>
        ) : (
          <button type="button" disabled className="rounded-lg bg-slate-900 px-4 py-2 font-medium text-slate-100 opacity-50 dark:bg-slate-100 dark:text-slate-900">
            {t('boost.payDisabled')}
          </button>
        )}
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg border border-slate-300 px-4 py-2 hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
        >
          {t('boost.close')}
        </button>
      </div>
    </section>
  )
}
