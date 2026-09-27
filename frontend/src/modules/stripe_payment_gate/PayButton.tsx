/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { CheckoutError, startCheckout } from './checkout'

interface PayButtonProps {
  /** Key of a purpose registered on the backend. */
  purpose: string
  /** Passed to that purpose's resolve() - never a price. */
  payload?: Record<string, unknown>
  children?: ReactNode
  className?: string
}

/**
 * Drop-in "Pay" button for application code: starts a checkout for the
 * given purpose and shows its own redirecting/error state. Use
 * startCheckout() directly instead when a custom control is needed.
 */
export default function PayButton({ purpose, payload, children, className }: PayButtonProps) {
  const { t } = useTranslation('stripe_payment_gate')
  const [redirecting, setRedirecting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleClick() {
    setRedirecting(true)
    setError(null)
    try {
      await startCheckout(purpose, payload)
    } catch (e) {
      setError(e instanceof CheckoutError && e.status === 401 ? t('button.signInRequired') : t('button.error'))
      setRedirecting(false)
    }
  }

  return (
    <div className="inline-flex flex-col gap-2">
      <button
        type="button"
        onClick={handleClick}
        disabled={redirecting}
        className={
          className ??
          'rounded-lg bg-slate-900 px-4 py-2 font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900'
        }
      >
        {redirecting ? t('button.redirecting') : (children ?? t('button.pay'))}
      </button>
      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
    </div>
  )
}
