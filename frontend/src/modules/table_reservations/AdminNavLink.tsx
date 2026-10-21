/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { MANAGE_PATH } from './api'

function CalendarIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      <rect x="3" y="4" width="18" height="18" rx="2" />
      <path d="M16 2v4M8 2v4M3 10h18" />
    </svg>
  )
}

/**
 * The header entry point to the administration of reservations - an icon link
 * rendered only for administrators (the module's `headerWidget`, because a plain
 * `nav` entry is shown to every visitor). Display only: the backend still checks
 * User.is_admin on every /manage request.
 */
export default function AdminNavLink() {
  const { t } = useTranslation('table_reservations')
  const { user } = useAuth()
  if (user?.is_admin !== true) return null
  return (
    <Link
      to={MANAGE_PATH}
      aria-label={t('nav.manage')}
      title={t('nav.manage')}
      className="rounded-full p-1.5 text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-100"
    >
      <CalendarIcon className="h-5 w-5" />
    </Link>
  )
}
