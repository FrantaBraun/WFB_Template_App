/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { TICKETS_PATH } from './api'

function TicketIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      <path d="M2 9a3 3 0 0 1 0 6v2a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-2a3 3 0 0 1 0-6V7a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z" />
      <path d="M13 5v2" />
      <path d="M13 17v2" />
      <path d="M13 11v2" />
    </svg>
  )
}

/**
 * The header entry point to the tickets - an icon link rendered only for
 * administrators (the module's `headerWidget`, because a plain `nav` entry is
 * shown to every visitor). Display only: the backend still checks
 * User.is_admin on every request.
 */
export default function TicketsNavLink() {
  const { t } = useTranslation('tickets')
  const { user } = useAuth()
  if (user?.is_admin !== true) return null
  return (
    <Link
      to={TICKETS_PATH}
      aria-label={t('nav.tickets')}
      title={t('nav.tickets')}
      className="rounded-full p-1.5 text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-slate-100"
    >
      <TicketIcon className="h-5 w-5" />
    </Link>
  )
}
