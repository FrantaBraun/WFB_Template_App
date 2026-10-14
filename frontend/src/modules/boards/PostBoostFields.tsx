/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { Trans, useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { RULES_PATH, type PaymentsInfo } from './api'

/** What the author chose to pay with a new post: nothing, something the server would refuse, or a whole number of dollars. */
export type Boost = { kind: 'none' } | { kind: 'invalid' } | { kind: 'ok'; dollars: number }

/**
 * Reads the amount field. An empty field is "no payment" (the common case);
 * anything but a whole number inside the configured range is `invalid` - the
 * backend checks the same again, this only keeps the form from sending it.
 */
export function parseBoost(amount: string, info: PaymentsInfo | null): Boost {
  if (!info?.enabled || amount.trim() === '') return { kind: 'none' }
  const dollars = Number(amount)
  if (!Number.isInteger(dollars) || dollars < info.min_amount_usd || dollars > info.max_amount_usd) return { kind: 'invalid' }
  return { kind: 'ok', dollars }
}

const PRESETS = [5, 10, 25]

/**
 * The optional "raise its value right away" part of the new-post form: an
 * amount in whole US dollars, with the points it buys, and - once there is an
 * amount - the express request for immediate performance the backend insists
 * on (it ends the 14-day withdrawal right) and the no-refund notice. The
 * terms notice that goes with the submit button is the form's own. Renders
 * nothing where payments are not switched on.
 */
export default function PostBoostFields({
  info,
  amount,
  onAmount,
  waiver,
  onWaiver,
  disabled,
}: {
  info: PaymentsInfo
  amount: string
  onAmount: (amount: string) => void
  waiver: boolean
  onWaiver: (waiver: boolean) => void
  disabled: boolean
}) {
  const { t } = useTranslation('boards')
  const { t: tGate } = useTranslation('stripe_payment_gate')
  const boost = parseBoost(amount, info)
  const presets = PRESETS.filter((dollars) => dollars >= info.min_amount_usd && dollars <= info.max_amount_usd)

  return (
    <fieldset
      disabled={disabled}
      className="space-y-3 rounded-2xl border border-violet-200 bg-violet-50/60 p-4 text-sm dark:border-violet-500/30 dark:bg-violet-500/10"
    >
      <legend className="px-1 font-semibold">
        <span aria-hidden="true">🏆</span> {t('form.boostHeading')}
      </legend>
      <p className="text-slate-600 dark:text-slate-400">
        {t('boost.explain', { points: info.points_per_usd })} {t('form.boostHint')}
      </p>

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
            placeholder={t('form.boostNone')}
            onChange={(e) => onAmount(e.target.value)}
            className="w-32 rounded-xl border border-slate-300 bg-white px-3 py-1.5 text-slate-900 focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-500/30 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          />
        </label>
        <div role="group" aria-label={t('form.boostPresets')} className="flex gap-2 pb-0.5">
          {presets.map((dollars) => (
            <button
              key={dollars}
              type="button"
              aria-pressed={boost.kind === 'ok' && boost.dollars === dollars}
              onClick={() => onAmount(String(dollars))}
              className="rounded-full border border-slate-300 px-3 py-1 font-medium transition hover:bg-white aria-pressed:border-violet-500 aria-pressed:bg-violet-600 aria-pressed:text-white dark:border-slate-600 dark:hover:bg-slate-800"
            >
              ${dollars}
            </button>
          ))}
        </div>
        <p aria-live="polite" className="pb-2 font-medium">
          {boost.kind === 'ok'
            ? t('boost.points', { points: boost.dollars * info.points_per_usd })
            : boost.kind === 'invalid'
              ? t('boost.invalid', { min: info.min_amount_usd, max: info.max_amount_usd })
              : ''}
        </p>
      </div>

      {boost.kind === 'ok' && (
        <>
          <label className="flex items-start gap-2 text-slate-700 dark:text-slate-300">
            <input type="checkbox" checked={waiver} onChange={(e) => onWaiver(e.target.checked)} className="mt-0.5" />
            <span>{tGate('button.digitalContentWaiver')}</span>
          </label>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            <Trans
              t={t}
              i18nKey="boost.noRefund"
              components={{ rules: <Link to={RULES_PATH} className="underline underline-offset-4 hover:no-underline" /> }}
            />
          </p>
        </>
      )}
    </fieldset>
  )
}
