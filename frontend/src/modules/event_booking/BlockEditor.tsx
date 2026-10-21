/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  API_BASE,
  formatDay,
  formatTime,
  sendJson,
  type Block,
  type DaysMode,
  type PreviewResult,
  type TimeMode,
} from './api'
import { errorClass, inputClass, labelClass, mutedClass, secondaryButtonClass, smallInputClass } from './ui'

export const EMPTY_BLOCK: Block = {
  days_mode: 'dates',
  dates: [],
  weekdays: [],
  range_from: null,
  range_to: null,
  time_mode: 'all_day',
  times: [],
  slot_minutes: null,
  time_from: null,
  time_to: null,
  capacity: null,
}

/** A block as the server takes it: only the fields of its modes (the server refuses unknown ones and ignores nothing). */
export function blockPayload(block: Block): Block {
  return {
    days_mode: block.days_mode,
    dates: block.days_mode === 'dates' ? [...block.dates].sort() : [],
    weekdays: block.days_mode === 'weekdays' ? [...block.weekdays].sort() : [],
    range_from: block.days_mode === 'weekdays' ? block.range_from : null,
    range_to: block.days_mode === 'weekdays' ? block.range_to : null,
    time_mode: block.days_mode === 'any_future' ? 'all_day' : block.time_mode,
    times: block.time_mode === 'manual' && block.days_mode !== 'any_future' ? [...block.times].map(formatTime).sort() : [],
    slot_minutes: block.time_mode === 'generated' && block.days_mode !== 'any_future' ? block.slot_minutes : null,
    time_from: block.time_mode === 'generated' && block.days_mode !== 'any_future' ? block.time_from : null,
    time_to: block.time_mode === 'generated' && block.days_mode !== 'any_future' ? block.time_to : null,
    capacity: block.capacity,
  }
}

const DAYS_MODES: DaysMode[] = ['dates', 'weekdays', 'any_future']
const TIME_MODES: TimeMode[] = ['all_day', 'manual', 'generated']
const PREVIEW_DAYS = 14

function Chips({ items, label, onRemove }: { items: string[]; label: (item: string) => string; onRemove: (item: string) => void }) {
  const { t } = useTranslation('event_booking')
  if (items.length === 0) return null
  return (
    <ul className="flex flex-wrap gap-2">
      {items.map((item) => (
        <li key={item} className="flex items-center gap-1 rounded-full border border-slate-300 bg-white py-0.5 pl-3 pr-1 text-sm dark:border-slate-600 dark:bg-slate-900">
          {label(item)}
          <button type="button" onClick={() => onRemove(item)} aria-label={t('editor.remove', { item: label(item) })} className="rounded-full px-2 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800">
            ×
          </button>
        </li>
      ))}
    </ul>
  )
}

function AddOne({ type, label, onAdd }: { type: 'date' | 'time'; label: string; onAdd: (value: string) => void }) {
  const { t } = useTranslation('event_booking')
  const [value, setValue] = useState('')
  function add() {
    if (!value) return
    onAdd(value)
    setValue('')
  }
  return (
    <div className="flex flex-wrap items-end gap-2">
      <div>
        <label className={labelClass}>
          {label}
          <input type={type} value={value} onChange={(e) => setValue(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), add())} className={`${smallInputClass} mt-1 block`} />
        </label>
      </div>
      <button type="button" onClick={add} disabled={!value} className={secondaryButtonClass}>{t('editor.add')}</button>
    </div>
  )
}

