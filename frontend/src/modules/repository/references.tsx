/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useRepositoryArea } from './areaContext'
import { fetchJson, recordPath, tableApi, type RecordHit, type RecordHitPage, type RefInfo } from './api'
import { Modal, inputClass, secondaryButtonClass } from './ui'

const SEARCH_DEBOUNCE_MS = 250

/** A link to the record a reference points at: its name with an arrow that opens it in a new tab. A deleted record is struck through. */
export function RefLink({ info }: { info: RefInfo | undefined }) {
  const { t } = useTranslation('repository')
  const { repository } = useRepositoryArea()
  if (!info) return <span className="text-slate-500 dark:text-slate-400">{t('reference.unknown')}</span>
  return (
    <span className="inline-flex max-w-full items-center gap-1">
      <span className={`truncate ${info.deleted ? 'text-slate-500 line-through dark:text-slate-400' : ''}`}>{info.name}</span>
      {info.deleted && (
        <span className="shrink-0 rounded-full bg-slate-200 px-1.5 text-xs text-slate-600 dark:bg-slate-700 dark:text-slate-300">{t('record.deletedBadge')}</span>
      )}
      <a
        href={recordPath(repository.slug, info.table_slug, info.slug)}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={t('reference.open', { name: info.name })}
        title={t('reference.open', { name: info.name })}
        className="repo-focus repo-accent-text shrink-0 rounded px-1 font-semibold no-underline hover:underline"
      >
        ↗
      </a>
    </span>
  )
}

/**
 * The picker of a reference: a dialog with a search over the records (not
 * deleted) of the table the attribute points at; clicking one chooses it.
 */
export function ReferencePicker({
  tableId,
  onPick,
  onClose,
}: {
  tableId: string
  onPick: (hit: RecordHit, table: { slug: string; name: string }) => void
  onClose: () => void
}) {
  const { t } = useTranslation('repository')
  const { repository } = useRepositoryArea()
  const table = repository.tables.find((candidate) => candidate.id === tableId)
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const [result, setResult] = useState<RecordHitPage | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    if (!table) return
    let cancelled = false
    const timer = setTimeout(() => {
      const params = new URLSearchParams({ page: String(page) })
      if (query.trim()) params.set('q', query.trim())
      fetchJson<RecordHitPage>(`${tableApi(repository.slug, table.slug)}/records-search?${params}`)
        .then((found) => {
          if (cancelled) return
          setResult(found)
          setError(false)
        })
        .catch(() => !cancelled && setError(true))
    }, SEARCH_DEBOUNCE_MS)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [repository.slug, table, query, page])

  if (!table) return null
  const pages = result ? Math.max(1, Math.ceil(result.total / result.page_size)) : 1

  return (
    <Modal title={t('reference.pickerTitle', { table: table.name })} onClose={onClose} wide>
      <div className="space-y-3">
        <input
          type="search"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setPage(1)
          }}
          placeholder={t('reference.search')}
          aria-label={t('reference.search')}
          className={inputClass}
        />
        {error && <p className="text-sm text-red-600 dark:text-red-400">{t('reference.searchError')}</p>}
        {result && result.items.length === 0 && <p className="text-sm text-slate-500 dark:text-slate-400">{t('reference.noResults')}</p>}
        {result && result.items.length > 0 && (
          <ul className="max-h-80 divide-y divide-slate-200 overflow-y-auto rounded-xl border border-slate-200 dark:divide-slate-800 dark:border-slate-700">
            {result.items.map((hit) => (
              <li key={hit.id}>
                <button
                  type="button"
                  onClick={() => onPick(hit, { slug: table.slug, name: table.name })}
                  className="repo-focus flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-slate-100 dark:hover:bg-slate-800"
                >
                  <span className="truncate font-medium">{hit.name}</span>
                  <span className="shrink-0 font-mono text-xs text-slate-500 dark:text-slate-400">{hit.slug}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        {result && pages > 1 && (
          <div className="flex items-center justify-between text-sm text-slate-600 dark:text-slate-400">
            <button type="button" disabled={page <= 1} onClick={() => setPage(page - 1)} className={secondaryButtonClass}>
              ←
            </button>
            <span>{t('reference.pageOf', { page, pages, total: result.total })}</span>
            <button type="button" disabled={page >= pages} onClick={() => setPage(page + 1)} className={secondaryButtonClass}>
              →
            </button>
          </div>
        )}
      </div>
    </Modal>
  )
}

/**
 * The input of a reference: the chosen record (name and an arrow that opens it
 * in a new tab), a button that opens the picker, and one that clears it.
 * `info` is what is known about the chosen record (from the server's `refs`, or
 * the hit just picked).
 */
export function ReferenceInput({
  tableId,
  value,
  info,
  onChange,
  label,
}: {
  tableId: string
  value: string
  info: RefInfo | undefined
  onChange: (id: string, info?: RefInfo) => void
  label: string
}) {
  const { t } = useTranslation('repository')
  const [picking, setPicking] = useState(false)

  return (
    <div className="flex flex-wrap items-center gap-2">
      {value && (
        <span className="min-w-0 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950">
          <RefLink info={info} />
        </span>
      )}
      <button type="button" onClick={() => setPicking(true)} aria-label={`${value ? t('reference.change') : t('reference.choose')}: ${label}`} className={secondaryButtonClass}>
        {value ? t('reference.change') : t('reference.choose')}
      </button>
      {value && (
        <button type="button" onClick={() => onChange('')} aria-label={`${t('reference.clear')}: ${label}`} className={secondaryButtonClass}>
          {t('reference.clear')}
        </button>
      )}
      {picking && (
        <ReferencePicker
          tableId={tableId}
          onClose={() => setPicking(false)}
          onPick={(hit, table) => {
            onChange(hit.id, { name: hit.name, slug: hit.slug, table_slug: table.slug, table_name: table.name, deleted: false })
            setPicking(false)
          }}
        />
      )}
    </div>
  )
}
