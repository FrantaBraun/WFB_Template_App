/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { API_BASE, fetchJson, type PaymentsStatus } from './api'

/**
 * Tells an administrator that payments are off, and why. Without it the
 * payment options are simply missing for everybody - nothing on the page says
 * a setting (the gateway module, the Stripe keys, the provider's details) is
 * behind it. Shows nothing while payments are on, or while the answer is not
 * in: a notice that flickers in and out would be worse than none.
 */
export default function PaymentsStatusNotice() {
  const { t } = useTranslation('boards')
  const [status, setStatus] = useState<PaymentsStatus | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchJson<PaymentsStatus>(`${API_BASE}/manage/payments-status`)
      .then((found) => !cancelled && setStatus(found))
      .catch(() => {}) // a missing notice is no reason to break the moderation page
    return () => {
      cancelled = true
    }
  }, [])

  if (!status || status.enabled) return null

  return (
    <aside
      aria-label={t('admin.payments.title')}
      className="mb-6 rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950 dark:border-amber-400/40 dark:bg-amber-400/10 dark:text-amber-100"
    >
      <p className="font-semibold">
        <span aria-hidden="true">⚠️</span> {t('admin.payments.title')}
      </p>
      <p className="mt-1">{t('admin.payments.explain')}</p>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        {status.problems.map((problem) => (
          <li key={problem.code}>
            {t(`admin.payments.problem.${problem.code}`, {
              fields: problem.missing.map((field) => t(`admin.payments.field.${field}`, { defaultValue: field })).join(', '),
            })}
          </li>
        ))}
      </ul>
      <p className="mt-2">{t('admin.payments.restart')}</p>
    </aside>
  )
}
