/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import {
  API_BASE,
  conflictOf,
  errorsOf,
  fetchJson,
  formatDay,
  formatTime,
  isoDay,
  sendJson,
  statusOf,
  weekdayName,
  type Conflict,
  type ExceptionDay,
  type WeekdayHours,
} from './api'
import { ConflictBox, ExceptionForm, Section, useErrorText } from './admin'
import { errorClass, inputClass, labelClass, mutedClass, okClass, primaryButtonClass, secondaryButtonClass, ManageShell } from './ui'

/**
 * /reservations/manage/hours - the regular opening hours of each weekday and the
 * one-off changes of a date (closed, or other hours). Neither can leave an
 * upcoming reservation outside the hours: such a change is refused with the
 * reservations that stand in the way, which the pub cancels one by one (each with
 * a message to the guest) before saving it again.
 */
export default function HoursPage() {
  const { t } = useTranslation('table_reservations')
  return (
    <ManageShell title={t('manage.hoursTitle')}>
      <div className="space-y-6">
        <WeeklyHours />
        <Exceptions />
      </div>
    </ManageShell>
  )
}

interface DraftDay {
  weekday: number
  is_closed: boolean
  opens: string
  closes: string
}

function toDraft(week: WeekdayHours[]): DraftDay[] {
  return week.map((entry) => ({
    weekday: entry.weekday,
    is_closed: entry.is_closed,
    opens: entry.opens ? formatTime(entry.opens) : '10:00',
    closes: entry.closes ? formatTime(entry.closes) : '22:00',
  }))
}

function WeeklyHours() {
  const { t, i18n } = useTranslation('table_reservations')
  const language = i18n.resolvedLanguage ?? i18n.language
  const errorText = useErrorText()
  const [draft, setDraft] = useState<DraftDay[] | null>(null)
  const [loadFailed, setLoadFailed] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [general, setGeneral] = useState<string | null>(null)
  const [conflict, setConflict] = useState<{ id: number; data: Conflict } | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchJson<WeekdayHours[]>(`${API_BASE}/manage/opening-hours`)
      .then((week) => !cancelled && setDraft(toDraft(week)))
      .catch(() => !cancelled && setLoadFailed(true))
    return () => {
      cancelled = true
    }
  }, [])

  function change(weekday: number, patch: Partial<DraftDay>) {
    setDraft((previous) => previous && previous.map((entry) => (entry.weekday === weekday ? { ...entry, ...patch } : entry)))
    setSaved(false)
  }

  async function save(event: FormEvent) {
    event.preventDefault()
    if (!draft) return
    setSaving(true)
    setErrors({})
    setGeneral(null)
    setSaved(false)
    try {
      const week = await sendJson<WeekdayHours[]>(`${API_BASE}/manage/opening-hours`, 'PUT', {
        days: draft.map((entry) => ({
          weekday: entry.weekday,
          is_closed: entry.is_closed,
          opens: entry.is_closed ? null : entry.opens,
          closes: entry.is_closed ? null : entry.closes,
        })),
      })
      setDraft(toDraft(week))
      setConflict(null)
      setSaved(true)
    } catch (err) {
      const found = conflictOf(err)
      if (found) setConflict({ id: Date.now(), data: found })
      else if (statusOf(err) === 422 && Object.keys(errorsOf(err)).length > 0) setErrors(errorsOf(err))
      else setGeneral(t('errors.generic'))
    } finally {
      setSaving(false)
    }
  }

  if (loadFailed) return <p role="alert" className={errorClass}>{t('hoursPage.loadError')}</p>
  if (!draft) return <p className={mutedClass}>{t('common.loading')}</p>

  return (
    <Section title={t('hoursPage.weeklyTitle')}>
      <p className={mutedClass}>{t('hoursPage.weeklyHint')}</p>
      <form onSubmit={save} className="space-y-3">
        <ul className="divide-y divide-slate-200 dark:divide-slate-800">
          {draft.map((entry) => {
            const problem = errors[`weekday_${entry.weekday}_opens`] ?? errors[`weekday_${entry.weekday}_closes`]
            return (
              <li key={entry.weekday} className="flex flex-wrap items-center gap-x-4 gap-y-2 py-2">
                <span className="w-28 font-medium capitalize">{weekdayName(entry.weekday, language)}</span>
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={entry.is_closed} onChange={(e) => change(entry.weekday, { is_closed: e.target.checked })} />
                  {t('hours.closed')}
                </label>
                <div className="flex items-center gap-2">
                  <label className="sr-only" htmlFor={`opens-${entry.weekday}`}>{t('hoursPage.opens')}</label>
                  <input id={`opens-${entry.weekday}`} type="time" required={!entry.is_closed} disabled={entry.is_closed} value={entry.opens} onChange={(e) => change(entry.weekday, { opens: e.target.value })} className={`${inputClass} w-32`} />
                  <span aria-hidden="true">–</span>
                  <label className="sr-only" htmlFor={`closes-${entry.weekday}`}>{t('hoursPage.closes')}</label>
                  <input id={`closes-${entry.weekday}`} type="time" required={!entry.is_closed} disabled={entry.is_closed} value={entry.closes} onChange={(e) => change(entry.weekday, { closes: e.target.value })} className={`${inputClass} w-32`} />
                </div>
                {problem && <p role="alert" className={errorClass}>{errorText(problem)}</p>}
              </li>
            )
          })}
        </ul>
        {general && <p role="alert" className={errorClass}>{general}</p>}
        {saved && <p role="status" className={okClass}>{t('hoursPage.saved')}</p>}
        <button type="submit" disabled={saving} className={primaryButtonClass}>
          {saving ? t('common.saving') : t('hoursPage.save')}
        </button>
      </form>
      {conflict && <ConflictBox key={conflict.id} conflict={conflict.data} />}
    </Section>
  )
}

