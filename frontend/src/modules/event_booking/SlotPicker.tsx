/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { formatDay, formatTime, isoDay, parseDay, type FreeDay, type SlotInfo } from './api'
import { errorClass, inputClass, labelClass, mutedClass } from './ui'

export interface SlotChoice {
  date: string
  /** null is the whole day. */
  time: string | null
}

interface SlotPickerProps {
  /** Every block is a list of days: pick from a list instead of a calendar. */
  finiteDays: boolean
  maxDaysAhead: number
  /** The days with a free place; `month` ("YYYY-MM") limits them to one month (not passed for a list). */
  loadDays: (month?: string) => Promise<FreeDay[]>
  loadSlots: (date: string) => Promise<SlotInfo[]>
  /** The complete choice (day and, if the day has times, a time) or null while it is not complete. */
  value: SlotChoice | null
  onChange: (value: SlotChoice | null) => void
  disabled?: boolean
  /** A problem with the choice, from the server. */
  error?: string | null
  idPrefix: string
  /** Changing this reloads the days and times (after a slot turned out to be taken). */
  reloadKey?: number
}

function startOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1)
}

function monthKey(date: Date): string {
  return isoDay(date).slice(0, 7)
}

/**
 * Picking a day and a time: a list of days when the offer is a fixed list of
 * them, otherwise a month calendar in which only days with a free place can be
 * chosen; then - unless the day is one whole-day slot - the times of that day
 * that still have room. Used by the public booking form and by the
 * administrators' edit of a booking (which passes loaders that include the
 * booking's own slot).
 */
export default function SlotPicker({
  finiteDays,
  maxDaysAhead,
  loadDays,
  loadSlots,
  value,
  onChange,
  disabled = false,
  error = null,
  idPrefix,
  reloadKey = 0,
}: SlotPickerProps) {
  const { t, i18n } = useTranslation('event_booking')
  const initial = useRef(value)
  const [month, setMonth] = useState(() => startOfMonth(initial.current ? parseDay(initial.current.date) : new Date()))
  const [days, setDays] = useState<FreeDay[] | null>(null)
  const [chosenDay, setChosenDay] = useState<string | null>(initial.current?.date ?? null)
  const [slots, setSlots] = useState<SlotInfo[] | null>(null)
  const [loadFailed, setLoadFailed] = useState(false)

  // The loaders and the callback are new functions on every render of the parent; the effects below must not re-run for that.
  const latest = useRef({ loadDays, loadSlots, onChange, value })
  latest.current = { loadDays, loadSlots, onChange, value }

  const shownMonth = monthKey(month)
  useEffect(() => {
    let cancelled = false
    setLoadFailed(false)
    latest.current
      .loadDays(finiteDays ? undefined : shownMonth)
      .then((found) => !cancelled && setDays(found))
      .catch(() => !cancelled && (setDays([]), setLoadFailed(true)))
    return () => {
      cancelled = true
    }
  }, [finiteDays, shownMonth, reloadKey])

  useEffect(() => {
    if (!chosenDay) {
      setSlots(null)
      return
    }
    let cancelled = false
    setSlots(null)
    latest.current
      .loadSlots(chosenDay)
      .then((found) => {
        if (cancelled) return
        setSlots(found)
        const wholeDay = found.length === 1 && found[0].time === null
        const current = latest.current.value
        if (wholeDay) latest.current.onChange({ date: chosenDay, time: null })
        else if (!(current && current.date === chosenDay && found.some((slot) => slot.time === current.time))) latest.current.onChange(null)
      })
      .catch(() => {
        if (cancelled) return
        setSlots([])
        setLoadFailed(true)
        latest.current.onChange(null)
      })
    return () => {
      cancelled = true
    }
  }, [chosenDay, reloadKey])

  function chooseDay(day: string) {
    setChosenDay(day || null)
    latest.current.onChange(null)
  }

  const freeDays = new Set((days ?? []).map((day) => day.date))
  const wholeDay = slots !== null && slots.length === 1 && slots[0].time === null
  const language = i18n.language

  return (
    <fieldset disabled={disabled} className="min-w-0 space-y-3" aria-describedby={error ? `${idPrefix}-slot-error` : undefined}>
      <legend className={`${labelClass} mb-2`}>{t('picker.legend')}</legend>

      {finiteDays ? (
        <div>
          <label htmlFor={`${idPrefix}-day`} className={labelClass}>{t('picker.day')}</label>
          <select id={`${idPrefix}-day`} value={chosenDay ?? ''} onChange={(e) => chooseDay(e.target.value)} className={inputClass} aria-invalid={error ? true : undefined}>
            <option value="">{days === null ? t('common.loading') : t('picker.pickDay')}</option>
            {(days ?? []).map((day) => (
              <option key={day.date} value={day.date}>{formatDay(day.date, language)}</option>
            ))}
          </select>
        </div>
      ) : (
        <MonthCalendar
          month={month}
          maxDaysAhead={maxDaysAhead}
          freeDays={freeDays}
          loading={days === null}
          chosen={chosenDay}
          onMonth={setMonth}
          onPick={chooseDay}
          minMonth={startOfMonth(initial.current ? new Date(Math.min(Date.now(), parseDay(initial.current.date).getTime())) : new Date())}
          idPrefix={idPrefix}
        />
      )}

      {days !== null && days.length === 0 && !loadFailed && finiteDays && <p className={mutedClass}>{t('picker.noDays')}</p>}
      {loadFailed && <p role="alert" className={errorClass}>{t('picker.loadError')}</p>}

      {chosenDay && slots !== null && !wholeDay && (
        slots.length === 0 ? (
          <p className={mutedClass}>{t('picker.noTimes')}</p>
        ) : (
          <div role="radiogroup" aria-label={t('picker.time')} className="flex flex-wrap gap-2">
            {slots.map((slot) => {
              const selected = value?.date === chosenDay && value.time === slot.time
              return (
                <label
                  key={slot.time ?? 'all'}
                  className={`cursor-pointer rounded-lg border px-3 py-1.5 text-sm ${
                    selected
                      ? 'border-slate-900 bg-slate-900 text-slate-100 dark:border-slate-100 dark:bg-slate-100 dark:text-slate-900'
                      : 'border-slate-200 bg-white hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:hover:bg-slate-800'
                  }`}
                >
                  <input
                    type="radio"
                    name={`${idPrefix}-time`}
                    className="sr-only"
                    checked={selected}
                    onChange={() => onChange({ date: chosenDay, time: slot.time })}
                  />
                  {slot.time ? formatTime(slot.time) : t('picker.allDay')}
                  {slot.capacity > 1 && <span className="ml-2 text-xs opacity-80">{t('picker.places', { count: slot.free })}</span>}
                </label>
              )
            })}
          </div>
        )
      )}
      {chosenDay && slots !== null && wholeDay && <p className={mutedClass}>{t('picker.wholeDay')}</p>}
      {error && <p id={`${idPrefix}-slot-error`} role="alert" className={errorClass}>{error}</p>}
    </fieldset>
  )
}

