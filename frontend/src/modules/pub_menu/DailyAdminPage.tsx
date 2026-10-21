/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { AllergenPicker } from './Allergens'
import {
  API_BASE,
  DAILY_KINDS,
  addDays,
  errorsOf,
  fetchJson,
  isoDay,
  longDate,
  mondayOf,
  parsePrice,
  priceText,
  query,
  sendJson,
  shortDate,
  statusOf,
  weekdayName,
  type DailyAdmin,
  type DailyItem,
  type DailyKind,
} from './api'
import {
  Section,
  ManageShell,
  dangerButtonClass,
  errorClass,
  labelClass,
  mutedClass,
  okClass,
  primaryButtonClass,
  secondaryButtonClass,
  smallInputClass,
} from './ui'

/**
 * /menu/manage - the lunch menu by date: a week at a time, each day a list of
 * dishes (soup, main courses, dessert, other) that stays a draft until it is
 * published. A day can be filled from another one (last week's, say) and edited
 * from there - nothing is stored until it is saved.
 */
export default function DailyAdminPage() {
  const { t } = useTranslation('pub_menu')
  return (
    <ManageShell title={t('manage.dailyTitle')}>
      <Week />
    </ManageShell>
  )
}

function Week() {
  const { t, i18n } = useTranslation('pub_menu')
  const language = i18n.resolvedLanguage ?? i18n.language
  const todayIso = useMemo(() => isoDay(new Date()), [])
  const [weekStart, setWeekStart] = useState(() => mondayOf(todayIso))
  const [days, setDays] = useState<Record<string, DailyAdmin>>({})
  const [selected, setSelected] = useState(todayIso)
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [reloadKey, setReloadKey] = useState(0)
  const [loadedWeek, setLoadedWeek] = useState<string | null>(null) // the week `days` belongs to: an editor made before it arrives would start empty
  const [resets, setResets] = useState(0) // bumped when a day is deleted, so its editor starts empty again

  useEffect(() => {
    let cancelled = false
    fetchJson<DailyAdmin[]>(`${API_BASE}/manage/daily${query({ date_from: weekStart, date_to: addDays(weekStart, 6) })}`)
      .then((found) => {
        if (cancelled) return
        setDays(Object.fromEntries(found.map((entry) => [entry.day, entry])))
        setLoadedWeek(weekStart)
        setState('ready')
      })
      .catch(() => !cancelled && setState('error'))
    return () => {
      cancelled = true
    }
  }, [weekStart, reloadKey])

  function moveWeek(delta: number) {
    const next = addDays(weekStart, delta * 7)
    setWeekStart(next)
    setSelected(next)
  }

  if (state === 'error') return <p role="alert" className={errorClass}>{t('manage.loadError')}</p>

  const week = Array.from({ length: 7 }, (_, index) => addDays(weekStart, index))
  const stored = days[selected]

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" onClick={() => moveWeek(-1)} aria-label={t('daily.previousWeek')} className={secondaryButtonClass}>‹</button>
        <span className="text-sm font-medium" aria-live="polite">{t('daily.week', { from: shortDate(week[0], language), to: shortDate(week[6], language) })}</span>
        <button type="button" onClick={() => moveWeek(1)} aria-label={t('daily.nextWeek')} className={secondaryButtonClass}>›</button>
        {mondayOf(todayIso) !== weekStart && (
          <button
            type="button"
            onClick={() => {
              setWeekStart(mondayOf(todayIso))
              setSelected(todayIso)
            }}
            className={secondaryButtonClass}
          >
            {t('daily.thisWeek')}
          </button>
        )}
        {state === 'loading' && <span className={mutedClass}>{t('common.loading')}</span>}
      </div>

      <ul className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
        {week.map((iso) => {
          const entry = days[iso]
          const active = selected === iso
          return (
            <li key={iso}>
              <button
                type="button"
                onClick={() => setSelected(iso)}
                aria-pressed={active}
                className={`flex h-full w-full flex-col items-start rounded-xl border p-3 text-left text-sm ${
                  active ? 'border-slate-900 bg-slate-900 text-slate-100 dark:border-slate-100 dark:bg-slate-100 dark:text-slate-900' : 'border-slate-200 hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800'
                }`}
              >
                <span className="font-medium capitalize">{weekdayName(iso, language)}</span>
                <span className="opacity-80">{shortDate(iso, language)}{iso === todayIso && ` · ${t('daily.today')}`}</span>
                <span className="mt-1 text-xs">
                  {!entry ? t('manage.dayNone') : entry.is_published ? t('manage.dayPublished', { count: entry.items.length }) : t('manage.dayDraft', { count: entry.items.length })}
                </span>
              </button>
            </li>
          )
        })}
      </ul>

      {loadedWeek === weekStart ? (
        <DayEditor
          key={`${selected}-${resets}`}
          day={selected}
          stored={stored}
          onChanged={() => setReloadKey((key) => key + 1)}
          onDeleted={() => {
            setDays((previous) => Object.fromEntries(Object.entries(previous).filter(([iso]) => iso !== selected)))
            setResets((count) => count + 1)
            setReloadKey((key) => key + 1)
          }}
        />
      ) : (
        <p className={mutedClass}>{t('common.loading')}</p>
      )}
    </div>
  )
}

