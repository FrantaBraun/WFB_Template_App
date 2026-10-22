/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { PAGE_SIZES, formatDate, recordPath, type Attribute, type RecordListItem, type RefInfo } from './api'
import { useFieldLabel } from './FilterBar'
import { nextSort, type FieldInfo, type Sort } from './filterModel'
import { RecordImage } from './images'
import ValueView from './ValueView'
import { cardClass, dangerButtonClass, secondaryButtonClass } from './ui'

const SORTABLE = new Set(['text', 'number', 'boolean', 'date', 'datetime', 'reference'])
const GRID_ATTRIBUTES = 3

interface ViewProps {
  repositorySlug: string
  tableSlug: string
  /** The attributes shown on the content page, in order. */
  attributes: Attribute[]
  items: RecordListItem[]
  refs: Record<string, RefInfo>
  onDelete: (item: RecordListItem) => void
  onRestore: (item: RecordListItem) => void
}

function DeletedBadge() {
  const { t } = useTranslation('repository')
  return <span className="ms-2 rounded-full bg-slate-200 px-2 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-700 dark:text-slate-300">{t('record.deletedBadge')}</span>
}

function RowActions({
  item,
  repositorySlug,
  tableSlug,
  onDelete,
  onRestore,
  nowrap = false,
}: Pick<ViewProps, 'repositorySlug' | 'tableSlug' | 'onDelete' | 'onRestore'> & { item: RecordListItem; nowrap?: boolean }) {
  const { t } = useTranslation('repository')
  const deleted = item.deleted_on !== null
  const base = recordPath(repositorySlug, tableSlug, item.slug)
  return (
    <div className={`flex gap-1.5 ${nowrap ? 'flex-nowrap whitespace-nowrap' : 'flex-wrap'}`}>
      <Link to={base} aria-label={t('record.openNamed', { name: item.name })} className={secondaryButtonClass}>
        {t('record.open')}
      </Link>
      {!deleted && (
        <Link to={`${base}/edit`} aria-label={t('record.editNamed', { name: item.name })} className={secondaryButtonClass}>
          {t('common.edit')}
        </Link>
      )}
      {deleted ? (
        <button type="button" onClick={() => onRestore(item)} aria-label={t('record.restoreNamed', { name: item.name })} className={secondaryButtonClass}>
          {t('record.restore')}
        </button>
      ) : (
        <button type="button" onClick={() => onDelete(item)} aria-label={t('record.deleteNamed', { name: item.name })} className={dangerButtonClass}>
          {t('common.delete')}
        </button>
      )}
    </div>
  )
}