function MonthCalendar({
  month,
  maxDaysAhead,
  freeDays,
  loading,
  chosen,
  onMonth,
  onPick,
  minMonth,
  idPrefix,
}: {
  month: Date
  maxDaysAhead: number
  freeDays: Set<string>
  loading: boolean
  chosen: string | null
  onMonth: (month: Date) => void
  onPick: (day: string) => void
  minMonth: Date
  idPrefix: string
}) {
  const { t, i18n } = useTranslation('event_booking')
  const language = i18n.language
  const last = new Date()
  last.setDate(last.getDate() + maxDaysAhead)
  const lastMonth = startOfMonth(last)
  const year = month.getFullYear()
  const number = month.getMonth()
  const offset = (new Date(year, number, 1).getDay() + 6) % 7 // Monday first
  const count = new Date(year, number + 1, 0).getDate()
  const weekdays = Array.from({ length: 7 }, (_, index) => new Date(2021, 0, 4 + index).toLocaleDateString(language, { weekday: 'short' }))
  const cells: (string | null)[] = [...Array(offset).fill(null), ...Array.from({ length: count }, (_, index) => isoDay(new Date(year, number, index + 1)))]

  return (
    <div className="max-w-xs" aria-busy={loading}>
      <div className="mb-2 flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={() => onMonth(new Date(year, number - 1, 1))}
          disabled={month <= minMonth}
          aria-label={t('picker.previousMonth')}
          className="rounded-lg border border-slate-200 px-3 py-1 text-sm disabled:opacity-30 dark:border-slate-700"
        >
          ‹
        </button>
        <span id={`${idPrefix}-month`} className="text-sm font-medium capitalize" aria-live="polite">
          {month.toLocaleDateString(language, { month: 'long', year: 'numeric' })}
        </span>
        <button
          type="button"
          onClick={() => onMonth(new Date(year, number + 1, 1))}
          disabled={month >= lastMonth}
          aria-label={t('picker.nextMonth')}
          className="rounded-lg border border-slate-200 px-3 py-1 text-sm disabled:opacity-30 dark:border-slate-700"
        >
          ›
        </button>
      </div>
      <div role="grid" aria-labelledby={`${idPrefix}-month`} className="grid grid-cols-7 gap-1 text-center text-sm">
        {weekdays.map((name) => (
          <div key={name} role="columnheader" className="pb-1 text-xs text-slate-500 dark:text-slate-400">{name}</div>
        ))}
        {cells.map((day, index) => {
          if (!day) return <div key={`blank-${index}`} role="gridcell" />
          const free = freeDays.has(day)
          const selected = day === chosen
          return (
            <button
              key={day}
              type="button"
              role="gridcell"
              disabled={!free}
              aria-pressed={selected}
              aria-label={`${formatDay(day, language)}${free ? '' : ` – ${t('picker.dayTaken')}`}`}
              onClick={() => onPick(day)}
              className={`h-10 rounded-lg ${
                selected
                  ? 'bg-slate-900 font-semibold text-slate-100 dark:bg-slate-100 dark:text-slate-900'
                  : free
                    ? 'border border-slate-300 bg-white hover:bg-slate-100 dark:border-slate-600 dark:bg-slate-900 dark:hover:bg-slate-800'
                    : 'text-slate-300 dark:text-slate-700'
              }`}
            >
              {Number(day.slice(8))}
            </button>
          )
        })}
      </div>
    </div>
  )
}
