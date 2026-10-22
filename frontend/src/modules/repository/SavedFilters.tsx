/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { deleteRequest, detailField, fieldErrors, sendJson, tableApi, type FilterDefinition, type SavedFilter, type TableDetail } from './api'
import { sameDefinition } from './filterModel'
import { ConfirmDialog, Modal, dangerButtonClass, errorTextClass, inputClass, labelClass, primaryButtonClass, secondaryButtonClass, useSaveErrorText } from './ui'

/** What the save dialog is for: a new filter, or replacing the active one (which may be renamed). */
type SaveMode = 'new' | 'update'

/**
 * The saved filters of a table as chips above the filter rows: a click puts a
 * filter's conditions, sort and deleted switch on the page, and the buttons next
 * to the chips save what is on the page as a new filter, replace the active one
 * with it, or delete the active one (refused while a statistic is based on it -
 * the answer names them). `current` is what the page shows now; the active
 * filter counts as changed when it no longer says the same.
 */
export default function SavedFilters({
  repositorySlug,
  table,
  filters,
  activeId,
  current,
  incomplete,
  onApply,
  onSaved,
  onDeleted,
}: {
  repositorySlug: string
  table: TableDetail
  filters: SavedFilter[]
  activeId: string | null
  current: FilterDefinition
  /** A filter row is not complete yet: it is not part of `current`, but the page no longer says what the saved filter says. */
  incomplete: boolean
  onApply: (filter: SavedFilter) => void
  onSaved: (filter: SavedFilter) => void
  onDeleted: () => void
}) {
  const { t } = useTranslation('repository')
  const saveErrorText = useSaveErrorText()
  const api = `${tableApi(repositorySlug, table.slug)}/filters`
  const active = filters.find((filter) => filter.id === activeId) ?? null
  const changed = active !== null && (incomplete || !sameDefinition(current, active.definition))
  const [saving, setSaving] = useState<SaveMode | null>(null)
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)

  function openSave(mode: SaveMode) {
    setSaving(mode)
    setName(mode === 'update' && active ? active.name : '')
    setError(null)
  }

  async function save(e: FormEvent) {
    e.preventDefault()
    if (!saving) return
    setBusy(true)
    setError(null)
    try {
      const body = { name: name.trim(), ...current }
      const saved =
        saving === 'update' && active
          ? await sendJson<SavedFilter>(`${api}/${active.id}`, 'PUT', body)
          : await sendJson<SavedFilter>(api, 'POST', body)
      setSaving(null)
      onSaved(saved)
    } catch (err) {
      setError(Object.keys(fieldErrors(err)).length ? t('filters.saved.invalid') : saveErrorText(err, 'filters.saved.saveError'))
    } finally {
      setBusy(false)
    }
  }

  async function confirmDelete(): Promise<string | null> {
    if (!active) return null
    try {
      await deleteRequest(`${api}/${active.id}`)
      setDeleting(false)
      onDeleted()
      return null
    } catch (err) {
      const inUse = detailField<{ id: string; name: string }[]>(err, 'in_use')
      return inUse?.length ? t('filters.saved.inUse', { by: inUse.map((statistic) => statistic.name).join(', ') }) : t('filters.saved.deleteError')
    }
  }

  return (
    <section aria-label={t('filters.saved.title')} className="flex flex-wrap items-center gap-2">
      <span className="text-sm font-medium text-slate-700 dark:text-slate-300">{t('filters.saved.title')}</span>
      {filters.length === 0 && <span className="text-sm text-slate-500 dark:text-slate-400">{t('filters.saved.none')}</span>}
      {filters.map((filter) => (
        <button
          key={filter.id}
          type="button"
          onClick={() => onApply(filter)}
          aria-pressed={filter.id === activeId}
          className={`repo-focus rounded-full border px-3 py-1 text-sm ${
            filter.id === activeId ? 'repo-accent-bg border-transparent' : 'repo-border bg-white text-slate-800 hover:bg-slate-100 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800'
          }`}
        >
          {filter.name}
          {filter.id === activeId && changed && <span aria-label={t('filters.saved.changed')}> •</span>}
        </button>
      ))}
      <button type="button" onClick={() => openSave('new')} className={secondaryButtonClass}>
        {t('filters.saved.saveNew')}
      </button>
      {active && changed && (
        <button type="button" onClick={() => openSave('update')} className={secondaryButtonClass}>
          {t('filters.saved.update', { name: active.name })}
        </button>
      )}
      {active && (
        <button type="button" onClick={() => setDeleting(true)} className={dangerButtonClass}>
          {t('filters.saved.delete', { name: active.name })}
        </button>
      )}

      {saving && (
        <Modal title={t(saving === 'new' ? 'filters.saved.saveNewTitle' : 'filters.saved.updateTitle')} onClose={() => setSaving(null)}>
          <form onSubmit={save} className="space-y-4">
            <div>
              <label htmlFor="saved-filter-name" className={labelClass}>
                {t('filters.saved.name')}
              </label>
              <input id="saved-filter-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} required className={inputClass} />
            </div>
            <p className="text-sm text-slate-600 dark:text-slate-400">{t('filters.saved.what', { conditions: current.conditions.length })}</p>
            {error && <p className={errorTextClass}>{error}</p>}
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setSaving(null)} className={secondaryButtonClass}>
                {t('common.cancel')}
              </button>
              <button type="submit" disabled={busy || name.trim() === ''} className={primaryButtonClass}>
                {busy ? t('common.saving') : t('common.save')}
              </button>
            </div>
          </form>
        </Modal>
      )}
      {deleting && active && (
        <ConfirmDialog
          title={t('filters.saved.deleteTitle', { name: active.name })}
          message={t('filters.saved.deleteMessage')}
          confirmLabel={t('common.delete')}
          danger
          onConfirm={confirmDelete}
          onClose={() => setDeleting(false)}
        />
      )}
    </section>
  )
}
