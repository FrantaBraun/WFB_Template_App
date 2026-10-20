/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import usePageMeta from '../../hooks/usePageMeta'
import { API_BASE, ARTICLES_PATH, fetchJson, type ArticleType, type ArticleTypeAdmin } from './api'
import { ArticlesGate, inputClass, labelClass, primaryButtonClass, secondaryButtonClass } from './ui'

type Colors = Pick<ArticleType, 'border_light' | 'background_light' | 'border_dark' | 'background_dark'>

const NEW_COLORS: Colors = {
  border_light: '#38bdf8',
  background_light: '#e0f2fe',
  border_dark: '#0ea5e9',
  background_dark: '#0c4a6e',
}

const COLOR_FIELDS = ['border_light', 'background_light', 'border_dark', 'background_dark'] as const

/** Just the four colours of a type - so spreading the result into a payload can't carry its name, id or count along. */
function pickColors(source: Colors): Colors {
  return {
    border_light: source.border_light,
    background_light: source.background_light,
    border_dark: source.border_dark,
    background_dark: source.background_dark,
  }
}

/** What an article of this type looks like in each theme - drawn from the colours themselves, not the active theme. */
function Preview({ colors, label }: { colors: Colors; label: string }) {
  const { t } = useTranslation('articles')
  return (
    <div className="grid grid-cols-2 gap-2 text-xs">
      <div className="rounded-lg border-2 px-2 py-1.5 text-slate-900" style={{ borderColor: colors.border_light, backgroundColor: colors.background_light }}>
        {t('types.previewLight')}: {label || '…'}
      </div>
      <div className="rounded-lg border-2 px-2 py-1.5 text-slate-100" style={{ borderColor: colors.border_dark, backgroundColor: colors.background_dark }}>
        {t('types.previewDark')}: {label || '…'}
      </div>
    </div>
  )
}

function ColorInputs({ value, onChange }: { value: Colors; onChange: (next: Colors) => void }) {
  const { t } = useTranslation('articles')
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {COLOR_FIELDS.map((field) => (
        <label key={field} className="text-sm text-slate-600 dark:text-slate-400">
          <span className="mb-1 block">{t(`types.${field}`)}</span>
          <input
            type="color"
            value={value[field]}
            onChange={(e) => onChange({ ...value, [field]: e.target.value })}
            className="h-9 w-full cursor-pointer rounded border border-slate-200 dark:border-slate-800"
          />
        </label>
      ))}
    </div>
  )
}