function SortHeader({ field, label, sort, onSort }: { field: string; label: string; sort: Sort | null; onSort: (sort: Sort | null) => void }) {
  const { t } = useTranslation('repository')
  const active = sort?.field === field
  return (
    <th scope="col" aria-sort={active ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'} className="whitespace-nowrap px-3 py-2 text-left font-semibold">
      <button type="button" onClick={() => onSort(nextSort(sort, field))} aria-label={t('records.sortBy', { column: label })} className="repo-focus inline-flex items-center gap-1 rounded hover:underline">
        {label}
        <span aria-hidden="true" className="text-xs">
          {active ? (sort.dir === 'asc' ? '▲' : '▼') : ''}
        </span>
      </button>
    </th>
  )
}

/** The content of a table as a table: the name (a link to the record), the attributes shown on the content page, when it was created, and the actions. */
export function RecordsTable({ sort, onSort, ...view }: ViewProps & { sort: Sort | null; onSort: (sort: Sort | null) => void }) {
  const { t, i18n } = useTranslation('repository')
  const language = i18n.resolvedLanguage ?? 'cs'
  const { attributes, items, refs, repositorySlug, tableSlug } = view
  return (
    // `relative`: the visually hidden header text is absolutely positioned and would otherwise widen the whole page.
    <div className={`${cardClass} relative overflow-x-auto`}>
      <table className="w-full min-w-[32rem] border-collapse text-sm">
        <thead className="border-b border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300">
          <tr>
            <SortHeader field="name" label={t('record.fields.name')} sort={sort} onSort={onSort} />
            {attributes.map((attribute) =>
              SORTABLE.has(attribute.type) ? (
                <SortHeader key={attribute.id} field={attribute.id} label={attribute.name} sort={sort} onSort={onSort} />
              ) : (
                <th key={attribute.id} scope="col" className="whitespace-nowrap px-3 py-2 text-left font-semibold">
                  {attribute.name}
                </th>
              ),
            )}
            <SortHeader field="created_on" label={t('records.createdOn')} sort={sort} onSort={onSort} />
            <th scope="col" className="px-3 py-2 text-left font-semibold">
              <span className="sr-only">{t('records.actions')}</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
          {items.map((item) => {
            const deleted = item.deleted_on !== null
            return (
              <tr key={item.id} className={deleted ? 'bg-slate-50 text-slate-500 dark:bg-slate-950 dark:text-slate-400' : ''}>
                <th scope="row" className="max-w-[16rem] px-3 py-2 text-left align-top font-medium">
                  <Link to={recordPath(repositorySlug, tableSlug, item.slug)} className={`repo-focus break-words hover:underline ${deleted ? 'line-through' : ''}`}>
                    {item.name}
                  </Link>
                  {deleted && <DeletedBadge />}
                </th>
                {attributes.map((attribute) => (
                  <td key={attribute.id} className="max-w-[18rem] px-3 py-2 align-top">
                    <ValueView attribute={attribute} value={item.values[attribute.id]} refs={refs} variant="cell" />
                  </td>
                ))}
                <td className="whitespace-nowrap px-3 py-2 align-top text-slate-600 dark:text-slate-400">{formatDate(item.created_on, language)}</td>
                <td className="px-3 py-2 align-top">
                  <RowActions item={item} {...view} nowrap />
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

/** The sort of a grid, which has no column headers to click: what to sort by and in which direction. */
export function GridSort({ fields, sort, onSort }: { fields: FieldInfo[]; sort: Sort | null; onSort: (sort: Sort | null) => void }) {
  const { t } = useTranslation('repository')
  const fieldLabel = useFieldLabel()
  const field = sort?.field ?? 'name'
  const dir = sort?.dir ?? 'asc'
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
      <label className="flex items-center gap-2">
        {t('records.sortField')}
        <select
          value={field}
          onChange={(e) => onSort({ field: e.target.value, dir })}
          className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100"
        >
          {fields.map((candidate) => (
            <option key={candidate.key} value={candidate.key}>
              {fieldLabel(candidate)}
            </option>
          ))}
        </select>
      </label>
      <button type="button" onClick={() => onSort({ field, dir: dir === 'asc' ? 'desc' : 'asc' })} className={secondaryButtonClass}>
        {t(dir === 'asc' ? 'records.sortAsc' : 'records.sortDesc')}
      </button>
    </div>
  )
}

/** The content of a table as a grid of cards: the first image shown on the content page as the cover, the name, up to three more attributes, the actions. */
export function RecordsGrid({ ...view }: ViewProps) {
  const { attributes, items, refs, repositorySlug, tableSlug } = view
  const cover = attributes.find((attribute) => attribute.type === 'image')
  const shown = attributes.filter((attribute) => attribute !== cover).slice(0, GRID_ATTRIBUTES)
  return (
    <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {items.map((item) => {
        const deleted = item.deleted_on !== null
        const image = cover ? item.values[cover.id] : undefined
        return (
          <li key={item.id} className={`${cardClass} flex flex-col overflow-hidden ${deleted ? 'opacity-75' : ''}`}>
            {typeof image === 'string' && (
              <Link to={recordPath(repositorySlug, tableSlug, item.slug)} tabIndex={-1} aria-hidden="true">
                <RecordImage id={image} alt="" className="aspect-video w-full object-cover" />
              </Link>
            )}
            <div className="flex flex-1 flex-col gap-2 p-4">
              <h3 className="break-words font-semibold">
                <Link to={recordPath(repositorySlug, tableSlug, item.slug)} className={`repo-focus hover:underline ${deleted ? 'line-through' : ''}`}>
                  {item.name}
                </Link>
                {deleted && <DeletedBadge />}
              </h3>
              <dl className="flex-1 space-y-1 text-sm">
                {shown.map((attribute) => (
                  <div key={attribute.id}>
                    <dt className="text-xs text-slate-500 dark:text-slate-400">{attribute.name}</dt>
                    <dd>
                      <ValueView attribute={attribute} value={item.values[attribute.id]} refs={refs} variant="cell" />
                    </dd>
                  </div>
                ))}
              </dl>
              <RowActions item={item} {...view} />
            </div>
          </li>
        )
      })}
    </ul>
  )
}

/** Paging: where we are, previous / next, and how many records a page holds. */
export function Pagination({
  page,
  pageSize,
  total,
  onPage,
  onPageSize,
}: {
  page: number
  pageSize: number
  total: number
  onPage: (page: number) => void
  onPageSize: (pageSize: number) => void
}) {
  const { t } = useTranslation('repository')
  const pages = Math.max(1, Math.ceil(total / pageSize))
  const first = total === 0 ? 0 : (page - 1) * pageSize + 1
  const last = Math.min(total, page * pageSize)
  return (
    <nav aria-label={t('records.paging')} className="flex flex-wrap items-center justify-between gap-3 text-sm text-slate-600 dark:text-slate-400">
      <span aria-live="polite">{t('records.showing', { first, last, total })}</span>
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-2">
          {t('records.perPage')}
          <select value={pageSize} onChange={(e) => onPageSize(Number(e.target.value))} className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-slate-900 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100">
            {PAGE_SIZES.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </label>
        <button type="button" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label={t('records.previous')} className={secondaryButtonClass}>
          ←
        </button>
        <span>{t('records.pageOf', { page, pages })}</span>
        <button type="button" disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label={t('records.next')} className={secondaryButtonClass}>
          →
        </button>
      </div>
    </nav>
  )
}
