/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { isoDay, weekdayName } from './api'

interface Props {
  year: number
  /** 0-based, like Date. */
  month: number
  selected: string | null
  onSelect: (day: string) => void
  /** Whether a day can be chosen (default: every day). */
  isSelectable?: (day: string) => boolean
  /** A short description of the day's state for screen readers (appended to its date). */
  describe?: (day: string) => string
  /** What to show under the day number (a count, "closed", ...). */
  renderBadge?: (day: string) => ReactNode
  /** Extra classes of a day (colour of a closed day, say). */
  dayClass?: (day: string) => string
  onPrevious: () => void
  onNext: () => void
  canPrevious: boolean
  canNext: boolean
  /** Taller cells with room for a badge (the administrators' calendar). */
  roomy?: boolean
}

/**
 * A month as a grid of days, Monday first: the date picker of the reservation
 * form and the administrators' calendar. It knows nothing about reservations -
 * what a day shows and whether it can be chosen come from the caller.
 */
export default function MonthGrid({
  year,
  month,
  selected,
  onSelect,
  isSelectable,
  describe,
  renderBadge,
  dayClass,
  onPrevious,
  onNext,
  canPrevious,
  canNext,
  roomy = false,
}: Props) {
  const { t, i18n } = useTranslation('table_reservations')
  const language = i18n.resolvedLanguage ?? i18n.language
  const first = new Date(year, month, 1)
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const blanks = (first.getDay() + 6) % 7
  const title = first.toLocaleDateString(language, { month: 'long', year: 'numeric' })

  const cells: (string | null)[] = [
    ...Array.from({ length: blanks }, () => null),
    ...Array.from({ length: daysInMonth }, (_, index) => isoDay(new Date(year, month, index + 1))),
  ]

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <button
          type="button"
          onClick={onPrevious}
          disabled={!canPrevious}
          aria-label={t('picker.previousMonth')}
          className="rounded-lg border border-slate-200 px-2.5 py-1 text-sm hover:bg-slate-100 disabled:opacity-30 dark:border-slate-700 dark:hover:bg-slate-800"
        >
          ‹
        </button>
        <p className="text-sm font-medium capitalize" aria-live="polite">
          {title}
        </p>
        <button
          type="button"
          onClick={onNext}
          disabled={!canNext}
          aria-label={t('picker.nextMonth')}
          className="rounded-lg border border-slate-200 px-2.5 py-1 text-sm hover:bg-slate-100 disabled:opacity-30 dark:border-slate-700 dark:hover:bg-slate-800"
        >
          ›
        </button>
      </div>
      <div className="grid grid-cols-7 gap-1 text-center text-xs text-slate-500 dark:text-slate-400" aria-hidden="true">
        {Array.from({ length: 7 }, (_, weekday) => (
          <span key={weekday}>{weekdayName(weekday, language, 'short')}</span>
        ))}
      </div>
      <div className="mt-1 grid grid-cols-7 gap-1">
        {cells.map((iso, index) => {
          if (iso === null) return <span key={`blank-${index}`} />
          const selectable = isSelectable ? isSelectable(iso) : true
          const isSelected = selected === iso
          const stateText = describe?.(iso)
          return (
            <button
              key={iso}
              type="button"
              disabled={!selectable}
              onClick={() => onSelect(iso)}
              aria-pressed={isSelected}
              aria-label={`${new Date(year, month, Number(iso.slice(8))).toLocaleDateString(language, { weekday: 'long', day: 'numeric', month: 'long' })}${stateText ? `, ${stateText}` : ''}`}
              className={`flex flex-col items-center justify-start rounded-lg border text-sm ${roomy ? 'min-h-16 gap-0.5 px-1 py-1.5' : 'h-10 justify-center'} ${
                isSelected
                  ? 'border-slate-900 bg-slate-900 text-slate-100 dark:border-slate-100 dark:bg-slate-100 dark:text-slate-900'
                  : selectable
                    ? 'border-slate-200 hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800'
                    : 'border-transparent text-slate-400 line-through dark:text-slate-600'
              } ${dayClass?.(iso) ?? ''}`}
            >
              <span>{Number(iso.slice(8))}</span>
              {renderBadge && <span className="text-[11px] leading-tight">{renderBadge(iso)}</span>}
            </button>
          )
        })}
      </div>
    </div>
  )
}
