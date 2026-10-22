/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import usePageMeta from '../../hooks/usePageMeta'
import { useRepositoryArea } from './areaContext'
import {
  deleteRequest,
  detailField,
  repositoryApi,
  repositoryPath,
  sendJson,
  tableApi,
  tablePath,
  type TableSummary,
} from './api'
import { BackLink, ConfirmNameDialog, cardClass, dangerButtonClass, errorTextClass, primaryButtonClass, secondaryButtonClass } from './ui'

interface ReferencedBy {
  table: string
  table_slug: string
  attribute: string
}

/** /repository/:repo/tables - the tables of the repository: create, reorder, edit the definition, delete. */
export default function TablesPage() {
  const { t } = useTranslation('repository')
  const { repository, reload } = useRepositoryArea()
  const [deleting, setDeleting] = useState<TableSummary | null>(null)
  const [moveError, setMoveError] = useState(false)
  usePageMeta({ title: t('tables.title'), noindex: true })

  async function move(index: number, direction: -1 | 1) {
    const ids = repository.tables.map((table) => table.id)
    const target = index + direction
    if (target < 0 || target >= ids.length) return
    ;[ids[index], ids[target]] = [ids[target], ids[index]]
    setMoveError(false)
    try {
      await sendJson<void>(`${repositoryApi(repository.slug)}/table-order`, 'PUT', { ids })
      await reload()
    } catch {
      setMoveError(true)
    }
  }

  async function confirmDelete(table: TableSummary): Promise<string | null> {
    try {
      await deleteRequest(`${tableApi(repository.slug, table.slug)}?confirm_name=${encodeURIComponent(table.name)}`)
      await reload()
      setDeleting(null)
      return null
    } catch (error) {
      const referring = detailField<ReferencedBy[]>(error, 'referenced_by')
      if (referring?.length) {
        return t('tables.deleteReferenced', { by: referring.map((item) => `${item.table}: ${item.attribute}`).join(', ') })
      }
      return t('tables.deleteError')
    }
  }

  return (
    <div className="space-y-5">
      <BackLink to={repositoryPath(repository.slug)}>{repository.name}</BackLink>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-3xl font-semibold tracking-tight">{t('tables.title')}</h1>
        <Link to={`${repositoryPath(repository.slug)}/table/new`} className={primaryButtonClass}>
          {t('tables.new')}
        </Link>
      </div>
      {moveError && <p className={errorTextClass}>{t('tables.moveError')}</p>}

      {repository.tables.length === 0 ? (
        <p className="rounded-2xl border border-dashed repo-border p-8 text-center text-slate-600 dark:text-slate-400">{t('tables.empty')}</p>
      ) : (
        <ul className={`${cardClass} divide-y divide-slate-200 overflow-hidden dark:divide-slate-800`}>
          {repository.tables.map((table, index) => (
            <li key={table.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
              <div className="min-w-0 flex-1">
                <Link to={tablePath(repository.slug, table.slug)} className="repo-focus block truncate font-medium hover:underline">
                  {table.name}
                </Link>
                <p className="truncate text-sm text-slate-500 dark:text-slate-400">
                  <span className="font-mono">{table.slug}</span> · {t(`table.view.${table.view_type}`)} · {t('home.recordCount', { count: table.record_count })}
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <button type="button" onClick={() => move(index, -1)} disabled={index === 0} aria-label={t('tables.moveUp', { name: table.name })} className={secondaryButtonClass}>
                  ↑
                </button>
                <button
                  type="button"
                  onClick={() => move(index, 1)}
                  disabled={index === repository.tables.length - 1}
                  aria-label={t('tables.moveDown', { name: table.name })}
                  className={secondaryButtonClass}
                >
                  ↓
                </button>
                <Link to={`${tablePath(repository.slug, table.slug)}/edit`} className={secondaryButtonClass}>
                  {t('table.editDefinition')}
                </Link>
                <button type="button" onClick={() => setDeleting(table)} className={dangerButtonClass}>
                  {t('common.delete')}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {deleting && (
        <ConfirmNameDialog
          title={t('tables.deleteTitle', { name: deleting.name })}
          message={t('tables.deleteMessage', { records: deleting.record_count })}
          expectedName={deleting.name}
          confirmLabel={t('common.delete')}
          onConfirm={() => confirmDelete(deleting)}
          onClose={() => setDeleting(null)}
        />
      )}
    </div>
  )
}