interface Row {
  key: string
  kind: DailyKind
  name: string
  amount: string
  description: string
  allergens: number[]
  price: string
}

let rowCounter = 0

function newRow(partial: Partial<Row> = {}): Row {
  rowCounter += 1
  return { key: `row-${rowCounter}`, kind: 'main', name: '', amount: '', description: '', allergens: [], price: '', ...partial }
}

function rowsOf(items: DailyItem[]): Row[] {
  return items.map((item) => newRow({ kind: item.kind, name: item.name, amount: item.amount, description: item.description, allergens: item.allergens, price: priceText(item.price) }))
}

function DayEditor({ day, stored, onChanged, onDeleted }: { day: string; stored: DailyAdmin | undefined; onChanged: () => void; onDeleted: () => void }) {
  const { t, i18n } = useTranslation('pub_menu')
  const language = i18n.resolvedLanguage ?? i18n.language
  const [rows, setRows] = useState<Row[]>(() => rowsOf(stored?.items ?? []))
  const [published, setPublished] = useState(stored?.is_published ?? false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null)
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({})
  const [copyDate, setCopyDate] = useState('')

  function change(key: string, patch: Partial<Row>) {
    setRows((previous) => previous.map((row) => (row.key === key ? { ...row, ...patch } : row)))
    setMessage(null)
  }

  function move(index: number, delta: number) {
    setRows((previous) => {
      const next = [...previous]
      const target = index + delta
      if (target < 0 || target >= next.length) return previous
      ;[next[index], next[target]] = [next[target], next[index]]
      return next
    })
  }

  async function copyFrom(source: string) {
    setMessage(null)
    try {
      const found = await fetchJson<DailyAdmin[]>(`${API_BASE}/manage/daily${query({ date_from: source, date_to: source })}`)
      if (found.length === 0 || found[0].items.length === 0) {
        setMessage({ kind: 'error', text: t('editor.copyEmpty', { date: longDate(source, language) }) })
        return
      }
      setRows(rowsOf(found[0].items))
      setMessage({ kind: 'ok', text: t('editor.copied', { date: longDate(source, language) }) })
    } catch {
      setMessage({ kind: 'error', text: t('editor.copyFailed') })
    }
  }

  async function save(event: FormEvent) {
    event.preventDefault()
    const errors: Record<string, string> = {}
    const items = rows
      .filter((row) => row.name.trim() !== '')
      .map((row) => {
        const price = parsePrice(row.price)
        if (row.price.trim() !== '' && (price === null || price < 0)) errors[row.key] = 'price'
        return { kind: row.kind, name: row.name.trim(), amount: row.amount.trim(), description: row.description.trim(), allergens: row.allergens, price }
      })
    setRowErrors(errors)
    if (Object.keys(errors).length > 0) {
      setMessage({ kind: 'error', text: t('editor.priceInvalid') })
      return
    }
    setBusy(true)
    setMessage(null)
    try {
      await sendJson<DailyAdmin>(`${API_BASE}/manage/daily/${day}`, 'PUT', { is_published: published, items })
      setMessage({ kind: 'ok', text: published ? t('editor.savedPublished') : t('editor.savedDraft') })
      onChanged()
    } catch (err) {
      setMessage({ kind: 'error', text: statusOf(err) === 422 && Object.keys(errorsOf(err)).length > 0 ? t('editor.invalid') : t('errors.generic') })
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    if (!window.confirm(t('editor.deleteConfirm', { date: longDate(day, language) }))) return
    setBusy(true)
    try {
      await fetchJson<void>(`${API_BASE}/manage/daily/${day}`, { method: 'DELETE' })
      onDeleted()
    } catch {
      setMessage({ kind: 'error', text: t('errors.generic') })
    } finally {
      setBusy(false)
    }
  }

  return (
    <Section title={longDate(day, language)}>
      <form onSubmit={save} className="space-y-4">
        <div className="flex flex-wrap items-end gap-2">
          <button type="button" onClick={() => void copyFrom(addDays(day, -7))} className={secondaryButtonClass}>
            {t('editor.copyLastWeek')}
          </button>
          <div className="flex items-end gap-2">
            <div>
              <label htmlFor="copy-date" className={labelClass}>{t('editor.copyFrom')}</label>
              <input id="copy-date" type="date" value={copyDate} onChange={(e) => setCopyDate(e.target.value)} className={smallInputClass} />
            </div>
            <button type="button" disabled={!copyDate} onClick={() => void copyFrom(copyDate)} className={secondaryButtonClass}>
              {t('editor.copy')}
            </button>
          </div>
        </div>
        <p className={mutedClass}>{t('editor.copyHint')}</p>

        {rows.length === 0 && <p className={mutedClass}>{t('editor.noDishes')}</p>}
        <ul className="space-y-3">
          {rows.map((row, index) => (
            <li key={row.key} className="space-y-2 rounded-xl border border-slate-200 p-3 dark:border-slate-700">
              <div className="flex flex-wrap items-end gap-2">
                <div>
                  <label htmlFor={`${row.key}-kind`} className={labelClass}>{t('editor.kind')}</label>
                  <select id={`${row.key}-kind`} value={row.kind} onChange={(e) => change(row.key, { kind: e.target.value as DailyKind })} className={smallInputClass}>
                    {DAILY_KINDS.map((kind) => (
                      <option key={kind} value={kind}>{t(`daily.kindsOne.${kind}`)}</option>
                    ))}
                  </select>
                </div>
                <div className="min-w-48 flex-1">
                  <label htmlFor={`${row.key}-name`} className={labelClass}>{t('editor.name')}</label>
                  <input id={`${row.key}-name`} maxLength={150} value={row.name} onChange={(e) => change(row.key, { name: e.target.value })} className={`${smallInputClass} w-full`} />
                </div>
                <div className="w-28">
                  <label htmlFor={`${row.key}-amount`} className={labelClass}>{t('editor.amount')}</label>
                  <input id={`${row.key}-amount`} maxLength={50} value={row.amount} onChange={(e) => change(row.key, { amount: e.target.value })} placeholder="150 g" className={`${smallInputClass} w-full`} />
                </div>
                <div className="w-24">
                  <label htmlFor={`${row.key}-price`} className={labelClass}>{t('editor.price')}</label>
                  <input
                    id={`${row.key}-price`}
                    inputMode="decimal"
                    value={row.price}
                    onChange={(e) => change(row.key, { price: e.target.value })}
                    aria-invalid={rowErrors[row.key] ? true : undefined}
                    className={`${smallInputClass} w-full`}
                  />
                </div>
                <div className="flex gap-1 pb-0.5">
                  <button type="button" onClick={() => move(index, -1)} disabled={index === 0} aria-label={t('editor.moveUp')} className={secondaryButtonClass}>↑</button>
                  <button type="button" onClick={() => move(index, 1)} disabled={index === rows.length - 1} aria-label={t('editor.moveDown')} className={secondaryButtonClass}>↓</button>
                  <button type="button" onClick={() => setRows((previous) => previous.filter((entry) => entry.key !== row.key))} aria-label={t('editor.removeDish')} className={dangerButtonClass}>×</button>
                </div>
              </div>
              <div>
                <label htmlFor={`${row.key}-description`} className={labelClass}>{t('editor.description')}</label>
                <input id={`${row.key}-description`} maxLength={500} value={row.description} onChange={(e) => change(row.key, { description: e.target.value })} className={`${smallInputClass} w-full`} />
              </div>
              <AllergenPicker idPrefix={row.key} value={row.allergens} onChange={(allergens) => change(row.key, { allergens })} />
            </li>
          ))}
        </ul>
        <button type="button" onClick={() => setRows((previous) => [...previous, newRow({ kind: previous.length === 0 ? 'soup' : 'main' })])} className={secondaryButtonClass}>
          {t('editor.addDish')}
        </button>

        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" checked={published} onChange={(e) => { setPublished(e.target.checked); setMessage(null) }} className="mt-1" />
          <span>
            <span className="font-medium">{t('editor.publish')}</span>
            <span className={`block ${mutedClass}`}>{t('editor.publishHint')}</span>
          </span>
        </label>

        {message && <p role={message.kind === 'error' ? 'alert' : 'status'} className={message.kind === 'error' ? errorClass : okClass}>{message.text}</p>}
        <div className="flex flex-wrap gap-2">
          <button type="submit" disabled={busy} className={primaryButtonClass}>{busy ? t('common.saving') : t('common.save')}</button>
          {stored && (
            <button type="button" onClick={() => void remove()} disabled={busy} className={dangerButtonClass}>
              {t('editor.deleteDay')}
            </button>
          )}
        </div>
      </form>
    </Section>
  )
}
