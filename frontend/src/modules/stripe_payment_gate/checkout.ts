/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { apiFetch } from '../../api/client'

export const API_BASE = '/api/modules/stripe_payment_gate'

export type PaymentStatus = 'pending' | 'paid' | 'failed' | 'expired'

export interface Payment {
  id: string
  purpose: string
  reference: string | null
  /** In the currency's minor unit (haléře, cents) - format with formatAmount(). */
  amount: number
  currency: string
  description: string
  status: PaymentStatus
  return_path: string | null
  created_at: string
  paid_at: string | null
}

export class CheckoutError extends Error {
  status: number
  constructor(status: number, detail: string) {
    super(detail)
    this.status = status
  }
}

/**
 * Starts a payment for a purpose registered on the backend (see
 * app/modules/stripe_payment_gate/purposes.py) and sends the browser to
 * Stripe's hosted checkout page. `payload` is whatever that purpose's
 * resolve() expects (e.g. `{ order_id }`) - never a price; the backend
 * computes the amount itself. After paying (or canceling), Stripe returns
 * the payer to this module's /platba/vysledek page.
 */
export async function startCheckout(purpose: string, payload: Record<string, unknown> = {}): Promise<never> {
  const resp = await apiFetch(`${API_BASE}/checkout`, {
    method: 'POST',
    body: JSON.stringify({ purpose, payload }),
  })
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}))
    throw new CheckoutError(resp.status, typeof body.detail === 'string' ? body.detail : '')
  }
  const { checkout_url } = await resp.json()
  window.location.assign(checkout_url)
  // The page is navigating away; never resolve so callers keep their
  // "redirecting..." state instead of flashing back to idle.
  return new Promise<never>(() => {})
}

/** Formats a minor-unit amount using the currency's own number of decimals (CZK/EUR: 2, JPY: 0). */
export function formatAmount(amount: number, currency: string, locale: string): string {
  const formatter = new Intl.NumberFormat(locale, { style: 'currency', currency: currency.toUpperCase() })
  const decimals = formatter.resolvedOptions().maximumFractionDigits ?? 2
  return formatter.format(amount / 10 ** decimals)
}
