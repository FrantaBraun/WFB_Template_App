/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'
import usePageMeta from '../../hooks/usePageMeta'
import { useRepositoryArea } from './areaContext'
import {
  deleteRequest,
  detailField,
  errorStatus,
  fetchJson,
  formatDate,
  recordApi,
  recordPath,
  sendJson,
  tableApi,
  tablePath,
  type RepoRecord,
  type TableDetail,
} from './api'
import ValueView from './ValueView'
import { BackLink, ConfirmDialog, PageMessage, cardClass, dangerButtonClass, primaryButtonClass, secondaryButtonClass } from './ui'

interface ReferencedBy {
  table: string
  table_slug: string
  record: string
  record_slug: string
}

type Dialog = 'delete' | 'purge' | null

/** /repository/:repo/table/:table/item/:item - the card of a record with all its attributes. */
export default function RecordPage() {
  const { t, i18n } = useTranslation('repository')
  const language = i18n.resolvedLanguage ?? 'cs'
  const navigate = useNavigate()
  const { table: tableSlug = '', item: itemSlug = '' } = useParams()
  const { repository, reload } = useRepositoryArea()
  const [table, setTable] = useState<TableDetail | null>(null)
  const [record, setRecord] = useState<RepoRecord | null>(null)
  const [loadError, setLoadError] = useState<'notFound' | 'error' | null>(null)
  const [dialog, setDialog] = useState<Dialog>(null)
  const [actionError, setActionError] = useState(false)
  usePageMeta({ title: record?.name, noindex: true })

  const load = useCallback(async () => {
    const [loadedTable, loadedRecord] = await Promise.all([
      fetchJson<TableDetail>(tableApi(repository.slug, tableSlug)),
      fetchJson<RepoRecord>(recordApi(repository.slug, tableSlug, itemSlug)),
    ])
    setTable(loadedTable)
    setRecord(loadedRecord)
  }, [repository.slug, tableSlug, itemSlug])

  useEffect(() => {
    let cancelled = false
    setTable(null)
    setRecord(null)
    setLoadError(null)
    load().catch((e) => !cancelled && setLoadError(errorStatus(e) === 404 ? 'notFound' : 'error'))
    return () => {
      cancelled = true
    }
  }, [load])

  if (loadError) return <PageMessage error>{t(loadError === 'notFound' ? 'record.notFound' : 'record.loadError')}</PageMessage>
  if (!table || !record) return <PageMessage>{t('common.loading')}</PageMessage>

  const deleted = record.deleted_on !== null
  const api = recordApi(repository.slug, table.slug, record.slug)

  async function restore() {
    setActionError(false)
    try {
      await sendJson<void>(`${api}/restore`, 'POST', undefined)
      await Promise.all([load(), reload()])
    } catch {
      setActionError(true)
    }
  }

  async function softDelete(): Promise<string | null> {
    try {
      await deleteRequest(api)
      await Promise.all([load(), reload()])
      setDialog(null)
      return null
    } catch {
      return t('record.deleteError')
    }
  }

  async function purge(): Promise<string | null> {
    try {
      await deleteRequest(`${api}/permanent`)
      await reload()
      navigate(tablePath(repository.slug, table?.slug ?? tableSlug))
      return null
    } catch (error) {
      const referring = detailField<ReferencedBy[]>(error, 'referenced_by')
      if (referring?.length) {
        const more = Number(detailField<number>(error, 'count') ?? referring.length) - referring.length
        return t('record.purgeReferenced', { by: referring.map((item) => `${item.table}: ${item.record}`).join(', '), more: Math.max(more, 0) })
      }
      return t('record.deleteError')
    }
  }

  return (
    <div className="space-y-5">
      <BackLink to={tablePath(repository.slug, table.slug)}>{table.name}</BackLink>
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className={`break-words text-3xl font-semibold tracking-tight ${deleted ? 'text-slate-500 line-through dark:text-slate-400' : ''}`}>{record.name}</h1>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
            {table.name} · <span className="font-mono">{record.slug}</span>
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {!deleted && (
            <Link to={`${recordPath(repository.slug, table.slug, record.slug)}/edit`} className={primaryButtonClass}>
              {t('common.edit')}
            </Link>
          )}
          {!deleted && (
            <button type="button" onClick={() => setDialog('delete')} className={dangerButtonClass}>
              {t('common.delete')}
            </button>
          )}
          {deleted && (
            <>
              <button type="button" onClick={restore} className={primaryButtonClass}>
                {t('record.restore')}
              </button>
              <button type="button" onClick={() => setDialog('purge')} className={dangerButtonClass}>
                {t('record.purge')}
              </button>
            </>
          )}
          <Link to={tablePath(repository.slug, table.slug)} className={secondaryButtonClass}>
            {t('record.backToList')}
          </Link>
        </div>
      </header>

      {deleted && (
        <p role="status" className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200">
          {t('record.deletedBanner', { date: formatDate(record.deleted_on, language) })}
        </p>
      )}
      {actionError && <p className="text-sm text-red-600 dark:text-red-400">{t('record.actionError')}</p>}

      <section className={`${cardClass} p-5`} aria-label={t('record.card')}>
        <dl className="space-y-4">
          {table.attributes.length === 0 && <p className="text-sm text-slate-500 dark:text-slate-400">{t('record.noAttributes')}</p>}
          {table.attributes.map((attribute) => (
            <div key={attribute.id}>
              <dt className="text-sm font-medium text-slate-600 dark:text-slate-400">
                {attribute.name}
                {attribute.description && <span className="ms-2 text-xs font-normal text-slate-500">{attribute.description}</span>}
              </dt>
              <dd className="mt-1">
                <ValueView attribute={attribute} value={record.data[attribute.id]} refs={record.refs} variant="full" />
              </dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="rounded-2xl border border-slate-200 p-4 text-sm text-slate-600 dark:border-slate-800 dark:text-slate-400" aria-label={t('record.system')}>
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide">{t('record.system')}</h2>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
          <dt>id</dt>
          <dd className="break-all font-mono text-xs">{record.id}</dd>
          <dt>slug</dt>
          <dd className="font-mono text-xs">{record.slug}</dd>
          <dt>created_on</dt>
          <dd>{formatDate(record.created_on, language)}</dd>
          <dt>deleted_on</dt>
          <dd>{formatDate(record.deleted_on, language)}</dd>
        </dl>
      </section>

      {dialog === 'delete' && (
        <ConfirmDialog
          title={t('record.deleteTitle', { name: record.name })}
          message={t('record.deleteMessage')}
          confirmLabel={t('common.delete')}
          danger
          onConfirm={softDelete}
          onClose={() => setDialog(null)}
        />
      )}
      {dialog === 'purge' && (
        <ConfirmDialog
          title={t('record.purgeTitle', { name: record.name })}
          message={t('record.purgeMessage')}
          confirmLabel={t('record.purge')}
          danger
          onConfirm={purge}
          onClose={() => setDialog(null)}
        />
      )}
    </div>
  )
}
