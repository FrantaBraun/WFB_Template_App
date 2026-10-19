/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import type { ItemStatus } from './api'

// Slate neutrals with dark: variants (dark mode is class-based), as in the rest
// of the app; violet is the accent of the public pages (the colour of the
// footer's link), the administrator's pages keep the CRM's plain slate buttons.
const focus =
  'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600 dark:focus-visible:outline-violet-400'

export const container = 'mx-auto w-full max-w-4xl px-6'
export const cardClass = 'rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900'
export const mutedText = 'text-slate-600 dark:text-slate-400'
export const inputClass = `w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 aria-[invalid=true]:border-red-500 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100 dark:aria-[invalid=true]:border-red-400 ${focus}`
export const labelClass = 'mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300'
export const hintClass = 'mt-1 text-xs text-slate-500 dark:text-slate-400'
export const errorTextClass = 'mt-1 text-sm text-red-700 dark:text-red-400'
export const linkClass = `font-medium text-violet-700 underline decoration-violet-300 underline-offset-4 hover:decoration-violet-700 dark:text-violet-400 dark:decoration-violet-700 dark:hover:decoration-violet-400 ${focus}`
export const accentButtonClass = `inline-flex items-center justify-center rounded-lg bg-violet-700 px-5 py-2.5 font-medium text-white transition-colors hover:bg-violet-800 dark:bg-violet-600 dark:hover:bg-violet-500 ${focus}`
export const primaryButtonClass = `inline-flex items-center justify-center rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900 ${focus}`
export const secondaryButtonClass = `inline-flex items-center justify-center rounded-lg border border-slate-200 px-3 py-1.5 text-sm hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:hover:bg-slate-800 ${focus}`
export const dangerButtonClass = `inline-flex items-center justify-center rounded-lg border border-red-200 px-3 py-1.5 text-sm text-red-700 hover:bg-red-50 disabled:opacity-50 dark:border-red-900 dark:text-red-400 dark:hover:bg-red-950 ${focus}`

const STATUS_STYLES: Record<ItemStatus, string> = {
  live: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-200',
  in_preparation: 'bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-200',
}

/** The status in words - the colour only helps. */
export function StatusBadge({ status }: { status: ItemStatus }) {
  const { t } = useTranslation('portfolio')
  return (
    <span className={`inline-flex shrink-0 items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_STYLES[status]}`}>
      {t(`status.${status}`)}
    </span>
  )
}

export function TagList({ tags, label }: { tags: string[]; label: string }) {
  if (tags.length === 0) return null
  return (
    <ul aria-label={label} className="flex flex-wrap gap-2">
      {tags.map((tag) => (
        <li
          key={tag}
          className="max-w-full break-words rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-300"
        >
          {tag}
        </li>
      ))}
    </ul>
  )
}

/** A status line on its own: loading (polite) or a problem (announced at once). */
export function PageMessage({ children, error = false }: { children: ReactNode; error?: boolean }) {
  return (
    <div className={`${container} py-16`}>
      <p
        role={error ? 'alert' : 'status'}
        className={error ? 'text-red-700 dark:text-red-400' : 'text-slate-500 dark:text-slate-400'}
      >
        {children}
      </p>
    </div>
  )
}

export function BackLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className={`text-sm ${mutedText} hover:text-slate-900 dark:hover:text-slate-100 ${focus}`}>
      <span aria-hidden="true">← </span>
      {children}
    </Link>
  )
}

/**
 * Wraps every administrator page. Signed-out visitors are sent to /login and
 * signed-in non-administrators get a notice. This only decides what is
 * *shown* - the backend checks User.is_admin on every /manage request, so
 * hiding the UI is never what protects the data.
 */
export function AdminGate({ children }: { children: ReactNode }) {
  const { t } = useTranslation('portfolio')
  const { user, loading } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (!loading && !user) navigate('/login')
  }, [loading, user, navigate])

  if (loading || !user) return <PageMessage>{t('common.loading')}</PageMessage>
  if (user.is_admin !== true) return <PageMessage>{t('common.forbidden')}</PageMessage>
  return <>{children}</>
}
