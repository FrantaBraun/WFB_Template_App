/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { API_BASE, conflictOf, errorsOf, fetchJson, sendJson, statusOf, type Conflict, type TableRow } from './api'
import { ConflictBox, Section, useErrorText } from './admin'
import { dangerButtonClass, errorClass, inputClass, labelClass, mutedClass, okClass, primaryButtonClass, secondaryButtonClass, ManageShell } from './ui'

/**
 * /reservations/manage/tables - the tables of the pub. Guests never choose a
 * table: the system gives each party the smallest free one that seats them, so
 * what matters here is how many each seats. Taking a table out of use, or seating
 * fewer people, is refused while an upcoming reservation would no longer fit (the
 * pub cancels those first, from the list shown); a table that ever had a
 * reservation is taken out of use instead of deleted.
 */
export default function TablesPage() {
  const { t } = useTranslation('table_reservations')
  return (
    <ManageShell title={t('manage.tablesTitle')}>
      <Tables />
    </ManageShell>
  )
}

function Tables() {
  const { t } = useTranslation('table_reservations')
  const [tables, setTables] = useState<TableRow[] | null>(null)
  const [loadFailed, setLoadFailed] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    fetchJson<TableRow[]>(`${API_BASE}/manage/tables`)
      .then((found) => {
        if (cancelled) return
        setTables(found)
        setLoadFailed(false)
      })
      .catch(() => !cancelled && setLoadFailed(true))
    return () => {
      cancelled = true
    }
  }, [reloadKey])

  const reload = () => setReloadKey((key) => key + 1)

  if (loadFailed) return <p role="alert" className={errorClass}>{t('tablesPage.loadError')}</p>
  if (!tables) return <p className={mutedClass}>{t('common.loading')}</p>

  const seatsInUse = tables.filter((table) => table.is_active).reduce((sum, table) => sum + table.seats, 0)

  return (
    <div className="space-y-6">
      <Section title={t('tablesPage.title')}>
        <p className={mutedClass}>{t('tablesPage.hint')}</p>
        {tables.length === 0 ? (
          <p className={mutedClass}>{t('tablesPage.none')}</p>
        ) : (
          <>
            <ul className="space-y-3">
              {tables.map((table) => (
                <TableEditor key={table.id} table={table} onChanged={reload} />
              ))}
            </ul>
            <p className={mutedClass}>{t('tablesPage.total', { tables: tables.filter((table) => table.is_active).length, seats: seatsInUse })}</p>
          </>
        )}
      </Section>
      <Section title={t('tablesPage.addTitle')}>
        <NewTable nextPosition={tables.length === 0 ? 0 : Math.max(...tables.map((table) => table.position)) + 1} onAdded={reload} />
      </Section>
    </div>
  )
}

