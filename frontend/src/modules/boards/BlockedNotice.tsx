/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'

/** Shown instead of a form to a user whose account this application has blocked. */
export default function BlockedNotice({ reason }: { reason: string | null }) {
  const { t } = useTranslation('boards')
  return (
    <p role="alert" className="mb-8 rounded-lg border border-red-600 p-4 text-sm dark:border-red-400">
      <strong>{t('blocked.title')}</strong>{' '}
      {t(`blocked.reason.${reason ?? 'unknown'}`, { defaultValue: reason ?? t('blocked.reason.unknown') })}
    </p>
  )
}
