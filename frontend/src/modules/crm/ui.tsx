/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import type { TaskStatus } from './api'

export const inputClass =
  'w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100'
export const labelClass = 'mb-1 block text-sm text-slate-600 dark:text-slate-400'
export const primaryButtonClass =
  'rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900'
export const secondaryButtonClass =
  'rounded-lg border border-slate-200 px-3 py-1.5 text-sm hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800'
export const dangerButtonClass =
  'rounded-lg border border-red-200 px-3 py-1.5 text-sm text-red-700 hover:bg-red-50 dark:border-red-900 dark:text-red-400 dark:hover:bg-red-950'
export const cardClass = 'rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900'

const STATUS_STYLES: Record<TaskStatus, string> = {
  new: 'bg-sky-100 text-sky-800 dark:bg-sky-900/50 dark:text-sky-200',
  in_progress: 'bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-200',
  done: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-200',
  invoiced: 'bg-violet-100 text-violet-800 dark:bg-violet-900/50 dark:text-violet-200',
  paid: 'bg-green-200 text-green-900 dark:bg-green-900/60 dark:text-green-100',
  cancelled: 'bg-slate-200 text-slate-600 dark:bg-slate-800 dark:text-slate-400',
}

export function StatusBadge({ status }: { status: TaskStatus }) {
  const { t } = useTranslation('crm')
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[status]}`}>{t(`status.${status}`)}</span>
}

export function PageMessage({ children, error = false }: { children: ReactNode; error?: boolean }) {
  return (
    <p className={`mx-auto max-w-4xl px-6 py-16 ${error ? 'text-red-600 dark:text-red-400' : 'text-slate-500 dark:text-slate-400'}`}>
      {children}
    </p>
  )
}

export function BackLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className="text-sm text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100">
      ← {children}
    </Link>
  )
}

/**
 * Wraps every CRM page. The CRM is administrator-only: signed-out visitors
 * are sent to /login and signed-in non-administrators get a notice. This only
 * decides what is *shown* - the backend enforces User.is_admin on every
 * endpoint, so hiding the UI is never what protects the data.
 */
export function CrmGate({ children }: { children: ReactNode }) {
  const { t } = useTranslation('crm')
  const { user, loading } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (!loading && !user) navigate('/login')
  }, [loading, user, navigate])

  if (loading || !user) return <PageMessage>{t('common.loading')}</PageMessage>
  if (user.is_admin !== true) return <PageMessage>{t('common.forbidden')}</PageMessage>
  return <>{children}</>
}