function Exceptions() {
  const { t, i18n } = useTranslation('table_reservations')
  const language = i18n.resolvedLanguage ?? i18n.language
  const todayIso = useMemo(() => isoDay(new Date()), [])
  const [list, setList] = useState<ExceptionDay[]>([])
  const [loadFailed, setLoadFailed] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const [date, setDate] = useState('')

  useEffect(() => {
    let cancelled = false
    fetchJson<ExceptionDay[]>(`${API_BASE}/manage/exceptions`)
      .then((found) => {
        if (cancelled) return
        setList(found)
        setLoadFailed(false)
      })
      .catch(() => !cancelled && setLoadFailed(true))
    return () => {
      cancelled = true
    }
  }, [reloadKey])

  const existing = list.find((entry) => entry.day === date) ?? null

  return (
    <Section title={t('hoursPage.exceptionsTitle')}>
      <p className={mutedClass}>{t('hoursPage.exceptionsHint')}</p>
      {loadFailed && <p role="alert" className={errorClass}>{t('hoursPage.loadError')}</p>}
      {list.length === 0 && !loadFailed ? (
        <p className={mutedClass}>{t('hoursPage.noExceptions')}</p>
      ) : (
        <ul className="divide-y divide-slate-200 text-sm dark:divide-slate-800">
          {list.map((entry) => (
            <li key={entry.day} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <span>
                <span className="font-medium">{formatDay(entry.day, language)}</span>
                {': '}
                {entry.is_closed || !entry.opens || !entry.closes ? t('hours.closed') : `${formatTime(entry.opens)}–${formatTime(entry.closes)}`}
                {entry.reason && <span className={mutedClass}> – {entry.reason}</span>}
              </span>
              <button type="button" onClick={() => setDate(entry.day)} className={secondaryButtonClass}>
                {t('hoursPage.editException')}
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="space-y-3 border-t border-slate-200 pt-4 dark:border-slate-800">
        <h3 className="font-medium">{t('hoursPage.addException')}</h3>
        <div>
          <label htmlFor="exception-date" className={labelClass}>{t('hoursPage.date')}</label>
          <input id="exception-date" type="date" min={todayIso} value={date} onChange={(e) => setDate(e.target.value)} className={`${inputClass} max-w-48`} />
        </div>
        {date && date >= todayIso && (
          <ExceptionForm
            key={`${date}-${existing ? 'x' : 'new'}`}
            day={date}
            existing={existing}
            onSaved={() => {
              setReloadKey((key) => key + 1)
            }}
            onChanged={() => setReloadKey((key) => key + 1)}
          />
        )}
      </div>
    </Section>
  )
}
