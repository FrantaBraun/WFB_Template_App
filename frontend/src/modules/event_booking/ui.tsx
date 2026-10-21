/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import usePageMeta from '../../hooks/usePageMeta'

export { inputClass, labelClass, primaryButtonClass, secondaryButtonClass, smallInputClass } from '../forms/ui'

export const dangerButtonClass =
  'rounded-lg border border-red-300 px-3 py-1.5 text-sm text-red-700 hover:bg-red-50 disabled:opacity-40 dark:border-red-900 dark:text-red-400 dark:hover:bg-red-950'
export const cardClass = 'rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900'
export const mutedClass = 'text-sm text-slate-500 dark:text-slate-400'
export const errorClass = 'text-sm text-red-600 dark:text-red-400'
export const okClass = 'text-sm text-emerald-700 dark:text-emerald-400'

export function PageMessage({ children }: { children: ReactNode }) {
  return <p className="mx-auto max-w-5xl px-6 py-16 text-slate-600 dark:text-slate-400">{children}</p>
}

/**
 * The page title and robots directive of pages that must stay out of search
 * results (the administration, the cancellation page). `noindex` is a
 * parameter of the shared usePageMeta in the applications that carry it;
 * where it does not exist (a branch from before it) the hook simply ignores it.
 */
export function useNoindexMeta(title: string): void {
  usePageMeta({ title, noindex: true } as Parameters<typeof usePageMeta>[0])
}

/**
 * Wraps an administrators-only page: sends signed-out visitors to /login and
 * shows a notice to anyone signed in who is not an administrator of this
 * application (User.is_admin, as GET /api/auth/me reports it). Hiding the UI
 * protects nothing by itself - the backend checks require_admin on every
 * /manage endpoint regardless.
 */
export function BookingsGate({ children }: { children: ReactNode }) {
  const { t } = useTranslation('event_booking')
  const { user, loading } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (!loading && !user) navigate('/login')
  }, [loading, user, navigate])

  if (loading || !user) return <PageMessage>{t('common.loading')}</PageMessage>
  if (user.is_admin !== true) return <PageMessage>{t('common.forbidden')}</PageMessage>
  return <>{children}</>
}
