/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { Trans, useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import usePageMeta from '../hooks/usePageMeta'

/** Landed on after the user rejects consent on /consent - dead-end page, no way back except re-login. */
export default function ConsentRejected() {
  const { t } = useTranslation()
  usePageMeta({ title: t('consentRejected.pageTitle') })

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-6 text-center text-slate-900 dark:text-slate-100">
      <h1 className="text-2xl font-semibold tracking-tight">{t('consentRejected.title')}</h1>
      <p className="max-w-md text-sm text-slate-600 dark:text-slate-400">
        {/* Trans (not t()) because the translated string embeds a <link> tag around part of the text. */}
        <Trans
          i18nKey="consentRejected.message"
          components={{ link: <Link to="/login" className="text-slate-900 underline dark:text-slate-100" /> }}
        />
      </p>
    </div>
  )
}