function BlockCard({
  block,
  index,
  count,
  capacity,
  onChange,
  onRemove,
  onMove,
}: {
  block: Block
  index: number
  count: number
  capacity: number
  onChange: (block: Block) => void
  onRemove: () => void
  onMove: (direction: -1 | 1) => void
}) {
  const { t, i18n } = useTranslation('event_booking')
  const id = `block-${index}`
  const set = (patch: Partial<Block>) => onChange({ ...block, ...patch })
  const anyFuture = block.days_mode === 'any_future'
  const weekdayNames = Array.from({ length: 7 }, (_, day) => new Date(2021, 0, 4 + day).toLocaleDateString(i18n.language, { weekday: 'short' }))

  return (
    <fieldset className="space-y-4 rounded-xl border border-slate-200 p-4 dark:border-slate-700">
      <legend className="px-1 text-sm font-semibold">{t('editor.block', { number: index + 1 })}</legend>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-3">
          <div>
            <label htmlFor={`${id}-days`} className={labelClass}>{t('editor.daysMode')}</label>
            <select id={`${id}-days`} value={block.days_mode} onChange={(e) => set({ days_mode: e.target.value as DaysMode })} className={inputClass}>
              {DAYS_MODES.map((mode) => (
                <option key={mode} value={mode}>{t(`editor.daysModes.${mode}`)}</option>
              ))}
            </select>
          </div>

          {block.days_mode === 'dates' && (
            <div className="space-y-2">
              <AddOne type="date" label={t('editor.addDay')} onAdd={(day) => !block.dates.includes(day) && set({ dates: [...block.dates, day].sort() })} />
              <Chips items={block.dates} label={(day) => formatDay(day, i18n.language, 'short')} onRemove={(day) => set({ dates: block.dates.filter((other) => other !== day) })} />
            </div>
          )}

          {block.days_mode === 'weekdays' && (
            <div className="space-y-2">
              <div role="group" aria-label={t('editor.weekdays')} className="flex flex-wrap gap-2">
                {weekdayNames.map((name, day) => (
                  <label key={day} className="flex items-center gap-1 text-sm">
                    <input
                      type="checkbox"
                      checked={block.weekdays.includes(day)}
                      onChange={(e) => set({ weekdays: e.target.checked ? [...block.weekdays, day] : block.weekdays.filter((other) => other !== day) })}
                    />
                    {name}
                  </label>
                ))}
              </div>
              <div className="flex flex-wrap gap-3">
                <div>
                  <label htmlFor={`${id}-from`} className={labelClass}>{t('editor.rangeFrom')}</label>
                  <input id={`${id}-from`} type="date" value={block.range_from ?? ''} onChange={(e) => set({ range_from: e.target.value || null })} className={smallInputClass} />
                </div>
                <div>
                  <label htmlFor={`${id}-to`} className={labelClass}>{t('editor.rangeTo')}</label>
                  <input id={`${id}-to`} type="date" value={block.range_to ?? ''} onChange={(e) => set({ range_to: e.target.value || null })} className={smallInputClass} />
                </div>
              </div>
            </div>
          )}

          {anyFuture && <p className={mutedClass}>{t('editor.anyFutureHint')}</p>}
        </div>

        <div className="space-y-3">
          <div>
            <label htmlFor={`${id}-times`} className={labelClass}>{t('editor.timeMode')}</label>
            <select id={`${id}-times`} value={anyFuture ? 'all_day' : block.time_mode} disabled={anyFuture} onChange={(e) => set({ time_mode: e.target.value as TimeMode })} className={`${inputClass} disabled:opacity-60`}>
              {TIME_MODES.map((mode) => (
                <option key={mode} value={mode}>{t(`editor.timeModes.${mode}`)}</option>
              ))}
            </select>
          </div>

          {!anyFuture && block.time_mode === 'manual' && (
            <div className="space-y-2">
              <AddOne type="time" label={t('editor.addTime')} onAdd={(time) => !block.times.map(formatTime).includes(time) && set({ times: [...block.times, time].sort() })} />
              <Chips items={block.times.map(formatTime)} label={(time) => time} onRemove={(time) => set({ times: block.times.filter((other) => formatTime(other) !== time) })} />
            </div>
          )}

          {!anyFuture && block.time_mode === 'generated' && (
            <div className="flex flex-wrap gap-3">
              <div>
                <label htmlFor={`${id}-minutes`} className={labelClass}>{t('editor.slotMinutes')}</label>
                <input id={`${id}-minutes`} type="number" min={5} max={1440} value={block.slot_minutes ?? ''} onChange={(e) => set({ slot_minutes: e.target.value ? Number(e.target.value) : null })} className={`${smallInputClass} w-24`} />
              </div>
              <div>
                <label htmlFor={`${id}-tfrom`} className={labelClass}>{t('editor.timeFrom')}</label>
                <input id={`${id}-tfrom`} type="time" value={block.time_from ? formatTime(block.time_from) : ''} onChange={(e) => set({ time_from: e.target.value || null })} className={smallInputClass} />
              </div>
              <div>
                <label htmlFor={`${id}-tto`} className={labelClass}>{t('editor.timeTo')}</label>
                <input id={`${id}-tto`} type="time" value={block.time_to ? formatTime(block.time_to) : ''} onChange={(e) => set({ time_to: e.target.value || null })} className={smallInputClass} />
              </div>
            </div>
          )}

          <div>
            <label htmlFor={`${id}-capacity`} className={labelClass}>{t('editor.blockCapacity')}</label>
            <input
              id={`${id}-capacity`}
              type="number"
              min={1}
              max={1000}
              value={block.capacity ?? ''}
              placeholder={String(capacity)}
              onChange={(e) => set({ capacity: e.target.value ? Number(e.target.value) : null })}
              className={`${smallInputClass} w-24`}
            />
            <p className={`mt-1 ${mutedClass}`}>{t('editor.blockCapacityHint')}</p>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={() => onMove(-1)} disabled={index === 0} className={secondaryButtonClass}>{t('editor.moveUp')}</button>
        <button type="button" onClick={() => onMove(1)} disabled={index === count - 1} className={secondaryButtonClass}>{t('editor.moveDown')}</button>
        <button type="button" onClick={onRemove} className="rounded-lg px-3 py-1.5 text-sm text-red-600 dark:text-red-400">{t('editor.removeBlock')}</button>
      </div>
    </fieldset>
  )
}

