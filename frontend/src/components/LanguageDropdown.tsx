/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { SUPPORTED_LANGUAGES } from '../i18n'

function ChevronIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      <path d="m6 9 6 6 6-6" />
    </svg>
  )
}

export default function LanguageDropdown() {
  const { i18n, t } = useTranslation()
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  function handleSelect(lng: string) {
    i18n.changeLanguage(lng)
    setOpen(false)
  }

  const current = i18n.resolvedLanguage ?? i18n.language

  return (
    <div ref={containerRef} className="relative inline-block text-left">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={t('common.changeLanguage')}
        className="inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-xs font-medium uppercase tracking-wide text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-slate-100"
      >
        {current}
        <ChevronIcon className="h-3 w-3" />
      </button>

      {open && (
        <div
          role="listbox"
          className="absolute right-0 z-10 mt-1 min-w-[4.5rem] overflow-hidden rounded border border-slate-200 bg-white py-1 text-xs uppercase tracking-wide shadow-lg dark:border-slate-800 dark:bg-slate-900"
        >
          {SUPPORTED_LANGUAGES.map((lng) => {
            const active = i18n.resolvedLanguage === lng
            return (
              <button
                key={lng}
                type="button"
                role="option"
                aria-selected={active}
                onClick={() => handleSelect(lng)}
                className={`block w-full px-3 py-1 text-left ${
                  active
                    ? 'bg-slate-200 text-slate-900 dark:bg-slate-800 dark:text-slate-100'
                    : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
                }`}
              >
                {lng}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