function TableEditor({ table, onChanged }: { table: TableRow; onChanged: () => void }) {
  const { t } = useTranslation('table_reservations')
  const errorText = useErrorText()
  const [name, setName] = useState(table.name)
  const [seats, setSeats] = useState(String(table.seats))
  const [position, setPosition] = useState(String(table.position))
  const [active, setActive] = useState(table.is_active)
  const [busy, setBusy] = useState(false)
  const [saved, setSaved] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [general, setGeneral] = useState<string | null>(null)
  const [conflict, setConflict] = useState<{ id: number; data: Conflict } | null>(null)

  const dirty = name !== table.name || Number(seats) !== table.seats || Number(position) !== table.position || active !== table.is_active

  async function run(action: () => Promise<void>, done: 'saved' | 'removed') {
    setBusy(true)
    setErrors({})
    setGeneral(null)
    setSaved(false)
    try {
      await action()
      setConflict(null)
      if (done === 'saved') setSaved(true)
      onChanged()
    } catch (err) {
      const found = conflictOf(err)
      if (found) setConflict({ id: Date.now(), data: found })
      else if (statusOf(err) === 409 || statusOf(err) === 422) setErrors(errorsOf(err))
      else setGeneral(t('errors.generic'))
    } finally {
      setBusy(false)
    }
  }

  function save(event: FormEvent) {
    event.preventDefault()
    void run(async () => {
      await sendJson<TableRow>(`${API_BASE}/manage/tables/${table.id}`, 'PATCH', {
        name: name.trim(),
        seats: Number(seats),
        position: Number(position),
        is_active: active,
      })
    }, 'saved')
  }

  function remove() {
    if (!window.confirm(t('tablesPage.deleteConfirm', { name: table.name }))) return
    void run(async () => {
      await fetchJson<void>(`${API_BASE}/manage/tables/${table.id}`, { method: 'DELETE' })
    }, 'removed')
  }

  return (
    <li className={`rounded-xl border p-3 ${table.is_active ? 'border-slate-200 dark:border-slate-700' : 'border-slate-200 bg-slate-50 text-slate-500 dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-400'}`}>
      <form onSubmit={save} className="flex flex-wrap items-end gap-3">
        <div className="min-w-40 flex-1">
          <label htmlFor={`table-name-${table.id}`} className={labelClass}>{t('tablesPage.name')}</label>
          <input id={`table-name-${table.id}`} required maxLength={100} value={name} onChange={(e) => setName(e.target.value)} className={inputClass} />
        </div>
        <div className="w-24">
          <label htmlFor={`table-seats-${table.id}`} className={labelClass}>{t('tablesPage.seats')}</label>
          <input id={`table-seats-${table.id}`} type="number" required min={1} max={50} value={seats} onChange={(e) => setSeats(e.target.value)} className={inputClass} />
        </div>
        <div className="w-24">
          <label htmlFor={`table-position-${table.id}`} className={labelClass}>{t('tablesPage.position')}</label>
          <input id={`table-position-${table.id}`} type="number" min={0} value={position} onChange={(e) => setPosition(e.target.value)} className={inputClass} />
        </div>
        <label className="flex items-center gap-2 pb-2 text-sm">
          <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
          {t('tablesPage.active')}
        </label>
        <div className="flex gap-2 pb-0.5">
          <button type="submit" disabled={busy || !dirty} className={primaryButtonClass}>
            {busy ? t('common.saving') : t('common.save')}
          </button>
          <button type="button" onClick={remove} disabled={busy} className={dangerButtonClass}>
            {t('tablesPage.delete')}
          </button>
        </div>
      </form>
      <p className={`mt-2 ${mutedClass}`}>{t('tablesPage.upcoming', { count: table.upcoming_count })}</p>
      {Object.entries(errors).map(([field, code]) => (
        <p key={field} role="alert" className={`mt-1 ${errorClass}`}>{errorText(code)}</p>
      ))}
      {general && <p role="alert" className={`mt-1 ${errorClass}`}>{general}</p>}
      {saved && <p role="status" className={`mt-1 ${okClass}`}>{t('tablesPage.saved')}</p>}
      {conflict && (
        <div className="mt-3">
          <ConflictBox key={conflict.id} conflict={conflict.data} onChanged={onChanged} />
        </div>
      )}
    </li>
  )
}

function NewTable({ nextPosition, onAdded }: { nextPosition: number; onAdded: () => void }) {
  const { t } = useTranslation('table_reservations')
  const errorText = useErrorText()
  const [name, setName] = useState('')
  const [seats, setSeats] = useState('4')
  const [busy, setBusy] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [general, setGeneral] = useState<string | null>(null)

  async function add(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setErrors({})
    setGeneral(null)
    try {
      await sendJson<TableRow>(`${API_BASE}/manage/tables`, 'POST', { name: name.trim(), seats: Number(seats), position: nextPosition, is_active: true })
      setName('')
      onAdded()
    } catch (err) {
      if (statusOf(err) === 422 && Object.keys(errorsOf(err)).length > 0) setErrors(errorsOf(err))
      else setGeneral(t('errors.generic'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={add} className="flex flex-wrap items-end gap-3">
      <div className="min-w-40 flex-1">
        <label htmlFor="new-table-name" className={labelClass}>{t('tablesPage.name')}</label>
        <input id="new-table-name" required maxLength={100} value={name} onChange={(e) => setName(e.target.value)} placeholder={t('tablesPage.namePlaceholder')} className={inputClass} />
      </div>
      <div className="w-24">
        <label htmlFor="new-table-seats" className={labelClass}>{t('tablesPage.seats')}</label>
        <input id="new-table-seats" type="number" required min={1} max={50} value={seats} onChange={(e) => setSeats(e.target.value)} className={inputClass} />
      </div>
      <button type="submit" disabled={busy} className={secondaryButtonClass}>
        {busy ? t('common.saving') : t('tablesPage.add')}
      </button>
      {Object.entries(errors).map(([field, code]) => (
        <p key={field} role="alert" className={`w-full ${errorClass}`}>{errorText(code)}</p>
      ))}
      {general && <p role="alert" className={`w-full ${errorClass}`}>{general}</p>}
    </form>
  )
}
