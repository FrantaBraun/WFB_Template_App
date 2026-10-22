/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { rememberReturnPath } from '../../utils/returnPath'
import { limitReached } from './api'
import './repository.css'

export const inputClass =
  'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100'
export const labelClass = 'mb-1 block text-sm font-medium text-slate-700 dark:text-slate-300'
export const hintClass = 'mt-1 text-xs text-slate-500 dark:text-slate-400'
export const primaryButtonClass =
  'repo-accent-bg repo-focus inline-flex items-center justify-center rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50'
export const secondaryButtonClass =
  'repo-focus inline-flex items-center justify-center rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-800 hover:bg-slate-100 disabled:opacity-50 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800'
export const dangerButtonClass =
  'inline-flex items-center justify-center rounded-lg border border-red-300 bg-white px-3 py-1.5 text-sm text-red-700 hover:bg-red-50 disabled:opacity-50 dark:border-red-900 dark:bg-slate-900 dark:text-red-400 dark:hover:bg-red-950'
export const cardClass = 'rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900'
export const errorTextClass = 'mt-1 text-sm text-red-600 dark:text-red-400'

export function PageMessage({ children, error = false }: { children: ReactNode; error?: boolean }) {
  return (
    <p className={`mx-auto max-w-4xl px-6 py-16 ${error ? 'text-red-600 dark:text-red-400' : 'text-slate-500 dark:text-slate-400'}`}>
      {children}
    </p>
  )
}

export function BackLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className="repo-focus text-sm text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100">
      ← {children}
    </Link>
  )
}

/**
 * Wraps every page of the module: everything here belongs to a signed-in user,
 * so a visitor is sent to /login and brought back afterwards. This only decides
 * what is shown - the backend answers 401 without a token and 404 for what
 * is not the caller's regardless.
 */
export function RepositoryGate({ children }: { children: ReactNode }) {
  const { t } = useTranslation('repository')
  const { user, loading } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    if (loading || user) return
    rememberReturnPath(location.pathname + location.search)
    navigate('/login')
  }, [loading, user, navigate, location.pathname, location.search])

  if (loading || !user) return <PageMessage>{t('common.loading')}</PageMessage>
  return <>{children}</>
}

/** The text of a failed save for the user: a reached limit is named, anything else is the generic message. */
export function useSaveErrorText() {
  const { t } = useTranslation('repository')
  return (error: unknown, fallbackKey: string): string => {
    const limit = limitReached(error)
    if (limit) return t(`limits.${limit.limit}`, { max: limit.max, defaultValue: t('limits.generic', { max: limit.max }) })
    return t(fallbackKey)
  }
}

/** A modal dialog: closes on Escape and on a click outside, focuses its first control, and says what it is to screen readers. */
export function Modal({ title, onClose, children, wide = false }: { title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  const { t } = useTranslation('repository')
  const titleId = useId()
  const panel = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    const focusable = panel.current?.querySelector<HTMLElement>('input, select, textarea') ?? panel.current?.querySelector<HTMLElement>('button')
    focusable?.focus()
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      previous?.focus?.()
    }
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/60 px-3 py-10"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className={`w-full ${wide ? 'max-w-2xl' : 'max-w-md'} rounded-2xl border border-slate-200 bg-white p-5 text-slate-900 shadow-xl dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100`}
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <h2 id={titleId} className="text-lg font-semibold">
            {title}
          </h2>
          <button type="button" onClick={onClose} aria-label={t('common.close')} className="repo-focus rounded p-1 text-slate-500 hover:text-slate-900 dark:hover:text-slate-100">
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}

/**
 * Asks the user to type the name of what they are about to delete - the same
 * confirmation the backend demands (`confirm_name`). `onConfirm` returns an
 * error text to show, or null when it went through (the caller then closes).
 */
export function ConfirmNameDialog({
  title,
  message,
  expectedName,
  confirmLabel,
  onConfirm,
  onClose,
}: {
  title: string
  message: ReactNode
  expectedName: string
  confirmLabel: string
  onConfirm: () => Promise<string | null>
  onClose: () => void
}) {
  const { t } = useTranslation('repository')
  const [typed, setTyped] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputId = useId()

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    const failure = await onConfirm()
    if (failure) {
      setError(failure)
      setBusy(false)
    }
  }

  return (
    <Modal title={title} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <div className="text-sm text-slate-700 dark:text-slate-300">{message}</div>
        <div>
          <label htmlFor={inputId} className={labelClass}>
            {t('common.typeNameToConfirm', { name: expectedName })}
          </label>
          <input id={inputId} value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" className={inputClass} />
        </div>
        {error && <p className={errorTextClass}>{error}</p>}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className={secondaryButtonClass}>
            {t('common.cancel')}
          </button>
          <button
            type="submit"
            disabled={busy || typed !== expectedName}
            className="inline-flex items-center justify-center rounded-lg bg-red-700 px-4 py-2 text-sm font-medium text-white hover:bg-red-800 disabled:opacity-50"
          >
            {confirmLabel}
          </button>
        </div>
      </form>
    </Modal>
  )
}

/** A yes/no question before something that cannot be taken back at once; `onConfirm` returns an error text to show, or null when it went through (the caller then closes). */
export function ConfirmDialog({
  title,
  message,
  confirmLabel,
  danger = false,
  onConfirm,
  onClose,
}: {
  title: string
  message: ReactNode
  confirmLabel: string
  danger?: boolean
  onConfirm: () => Promise<string | null>
  onClose: () => void
}) {
  const { t } = useTranslation('repository')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function confirm() {
    setBusy(true)
    setError(null)
    const failure = await onConfirm()
    if (failure) {
      setError(failure)
      setBusy(false)
    }
  }

  return (
    <Modal title={title} onClose={onClose}>
      <div className="space-y-4">
        <div className="text-sm text-slate-700 dark:text-slate-300">{message}</div>
        {error && <p className={errorTextClass}>{error}</p>}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className={secondaryButtonClass}>
            {t('common.cancel')}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={confirm}
            className={
              danger
                ? 'inline-flex items-center justify-center rounded-lg bg-red-700 px-4 py-2 text-sm font-medium text-white hover:bg-red-800 disabled:opacity-50'
                : primaryButtonClass
            }
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </Modal>
  )
}
