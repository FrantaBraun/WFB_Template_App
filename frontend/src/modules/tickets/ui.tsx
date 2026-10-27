/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { useEnabledModules } from '../moduleStore'
import {
  CRM_API_BASE,
  errorCode,
  errorStatus,
  fetchJson,
  splitMinutes,
  type PartnerOption,
  type TicketStatus,
  type TicketType,
} from './api'

export const inputClass =
  'w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100'
export const labelClass = 'mb-1 block text-sm text-slate-600 dark:text-slate-400'
export const primaryButtonClass =
  'rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900'
export const secondaryButtonClass =
  'rounded-lg border border-slate-200 px-3 py-1.5 text-sm hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:hover:bg-slate-800'
export const dangerButtonClass =
  'rounded-lg border border-red-200 px-3 py-1.5 text-sm text-red-700 hover:bg-red-50 dark:border-red-900 dark:text-red-400 dark:hover:bg-red-950'
export const cardClass = 'rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900'

const TYPE_STYLES: Record<TicketType, string> = {
  general: 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  issue: 'bg-red-100 text-red-800 dark:bg-red-900/50 dark:text-red-200',
  order: 'bg-violet-100 text-violet-800 dark:bg-violet-900/50 dark:text-violet-200',
  internal: 'bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-200',
}

const STATUS_STYLES: Record<TicketStatus, string> = {
  open: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/50 dark:text-emerald-200',
  closed: 'bg-slate-200 text-slate-600 dark:bg-slate-800 dark:text-slate-400',
}

export function TypeBadge({ type }: { type: TicketType }) {
  const { t } = useTranslation('tickets')
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${TYPE_STYLES[type]}`}>{t(`type.${type}`)}</span>
}

export function StatusBadge({ status }: { status: TicketStatus }) {
  const { t } = useTranslation('tickets')
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[status]}`}>{t(`status.${status}`)}</span>
}

export function PageMessage({ children, error = false }: { children: ReactNode; error?: boolean }) {
  return (
    <p className={`mx-auto max-w-5xl px-6 py-16 ${error ? 'text-red-600 dark:text-red-400' : 'text-slate-500 dark:text-slate-400'}`}>
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
 * Wraps every tickets page. The module is administrator-only: signed-out
 * visitors are sent to /login and signed-in non-administrators get a notice.
 * This only decides what is *shown* - the backend enforces User.is_admin on
 * every /manage endpoint, so hiding the UI is never what protects the data.
 */
export function TicketsGate({ children }: { children: ReactNode }) {
  const { t } = useTranslation('tickets')
  const { user, loading } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (!loading && !user) navigate('/login')
  }, [loading, user, navigate])

  if (loading || !user) return <PageMessage>{t('common.loading')}</PageMessage>
  if (user.is_admin !== true) return <PageMessage>{t('common.forbidden')}</PageMessage>
  return <>{children}</>
}

/** "1 h 35 min", "2 h", "45 min", "0 min" - in the language of the viewer. */
export function useMinutesLabel(): (minutes: number) => string {
  const { t } = useTranslation('tickets')
  return (minutes) => {
    const { hours, minutes: rest } = splitMinutes(minutes)
    if (hours > 0 && rest > 0) return t('time.hoursMinutes', { hours, minutes: rest })
    if (hours > 0) return t('time.hours', { hours })
    return t('time.minutes', { minutes: rest })
  }
}

/** The translated message for a failed request: by the backend's code, else by status, else the generic one. */
export function useErrorText(): (error: unknown, fallbackKey: string) => string {
  const { t } = useTranslation('tickets')
  return (error, fallbackKey) => {
    const code = errorCode(error)
    if (code && t(`errors.${code}`, { defaultValue: '' })) return t(`errors.${code}`)
    const status = errorStatus(error)
    if (status === 413) return t('errors.tooLarge')
    if (status === 415) return t('errors.unsupportedType')
    return t(fallbackKey)
  }
}

/** Whether the CRM module is switched on - only then partners can be linked and searched. */
export function useCrmEnabled(): boolean {
  return useEnabledModules().some((module) => module.key === 'crm')
}

/**
 * Chooses the CRM partner a ticket is linked to: a search box over the CRM's
 * own partner list (so there is one source of truth), the choice shown as a
 * chip. Renders nothing while the CRM is off.
 */
export function PartnerPicker({
  value,
  onChange,
}: {
  value: PartnerOption | null
  onChange: (partner: PartnerOption | null) => void
}) {
  const { t } = useTranslation('tickets')
  const crmEnabled = useCrmEnabled()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<PartnerOption[]>([])
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!crmEnabled || value || query.trim().length < 1) {
      setResults([])
      return
    }
    let cancelled = false
    const timer = setTimeout(async () => {
      try {
        const found = await fetchJson<PartnerOption[]>(`${CRM_API_BASE}/partners?q=${encodeURIComponent(query.trim())}`)
        if (!cancelled) {
          setResults(found.slice(0, 8))
          setFailed(false)
        }
      } catch {
        if (!cancelled) setFailed(true)
      }
    }, 250)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [crmEnabled, query, value])

  if (!crmEnabled) return null

  if (value) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-sky-100 px-3 py-1 text-sm text-sky-900 dark:bg-sky-900/50 dark:text-sky-100">
          {value.name}
          {value.company ? ` · ${value.company}` : ''}
        </span>
        <button type="button" onClick={() => onChange(null)} className={secondaryButtonClass}>
          {t('partner.remove')}
        </button>
      </div>
    )
  }

  return (
    <div className="relative">
      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={t('partner.search')}
        className={inputClass}
        aria-label={t('partner.search')}
      />
      {failed && <p className="mt-1 text-sm text-red-600 dark:text-red-400">{t('partner.searchError')}</p>}
      {results.length > 0 && (
        <ul className={`${cardClass} absolute z-10 mt-1 max-h-64 w-full overflow-auto shadow-lg`}>
          {results.map((partner) => (
            <li key={partner.id}>
              <button
                type="button"
                onClick={() => {
                  onChange(partner)
                  setQuery('')
                }}
                className="block w-full px-4 py-2 text-start hover:bg-slate-50 dark:hover:bg-slate-800"
              >
                <span className="block font-medium">{partner.name}</span>
                <span className="block text-sm text-slate-500 dark:text-slate-400">
                  {[partner.company, partner.email].filter(Boolean).join(' · ')}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
