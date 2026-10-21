/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { MANAGE_PATH } from './api'

function MenuIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      <path d="M4 3h16v18H4z" />
      <path d="M8 8h8M8 12h8M8 16h5" />
    </svg>
  )
}

/**
 * The header entry point to the administration of the menus - an icon link
 * rendered only for administrators (the module's `headerWidget`, because a plain
 * `nav` entry is shown to every visitor). Display only: the backend still checks
 * User.is_admin on every /manage request.
 */
export default function AdminNavLink() {
  const { t } = useTranslation('pub_menu')
  const { user } = useAuth()
  if (user?.is_admin !== true) return null
  return (
    <Link
      to={MANAGE_PATH}
      aria-label={t('nav.manage')}
      title={t('nav.manage')}
      className="rounded-full p-1.5 text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-100"
    >
      <MenuIcon className="h-5 w-5" />
    </Link>
  )
}
