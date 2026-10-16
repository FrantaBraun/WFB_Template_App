/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useId } from 'react'
import { useTranslation } from 'react-i18next'

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </svg>
  )
}

function ClearIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  )
}

/**
 * The free-text search row shared by the API documentation, collection and
 * integration lists. It only holds the text - the page decides what to do with
 * it (a debounced server-side search). `label` is read by screen readers only;
 * the placeholder says what is searched.
 */
export default function ListSearch({ value, onChange, label }: { value: string; onChange: (value: string) => void; label: string }) {
  const { t } = useTranslation()
  const inputId = useId()

  return (
    <form role="search" onSubmit={(e) => e.preventDefault()} className="relative">
      <label htmlFor={inputId} className="sr-only">
        {label}
      </label>
      <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
      <input
        id={inputId}
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Escape') onChange('')
        }}
        placeholder={t('common.search.placeholder')}
        autoComplete="off"
        spellCheck={false}
        maxLength={200}
        className="w-full rounded-lg border border-slate-200 bg-white py-2 pl-9 pr-9 text-base text-slate-900 sm:text-sm placeholder:text-slate-400 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100 [&::-webkit-search-cancel-button]:hidden"
      />
      {value && (
        <button
          type="button"
          onClick={() => onChange('')}
          aria-label={t('common.search.clear')}
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full p-1 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
        >
          <ClearIcon className="h-4 w-4" />
        </button>
      )}
    </form>
  )
}
