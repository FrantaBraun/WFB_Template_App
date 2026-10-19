/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { CRM_PATH } from './api'

function BriefcaseIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      <rect x="2" y="7" width="20" height="14" rx="2" />
      <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
    </svg>
  )
}

/**
 * The header entry point to the CRM - an icon link rendered only for
 * administrators (the module's `headerWidget`, because a plain `nav` entry
 * is shown to every visitor). Display only: the backend still checks
 * User.is_admin on every CRM request.
 */
export default function CrmNavLink() {
  const { t } = useTranslation('crm')
  const { user } = useAuth()
  if (user?.is_admin !== true) return null
  return (
    <Link
      to={CRM_PATH}
      aria-label={t('nav.crm')}
      title={t('nav.crm')}
      className="rounded-full p-1.5 text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-100"
    >
      <BriefcaseIcon className="h-5 w-5" />
    </Link>
  )
}
