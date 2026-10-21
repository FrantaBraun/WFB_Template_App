/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import usePageMeta from '../../hooks/usePageMeta'
import { MANAGE_PATH } from './api'

export const inputClass =
  'w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100'
export const smallInputClass =
  'rounded-lg border border-slate-200 bg-slate-50 px-2 py-1.5 text-sm text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100'
export const labelClass = 'mb-1 block text-sm text-slate-600 dark:text-slate-400'
export const primaryButtonClass =
  'rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-slate-100 hover:bg-slate-800 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-200'
export const secondaryButtonClass =
  'rounded-lg border border-slate-200 px-3 py-1.5 text-sm hover:bg-slate-100 disabled:opacity-40 dark:border-slate-700 dark:hover:bg-slate-800'
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
export function ReservationsGate({ children }: { children: ReactNode }) {
  const { t } = useTranslation('table_reservations')
  const { user, loading } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (!loading && !user) navigate('/login')
  }, [loading, user, navigate])

  if (loading || !user) return <PageMessage>{t('common.loading')}</PageMessage>
  if (user.is_admin !== true) return <PageMessage>{t('common.forbidden')}</PageMessage>
  return <>{children}</>
}

const tabClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-lg px-3 py-1.5 text-sm ${
    isActive
      ? 'bg-slate-900 text-slate-100 dark:bg-slate-100 dark:text-slate-900'
      : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
  }`

/** The frame of every administration page: the gate, the heading and the tabs between the three pages. */
export function ManageShell({ title, children }: { title: string; children: ReactNode }) {
  const { t } = useTranslation('table_reservations')
  useNoindexMeta(title)
  return (
    <ReservationsGate>
      <div className="mx-auto max-w-6xl px-4 py-8 text-slate-900 sm:px-6 sm:py-12 dark:text-slate-100">
        <h1 className="mb-4 text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1>
        <nav aria-label={t('manage.tabsLabel')} className="mb-6 flex flex-wrap gap-2">
          <NavLink to={MANAGE_PATH} end className={tabClass}>
            {t('manage.tabCalendar')}
          </NavLink>
          <NavLink to={`${MANAGE_PATH}/hours`} className={tabClass}>
            {t('manage.tabHours')}
          </NavLink>
          <NavLink to={`${MANAGE_PATH}/tables`} className={tabClass}>
            {t('manage.tabTables')}
          </NavLink>
        </nav>
        {children}
      </div>
    </ReservationsGate>
  )
}