function TypeRow({ type, others, onChanged }: { type: ArticleTypeAdmin; others: ArticleTypeAdmin[]; onChanged: () => void }) {
  const { t } = useTranslation('articles')
  const [name, setName] = useState(type.name)
  const [colors, setColors] = useState<Colors>(pickColors(type))
  const [replaceWith, setReplaceWith] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null)

  async function save() {
    setBusy(true)
    setMessage(null)
    try {
      await fetchJson(`${API_BASE}/manage/types/${type.id}`, { method: 'PATCH', body: JSON.stringify({ name, ...colors }) })
      setMessage({ kind: 'ok', text: t('types.saved') })
      onChanged()
    } catch (err) {
      setMessage({ kind: 'error', text: (err as { status?: number }).status === 409 ? t('types.nameTaken') : t('types.saveError') })
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    const used = type.article_count > 0
    if (used && !replaceWith) return
    if (!window.confirm(used ? t('types.confirmDeleteUsed', { count: type.article_count }) : t('types.confirmDelete'))) return
    setBusy(true)
    setMessage(null)
    try {
      await fetchJson(`${API_BASE}/manage/types/${type.id}${used ? `?replace_with=${replaceWith}` : ''}`, { method: 'DELETE' })
      onChanged()
    } catch {
      setMessage({ kind: 'error', text: t('types.deleteError') })
      setBusy(false)
    }
  }

  return (
    <li className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-0 flex-1">
          <label htmlFor={`type-name-${type.id}`} className={labelClass}>{t('types.name')}</label>
          <input id={`type-name-${type.id}`} value={name} maxLength={100} onChange={(e) => setName(e.target.value)} className={inputClass} />
        </div>
        <span className="pb-2 text-xs text-slate-500 dark:text-slate-400">{t('types.articleCount', { count: type.article_count })}</span>
      </div>
      <ColorInputs value={colors} onChange={setColors} />
      <Preview colors={colors} label={name} />
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" onClick={save} disabled={busy || !name.trim()} className={primaryButtonClass}>{t('form.save')}</button>
        {type.article_count > 0 && (
          <select value={replaceWith} onChange={(e) => setReplaceWith(e.target.value)} aria-label={t('types.replaceWith')} className={`${inputClass} w-auto py-1.5 text-sm`}>
            <option value="">{t('types.replaceWith')}</option>
            {others.map((other) => (
              <option key={other.id} value={other.id}>{other.name}</option>
            ))}
          </select>
        )}
        <button type="button" onClick={remove} disabled={busy || (type.article_count > 0 && !replaceWith)} className="rounded-lg px-3 py-1.5 text-sm text-red-600 disabled:opacity-40 dark:text-red-400">
          {t('types.delete')}
        </button>
        {message && <span role="status" className={`text-sm ${message.kind === 'ok' ? 'text-emerald-700 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>{message.text}</span>}
      </div>
    </li>
  )
}

function NewTypeForm({ onCreated }: { onCreated: () => void }) {
  const { t } = useTranslation('articles')
  const [name, setName] = useState('')
  const [colors, setColors] = useState<Colors>(NEW_COLORS)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setMessage(null)
    try {
      await fetchJson(`${API_BASE}/manage/types`, { method: 'POST', body: JSON.stringify({ name, ...colors }) })
      setName('')
      onCreated()
    } catch (err) {
      setMessage((err as { status?: number }).status === 409 ? t('types.nameTaken') : t('types.saveError'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3 rounded-2xl border border-dashed border-slate-300 p-4 dark:border-slate-700">
      <h2 className="font-medium">{t('types.newTitle')}</h2>
      <div>
        <label htmlFor="type-new-name" className={labelClass}>{t('types.name')}</label>
        <input id="type-new-name" required value={name} maxLength={100} onChange={(e) => setName(e.target.value)} className={inputClass} />
      </div>
      <ColorInputs value={colors} onChange={setColors} />
      <Preview colors={colors} label={name} />
      <div className="flex items-center gap-3">
        <button type="submit" disabled={busy || !name.trim()} className={primaryButtonClass}>{t('types.create')}</button>
        {message && <span role="alert" className="text-sm text-red-600 dark:text-red-400">{message}</span>}
      </div>
    </form>
  )
}

function TypesManager() {
  const { t } = useTranslation('articles')
  const [types, setTypes] = useState<ArticleTypeAdmin[] | null>(null)
  const [error, setError] = useState(false)

  const reload = useCallback(() => {
    fetchJson<ArticleTypeAdmin[]>(`${API_BASE}/manage/types`)
      .then((rows) => {
        setTypes(rows)
        setError(false)
      })
      .catch(() => setError(true))
  }, [])

  useEffect(reload, [reload])

  return (
    <div className="mx-auto max-w-4xl space-y-6 px-6 py-12 text-slate-900 dark:text-slate-100">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-3xl font-semibold tracking-tight">{t('types.title')}</h1>
        <Link to={`${ARTICLES_PATH}/manage`} className={secondaryButtonClass}>{t('form.backToList')}</Link>
      </div>
      <p className="text-sm text-slate-600 dark:text-slate-400">{t('types.intro')}</p>
      {error && <p className="text-sm text-red-600 dark:text-red-400">{t('list.error')}</p>}
      {types === null && !error && <p className="text-slate-500 dark:text-slate-400">{t('common.loading')}</p>}
      {types && types.length === 0 && <p className="text-slate-500 dark:text-slate-400">{t('types.empty')}</p>}
      {types && types.length > 0 && (
        <ul className="space-y-4">
          {types.map((type) => (
            // Keyed by id and updated-colours so a reload after save re-seeds the row from the server's copy.
            <TypeRow key={`${type.id}-${type.name}-${COLOR_FIELDS.map((f) => type[f]).join('')}`} type={type} others={types.filter((o) => o.id !== type.id)} onChanged={reload} />
          ))}
        </ul>
      )}
      <NewTypeForm onCreated={reload} />
    </div>
  )
}

/** /articles/manage/types - define the article types and their colours. */
export default function ManageTypesPage() {
  const { t } = useTranslation('articles')
  usePageMeta({ title: t('types.title') })
  return (
    <ArticlesGate>
      <TypesManager />
    </ArticlesGate>
  )
}
