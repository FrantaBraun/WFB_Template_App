/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useId, useState, type ReactNode } from 'react'
import { Trans, useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { CheckoutError, startCheckout, type Consent } from './checkout'
import { LEGAL_PATHS } from './LegalPages'

interface PayButtonProps {
  /** Key of a purpose registered on the backend. */
  purpose: string
  /** Passed to that purpose's resolve() - never a price. */
  payload?: Record<string, unknown>
  /**
   * Set for digital content delivered right after payment: shows a
   * required checkbox by which the consumer expressly consents to
   * immediate delivery and acknowledges losing the 14-day withdrawal
   * right - without it, that right is not lost (see the module README).
   */
  digitalContent?: boolean
  /** Defaults to "Order and pay" - the label must make clear the order obliges to pay (§ 1826a OZ). */
  children?: ReactNode
  className?: string
}

/**
 * Drop-in pay button for application code: shows the terms/privacy notice
 * next to it, starts a checkout for the given purpose (recording the
 * consents) and shows its own redirecting/error state. Use startCheckout()
 * directly instead when a custom control is needed - it then has to show
 * the same notice itself.
 */
export default function PayButton({ purpose, payload, digitalContent = false, children, className }: PayButtonProps) {
  const { t } = useTranslation('stripe_payment_gate')
  const checkboxId = useId()
  const [waiverChecked, setWaiverChecked] = useState(false)
  const [redirecting, setRedirecting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleClick() {
    setRedirecting(true)
    setError(null)
    const consents: Consent[] = ['terms']
    if (digitalContent) consents.push('digital_content_waiver')
    try {
      await startCheckout(purpose, payload, consents)
    } catch (e) {
      setError(e instanceof CheckoutError && e.status === 401 ? t('button.signInRequired') : t('button.error'))
      setRedirecting(false)
    }
  }

  const linkClass = 'underline hover:text-slate-700 dark:hover:text-slate-200'

  return (
    <div className="inline-flex max-w-md flex-col gap-2">
      {digitalContent && (
        <label htmlFor={checkboxId} className="flex items-start gap-2 text-sm text-slate-700 dark:text-slate-300">
          <input
            id={checkboxId}
            type="checkbox"
            checked={waiverChecked}
            onChange={(e) => setWaiverChecked(e.target.checked)}
            className="mt-0.5"
          />
          <span>{t('button.digitalContentWaiver')}</span>
        </label>
      )}
      <button
        type="button"
        onClick={handleClick}
        disabled={redirecting || (digitalContent && !waiverChecked)}
        className={
          className ??
          'self-start rounded-lg bg-slate-900 px-4 py-2 font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900'
        }
      >
        {redirecting ? t('button.redirecting') : (children ?? t('button.pay'))}
      </button>
      <p className="text-xs text-slate-500 dark:text-slate-400">
        <Trans
          t={t}
          i18nKey="button.termsNotice"
          components={{
            terms: <Link to={LEGAL_PATHS.terms} className={linkClass} />,
            privacy: <Link to={LEGAL_PATHS.privacy} className={linkClass} />,
          }}
        />
      </p>
      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
    </div>
  )
}
