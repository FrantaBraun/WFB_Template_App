/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'

export const inputClass =
  'w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100'
export const smallInputClass =
  'rounded-lg border border-slate-200 bg-slate-50 px-2 py-1.5 text-sm text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100'
export const labelClass = 'mb-1 block text-sm text-slate-600 dark:text-slate-400'
export const primaryButtonClass =
  'rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900'
export const secondaryButtonClass =
  'rounded-lg border border-slate-200 px-3 py-1.5 text-sm hover:bg-slate-100 disabled:opacity-40 dark:border-slate-700 dark:hover:bg-slate-800'

export function PageMessage({ children }: { children: ReactNode }) {
  return <p className="mx-auto max-w-5xl px-6 py-16 text-slate-600 dark:text-slate-400">{children}</p>
}

/**
 * Wraps an administrators-only page: sends signed-out visitors to /login and
 * shows a notice to anyone signed in who isn't an administrator of this
 * application (User.is_admin, as GET /api/auth/me reports it). Hiding the UI
 * protects nothing by itself - the backend checks require_admin on every
 * /manage endpoint regardless.
 */
export function FormsGate({ children }: { children: ReactNode }) {
  const { t } = useTranslation('forms')
  const { user, loading } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (!loading && !user) navigate('/login')
  }, [loading, user, navigate])

  if (loading || !user) return <PageMessage>{t('common.loading')}</PageMessage>
  if (user.is_admin !== true) return <PageMessage>{t('common.forbidden')}</PageMessage>
  return <>{children}</>
}
