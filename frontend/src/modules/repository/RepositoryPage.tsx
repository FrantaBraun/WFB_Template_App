/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import usePageMeta from '../../hooks/usePageMeta'
import { useRepositoryArea } from './areaContext'
import { deleteRequest, repositoryApi, repositoryPath, tablePath, tablesPath } from './api'
import RepositoryForm from './RepositoryForm'
import { ConfirmNameDialog, cardClass, dangerButtonClass, primaryButtonClass, secondaryButtonClass } from './ui'

/** /repository/:repo - the repository: its tables, editing it, and deleting it. */
export default function RepositoryPage() {
  const { t } = useTranslation('repository')
  const navigate = useNavigate()
  const { repository, reload } = useRepositoryArea()
  const [editing, setEditing] = useState(false)
  const [deleting, setDeleting] = useState(false)
  usePageMeta({ title: repository.name, noindex: true })

  async function confirmDelete(): Promise<string | null> {
    try {
      await deleteRequest(`${repositoryApi(repository.slug)}?confirm_name=${encodeURIComponent(repository.name)}`)
      navigate('/')
      return null
    } catch {
      return t('repository.deleteError')
    }
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-3xl font-semibold tracking-tight">{repository.name}</h1>
          {repository.description && <p className="mt-2 max-w-2xl whitespace-pre-line text-slate-700 dark:text-slate-300">{repository.description}</p>}
          <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
            {t('home.tableCount', { count: repository.table_count })} · {t('home.recordCount', { count: repository.record_count })}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={() => setEditing((value) => !value)} aria-expanded={editing} className={secondaryButtonClass}>
            {t('repository.edit')}
          </button>
          <Link to={tablesPath(repository.slug)} className={secondaryButtonClass}>
            {t('area.manageTables')}
          </Link>
          <Link to={`${repositoryPath(repository.slug)}/table/new`} className={primaryButtonClass}>
            {t('tables.new')}
          </Link>
        </div>
      </header>

      {editing && (
        <section className={`${cardClass} p-5`} aria-label={t('repository.edit')}>
          <RepositoryForm
            repository={repository}
            onCancel={() => setEditing(false)}
            onSaved={async (saved) => {
              if (saved.slug !== repository.slug) navigate(repositoryPath(saved.slug), { replace: true })
              else {
                await reload()
                setEditing(false)
              }
            }}
          />
        </section>
      )}

      <section aria-labelledby="repository-tables">
        <h2 id="repository-tables" className="mb-3 text-xl font-semibold">
          {t('area.tables')}
        </h2>
        {repository.tables.length === 0 ? (
          <p className="rounded-2xl border border-dashed repo-border p-8 text-center text-slate-600 dark:text-slate-400">{t('repository.noTables')}</p>
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2">
            {repository.tables.map((table) => (
              <li key={table.id} className={`${cardClass} flex flex-col gap-2 p-4`}>
                <h3 className="truncate text-lg font-semibold">{table.name}</h3>
                {table.description && <p className="line-clamp-2 whitespace-pre-line text-sm text-slate-600 dark:text-slate-300">{table.description}</p>}
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  {t(`table.view.${table.view_type}`)} · {t('home.recordCount', { count: table.record_count })}
                </p>
                <div className="mt-1 flex flex-wrap gap-2">
                  <Link to={tablePath(repository.slug, table.slug)} className={primaryButtonClass}>
                    {t('home.open')}
                  </Link>
                  <Link to={`${tablePath(repository.slug, table.slug)}/edit`} className={secondaryButtonClass}>
                    {t('table.editDefinition')}
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-2xl border border-red-200 p-4 dark:border-red-900/60" aria-labelledby="repository-danger">
        <h2 id="repository-danger" className="mb-1 text-base font-semibold text-red-700 dark:text-red-400">
          {t('repository.dangerZone')}
        </h2>
        <p className="mb-3 text-sm text-slate-600 dark:text-slate-400">{t('repository.deleteWarning')}</p>
        <button type="button" onClick={() => setDeleting(true)} className={dangerButtonClass}>
          {t('repository.delete')}
        </button>
      </section>

      {deleting && (
        <ConfirmNameDialog
          title={t('repository.deleteTitle', { name: repository.name })}
          message={t('repository.deleteMessage', { tables: repository.table_count, records: repository.record_count })}
          expectedName={repository.name}
          confirmLabel={t('repository.delete')}
          onConfirm={confirmDelete}
          onClose={() => setDeleting(false)}
        />
      )}
    </div>
  )
}
