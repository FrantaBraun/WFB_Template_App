/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useId, useRef, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

interface ResultDialogProps {
  tone: 'success' | 'error'
  title: string
  children: ReactNode
  onClose: () => void
}

function ResultIcon({ tone }: { tone: ResultDialogProps['tone'] }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="h-5 w-5">
      {tone === 'success' ? <path d="m5 12.5 4.5 4.5L19 7.5" /> : <path d="M12 7v6m0 3.5v.01" />}
    </svg>
  )
}

/**
 * A small modal telling the user how something they just did turned out
 * (the manual API documentation check, see ApiDocDetail.tsx). It has a single
 * way out - the Close button, Escape or a click outside the card - so focus
 * moves to that button on open and Tab is kept from wandering to the page
 * behind. Putting focus back where the user was is up to the caller, who
 * knows which control opened it.
 */
export default function ResultDialog({ tone, title, children, onClose }: ResultDialogProps) {
  const { t } = useTranslation()
  const titleId = useId()
  const bodyId = useId()
  const closeRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        onClose()
      } else if (e.key === 'Tab') {
        e.preventDefault()
        closeRef.current?.focus()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        role={tone === 'error' ? 'alertdialog' : 'dialog'}
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={bodyId}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-5 shadow-xl dark:border-slate-800 dark:bg-slate-900"
      >
        <div className="flex items-start gap-3">
          <span
            className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${
              tone === 'success'
                ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300'
                : 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'
            }`}
          >
            <ResultIcon tone={tone} />
          </span>
          <div className="min-w-0 flex-1">
            <h3 id={titleId} className="text-base font-semibold text-slate-900 dark:text-slate-100">
              {title}
            </h3>
            <div id={bodyId} className="mt-2 space-y-2 break-words text-sm text-slate-600 dark:text-slate-400">
              {children}
            </div>
          </div>
        </div>

        <div className="mt-5 flex justify-end">
          <button
            ref={closeRef}
            type="button"
            autoFocus
            onClick={onClose}
            className="rounded-lg bg-slate-900 px-4 py-1.5 text-sm font-medium text-slate-100 dark:bg-slate-100 dark:text-slate-900"
          >
            {t('common.close')}
          </button>
        </div>
      </div>
    </div>
  )
}
