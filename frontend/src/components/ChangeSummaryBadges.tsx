/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'

/** How many structural changes a version brought, by severity (backend ChangeSummaryOut). */
export interface ChangeSummaryData {
  breaking: number
  warning: number
  info: number
}

const BADGE = 'rounded-full px-2 py-0.5 text-xs font-medium'

/**
 * The counts of a version's changes as small badges: breaking ones in red,
 * warnings in amber, and - only when `showInfo` is on, as the version history
 * keeps to what matters - the harmless ones in grey. Nothing at all for a
 * count of zero, so a version with no structural change shows no badge.
 */
export default function ChangeSummaryBadges({ summary, showInfo = false }: { summary: ChangeSummaryData | null; showInfo?: boolean }) {
  const { t } = useTranslation()
  if (!summary) return null
  return (
    <>
      {summary.breaking > 0 && (
        <span className={`${BADGE} bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300`}>
          {t('changes.summary.breaking', { count: summary.breaking })}
        </span>
      )}
      {summary.warning > 0 && (
        <span className={`${BADGE} bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300`}>
          {t('changes.summary.warning', { count: summary.warning })}
        </span>
      )}
      {showInfo && summary.info > 0 && (
        <span className={`${BADGE} bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300`}>
          {t('changes.summary.info', { count: summary.info })}
        </span>
      )}
    </>
  )
}
