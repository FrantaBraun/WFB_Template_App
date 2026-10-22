/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import usePageMeta from '../../hooks/usePageMeta'
import { useRepositoryArea } from './areaContext'
import {
  PAGE_SIZES,
  deleteRequest,
  errorStatus,
  fetchJson,
  recordApi,
  repositoryPath,
  sendJson,
  tableApi,
  tablePath,
  type RecordListItem,
  type RecordPage,
  type SavedFilter,
  type TableDetail,
} from './api'
import FilterBar from './FilterBar'
import { buildDefinition, conditionToRequest, definitionToDrafts, fieldsFor, type ConditionDraft, type Sort } from './filterModel'
import { GridSort, Pagination, RecordsGrid, RecordsTable } from './RecordsView'
import SavedFilters from './SavedFilters'
import StatisticsSection from './StatisticsSection'
import { BackLink, ConfirmDialog, PageMessage, cardClass, errorTextClass, primaryButtonClass, secondaryButtonClass } from './ui'

const SEARCH_DEBOUNCE_MS = 300

/** /repository/:repo/table/:table - the content of a table: add a record, filter, sort and page through it as a table or a grid. */
export default function TablePage() {
  const { t } = useTranslation('repository')
  const { table: tableSlug = '' } = useParams()
  const { repository, reload } = useRepositoryArea()
  const [table, setTable] = useState<TableDetail | null>(null)
  const [loadError, setLoadError] = useState<'notFound' | 'error' | null>(null)

  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [conditions, setConditions] = useState<ConditionDraft[]>([])
  const [includeDeleted, setIncludeDeleted] = useState(false)
  const [sort, setSort] = useState<Sort | null>(null)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState<number>(PAGE_SIZES[0])

  const [result, setResult] = useState<RecordPage | null>(null)
  const [queryError, setQueryError] = useState(false)
  const [deleting, setDeleting] = useState<RecordListItem | null>(null)
  const [actionError, setActionError] = useState(false)
  const [savedFilters, setSavedFilters] = useState<SavedFilter[]>([])
  const [activeFilterId, setActiveFilterId] = useState<string | null>(null)
  // Bumped when the records or the saved filters changed, so the statistics are computed again.
  const [statisticsKey, setStatisticsKey] = useState(0)
  const ticket = useRef(0)

  usePageMeta({ title: table?.name, noindex: true })

  useEffect(() => {
    let cancelled = false
    setTable(null)
    setResult(null)
    setLoadError(null)
    setSearch('')
    setDebouncedSearch('')
    setConditions([])
    setIncludeDeleted(false)
    setSort(null)
    setPage(1)
    setSavedFilters([])
    setActiveFilterId(null)
    fetchJson<TableDetail>(tableApi(repository.slug, tableSlug))
      .then((found) => !cancelled && setTable(found))
      .catch((e) => !cancelled && setLoadError(errorStatus(e) === 404 ? 'notFound' : 'error'))
    return () => {
      cancelled = true
    }
  }, [repository.slug, tableSlug])

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [search])

  const fields = useMemo(() => (table ? fieldsFor(table.attributes) : []), [table])
  const applied = useMemo(
    () =>
      conditions
        .map((condition) => conditionToRequest(condition, fields.find((field) => field.key === condition.field)))
        .filter((condition) => condition !== null),
    [conditions, fields],
  )
  // A filter only reaches the server once it is complete; typing into a row must not fire a request per key.
  const appliedKey = JSON.stringify(applied)

  const loadFilters = useCallback(async (): Promise<SavedFilter[]> => {
    if (!table) return []
    try {
      const found = await fetchJson<SavedFilter[]>(`${tableApi(repository.slug, table.slug)}/filters`)
      setSavedFilters(found)
      return found
    } catch {
      return []
    }
  }, [repository.slug, table])

  useEffect(() => {
    void loadFilters()
  }, [loadFilters])

  const loadRecords = useCallback(async () => {
    if (!table) return
    const mine = ++ticket.current
    try {
      const found = await sendJson<RecordPage>(`${recordApi(repository.slug, table.slug)}-query`, 'POST', {
        conditions: JSON.parse(appliedKey),
        sort,
        include_deleted: includeDeleted,
        q: debouncedSearch.trim() || null,
        page,
        page_size: pageSize,
      })
      if (mine !== ticket.current) return
      setResult(found)
      setQueryError(false)
    } catch (error) {
      if (mine !== ticket.current) return
      // The page asked for no longer exists (records were deleted meanwhile): go back to the first.
      if (errorStatus(error) === 422 || page > 1) setPage(1)
      setQueryError(true)
    }
  }, [repository.slug, table, appliedKey, sort, includeDeleted, debouncedSearch, page, pageSize])

  useEffect(() => {
    void loadRecords()
  }, [loadRecords])

  if (loadError) return <PageMessage error>{t(loadError === 'notFound' ? 'table.notFound' : 'table.loadError')}</PageMessage>
  if (!table) return <PageMessage>{t('common.loading')}</PageMessage>

  const listed = table.attributes.filter((attribute) => attribute.show_in_list)
  const filtered = search !== '' || conditions.length > 0 || includeDeleted || sort !== null
  const view = { repositorySlug: repository.slug, tableSlug: table.slug, attributes: listed, refs: result?.refs ?? {} }

  const currentDefinition = buildDefinition(applied, sort, includeDeleted, search)

  function applyFilter(saved: SavedFilter) {
    setConditions(definitionToDrafts(saved.definition, saved.refs))
    setSort(saved.definition.sort)
    setIncludeDeleted(saved.definition.include_deleted)
    setSearch(saved.definition.q ?? '')
    setDebouncedSearch(saved.definition.q ?? '')
    setPage(1)
    setActiveFilterId(saved.id)
  }

  function backToFirstPage<T>(setter: (value: T) => void) {
    return (value: T) => {
      setter(value)
      setPage(1)
    }
  }

  async function restore(item: RecordListItem) {
    setActionError(false)
    try {
      await sendJson<void>(`${recordApi(repository.slug, tableSlug, item.slug)}/restore`, 'POST', undefined)
      await Promise.all([loadRecords(), reload()])
      setStatisticsKey((key) => key + 1)
    } catch {
      setActionError(true)
    }
  }

  async function confirmDelete(item: RecordListItem): Promise<string | null> {
    try {
      await deleteRequest(recordApi(repository.slug, tableSlug, item.slug))
      await Promise.all([loadRecords(), reload()])
      setStatisticsKey((key) => key + 1)
      setDeleting(null)
      return null
    } catch {
      return t('record.deleteError')
    }
  }

  return (
    <div className="space-y-5">
      <BackLink to={repositoryPath(repository.slug)}>{repository.name}</BackLink>
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="break-words text-3xl font-semibold tracking-tight">{table.name}</h1>
          {table.description && <p className="mt-2 max-w-2xl whitespace-pre-line text-slate-700 dark:text-slate-300">{table.description}</p>}
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to={`${tablePath(repository.slug, table.slug)}/item/new`} className={primaryButtonClass}>
            {t('records.new')}
          </Link>
          <Link to={`${tablePath(repository.slug, table.slug)}/edit`} className={secondaryButtonClass}>
            {t('table.editDefinition')}
          </Link>
        </div>
      </header>

      <StatisticsSection table={table} repositorySlug={repository.slug} filters={savedFilters} refreshKey={statisticsKey} />

      <SavedFilters
        repositorySlug={repository.slug}
        table={table}
        filters={savedFilters}
        activeId={activeFilterId}
        current={currentDefinition}
        onApply={applyFilter}
        onSaved={async (saved) => {
          await loadFilters()
          setActiveFilterId(saved.id)
          setStatisticsKey((key) => key + 1)
        }}
        onDeleted={async () => {
          await loadFilters()
          setActiveFilterId(null)
          setStatisticsKey((key) => key + 1)
        }}
      />

      <FilterBar
        fields={fields}
        conditions={conditions}
        onConditionsChange={backToFirstPage(setConditions)}
        search={search}
        onSearchChange={backToFirstPage(setSearch)}
        includeDeleted={includeDeleted}
        onIncludeDeletedChange={backToFirstPage(setIncludeDeleted)}
        dirty={filtered}
        onClear={() => {
          setSearch('')
          setDebouncedSearch('')
          setConditions([])
          setIncludeDeleted(false)
          setSort(null)
          setPage(1)
          setActiveFilterId(null)
        }}
      />

      {queryError && <p className={errorTextClass}>{t('records.loadError')}</p>}
      {actionError && <p className={errorTextClass}>{t('record.actionError')}</p>}
      {!result && !queryError && <p className="text-slate-500 dark:text-slate-400">{t('common.loading')}</p>}

      {result && result.items.length === 0 && (
        <p className={`${cardClass} p-8 text-center text-slate-600 dark:text-slate-400`}>{filtered ? t('records.emptyFiltered') : t('records.empty')}</p>
      )}

      {result && result.items.length > 0 && (
        <>
          {table.view_type === 'grid' ? (
            <>
              <GridSort fields={fields} sort={sort} onSort={backToFirstPage(setSort)} />
              <RecordsGrid {...view} items={result.items} onDelete={setDeleting} onRestore={restore} />
            </>
          ) : (
            <RecordsTable {...view} items={result.items} sort={sort} onSort={backToFirstPage(setSort)} onDelete={setDeleting} onRestore={restore} />
          )}
        </>
      )}
      {result && (
        <Pagination page={result.page} pageSize={result.page_size} total={result.total} onPage={setPage} onPageSize={backToFirstPage(setPageSize)} />
      )}

      {deleting && (
        <ConfirmDialog
          title={t('record.deleteTitle', { name: deleting.name })}
          message={t('record.deleteMessage')}
          confirmLabel={t('common.delete')}
          danger
          onConfirm={() => confirmDelete(deleting)}
          onClose={() => setDeleting(null)}
        />
      )}
    </div>
  )
}