/** What the blocks would offer, from the server (the same function that serves the visitors), as they are edited. */
function Preview({ blocks, capacity }: { blocks: Block[]; capacity: number }) {
  const { t, i18n } = useTranslation('event_booking')
  const [result, setResult] = useState<PreviewResult | null>(null)
  const [failed, setFailed] = useState(false)

  const key = JSON.stringify([blocks.map(blockPayload), capacity])
  useEffect(() => {
    let cancelled = false
    const timer = setTimeout(() => {
      sendJson<PreviewResult>(`${API_BASE}/manage/preview-slots`, 'POST', { blocks: blocks.map(blockPayload), capacity })
        .then((found) => !cancelled && (setResult(found), setFailed(false)))
        .catch(() => !cancelled && setFailed(true))
    }, 400)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
    // `key` is the content of blocks and capacity; the arrays themselves change identity on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  const byDay = new Map<string, string[]>()
  for (const slot of result?.slots ?? []) {
    const list = byDay.get(slot.date) ?? []
    list.push(slot.time ? formatTime(slot.time) : t('picker.allDay'))
    byDay.set(slot.date, list)
  }
  const days = [...byDay.entries()]
  const shownDays = days.slice(0, PREVIEW_DAYS)
  const hiddenSlots = (result?.total ?? 0) - shownDays.reduce((sum, [, times]) => sum + times.length, 0)

  return (
    <section aria-label={t('editor.previewTitle')} aria-live="polite" className="rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-950">
      <h3 className="mb-2 text-sm font-semibold">{t('editor.previewTitle')}</h3>
      {failed && <p className={errorClass}>{t('editor.previewFailed')}</p>}
      {result === null && !failed && <p className={mutedClass}>{t('common.loading')}</p>}
      {result && result.problems.length > 0 && (
        <ul role="alert" className={`list-disc space-y-1 pl-5 ${errorClass}`}>
          {result.problems.map((problem) => (
            <li key={problem}>{problem}</li>
          ))}
        </ul>
      )}
      {result && result.problems.length === 0 && (
        <>
          {blocks.length === 0 && <p className={`mb-2 ${mutedClass}`}>{t('editor.noBlocksHint')}</p>}
          {days.length === 0 && <p className={mutedClass}>{t('editor.previewEmpty')}</p>}
          <ul className="space-y-1 text-sm">
            {shownDays.map(([day, times]) => (
              <li key={day}>
                <span className="font-medium">{formatDay(day, i18n.language, 'short')}</span>
                <span className="ml-2 text-slate-600 dark:text-slate-300">{times.join(', ')}</span>
              </li>
            ))}
          </ul>
          {hiddenSlots > 0 && <p className={`mt-2 ${mutedClass}`}>{t('editor.previewMore', { count: hiddenSlots })}</p>}
          <p className={`mt-2 ${mutedClass}`}>{t('editor.previewTotal', { count: result.total })}</p>
        </>
      )}
    </section>
  )
}

/**
 * The blocks of a registration's offer - which days and which times people
 * can book, each block optionally with a capacity of its own - with the
 * resulting slots shown live underneath.
 */
export default function BlockEditor({ blocks, capacity, onChange }: { blocks: Block[]; capacity: number; onChange: (blocks: Block[]) => void }) {
  const { t } = useTranslation('event_booking')

  function move(index: number, direction: -1 | 1) {
    const next = [...blocks]
    ;[next[index], next[index + direction]] = [next[index + direction], next[index]]
    onChange(next)
  }

  return (
    <div className="space-y-4">
      <p className={mutedClass}>{t('editor.intro')}</p>
      {blocks.map((block, index) => (
        <BlockCard
          // Blocks have no id before they are saved; the editor only ever reorders or removes them, so the position is a stable enough key.
          key={index}
          block={block}
          index={index}
          count={blocks.length}
          capacity={capacity}
          onChange={(changed) => onChange(blocks.map((other, at) => (at === index ? changed : other)))}
          onRemove={() => onChange(blocks.filter((_, at) => at !== index))}
          onMove={(direction) => move(index, direction)}
        />
      ))}
      <button type="button" onClick={() => onChange([...blocks, { ...EMPTY_BLOCK }])} className={secondaryButtonClass}>{t('editor.addBlock')}</button>
      <Preview blocks={blocks} capacity={capacity} />
    </div>
  )
}
