/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { Trans, useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { CONTACT_PATH, RULES_PATH } from './api'

const linkClass = 'underline underline-offset-4 hover:no-underline'

/** Shown instead of a form to a user whose account this application has blocked - with the way to object and the rules behind it. */
export default function BlockedNotice({ reason }: { reason: string | null }) {
  const { t } = useTranslation('boards')
  return (
    <p role="alert" className="mb-8 rounded-lg border border-red-600 p-4 text-sm dark:border-red-400">
      <strong>{t('blocked.title')}</strong>{' '}
      {t(`blocked.reason.${reason ?? 'unknown'}`, { defaultValue: reason ?? t('blocked.reason.unknown') })}{' '}
      <Trans
        t={t}
        i18nKey="blocked.help"
        components={{
          contact: <Link to={CONTACT_PATH} className={linkClass} />,
          rules: <Link to={RULES_PATH} className={linkClass} />,
        }}
      />
    </p>
  )
}
