/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { deleteRequest, fetchJson, sendJson, tableApi, type SavedFilter, type Statistic, type StatisticWithResult, type TableDetail } from './api'
import StatisticEditor from './StatisticEditor'
import StatisticView from './StatisticView'
import { ConfirmDialog, cardClass, dangerButtonClass, errorTextClass, secondaryButtonClass } from './ui'

/**
 * The statistics of a table, as tiles at the top of its content page: each is a
 * saved statistic shown as a table, a chart or both (see StatisticView), with
 * buttons to edit, delete and reorder it, and a button for a new one. A statistic
 * saved as "hidden" is not a tile and is listed below them so it can still be
 * edited or deleted. `refreshKey` changes when the records or the saved filters did,
 * and the results are fetched again (the old ones stay on screen meanwhile).
 */
export default function StatisticsSection({
  table,
  repositorySlug,
  filters,
  refreshKey,
}: {
  table: TableDetail
  repositorySlug: string
  filters: SavedFilter[]
  refreshKey: number
}) {
  const { t } = useTranslation('repository')
  const [statistics, setStatistics] = useState<Statistic[] | null>(null)
  const [tiles, setTiles] = useState<StatisticWithResult[]>([])
  const [error, setError] = useState(false)
  const [editing, setEditing] = useState<Statistic | 'new' | null>(null)
  const [deleting, setDeleting] = useState<Statistic | null>(null)
  const api = tableApi(repositorySlug, table.slug)

  const load = useCallback(async () => {
    try {
      const [all, shown] = await Promise.all([fetchJson<Statistic[]>(`${api}/statistics`), fetchJson<StatisticWithResult[]>(`${api}/statistics-results`)])
      setStatistics(all)
      setTiles(shown)
      setError(false)
    } catch {
      setError(true)
    }
  }, [api])

  useEffect(() => {
    void load()
  }, [load, refreshKey])

  async function move(statistic: Statistic, direction: -1 | 1) {
    if (!statistics) return
    const shown = tiles.map((tile) => tile.statistic.id)
    const neighbour = shown[shown.indexOf(statistic.id) + direction]
    if (!neighbour) return
    const ids = statistics.map((candidate) => candidate.id)
    const from = ids.indexOf(statistic.id)
    const to = ids.indexOf(neighbour)
    ;[ids[from], ids[to]] = [ids[to], ids[from]]
    try {
      await sendJson<void>(`${api}/statistics-order`, 'PUT', { ids })
      await load()
    } catch {
      setError(true)
    }
  }

  async function confirmDelete(statistic: Statistic): Promise<string | null> {
    try {
      await deleteRequest(`${api}/statistics/${statistic.id}`)
      await load()
      setDeleting(null)
      return null
    } catch {
      return t('statistics.deleteError')
    }
  }

  const filterName = (id: string | null) => filters.find((saved) => saved.id === id)?.name
  const hidden = (statistics ?? []).filter((statistic) => statistic.display === 'hidden')

  return (
    <section aria-labelledby="statistics-title" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="statistics-title" className="text-xl font-semibold">
          {t('statistics.title')}
        </h2>
        <button type="button" onClick={() => setEditing('new')} className={secondaryButtonClass}>
          {t('statistics.new')}
        </button>
      </div>
      {error && <p className={errorTextClass}>{t('statistics.loadError')}</p>}
      {statistics !== null && tiles.length === 0 && hidden.length === 0 && <p className="text-sm text-slate-600 dark:text-slate-400">{t('statistics.none')}</p>}

      {tiles.length > 0 && (
        <ul className="grid gap-4 lg:grid-cols-2">
          {tiles.map(({ statistic, result }, index) => (
            <li key={statistic.id} className={`${cardClass} stat-viz flex min-w-0 flex-col gap-3 p-4`}>
              <div>
                <h3 className="break-words text-base font-semibold">{statistic.name}</h3>
                {statistic.filter_id && <p className="text-xs text-slate-500 dark:text-slate-400">{t('statistics.filteredBy', { name: filterName(statistic.filter_id) ?? '?' })}</p>}
              </div>
              <div className="min-w-0 flex-1">
                <StatisticView
                  result={result}
                  dimensions={statistic.group_by}
                  aggregation={statistic.aggregation}
                  attributes={table.attributes}
                  display={statistic.display}
                  chartType={statistic.chart_type}
                />
              </div>
              <div className="flex flex-wrap gap-1.5">
                <button type="button" onClick={() => setEditing(statistic)} aria-label={t('statistics.editNamed', { name: statistic.name })} className={secondaryButtonClass}>
                  {t('common.edit')}
                </button>
                <button type="button" onClick={() => setDeleting(statistic)} aria-label={t('statistics.deleteNamed', { name: statistic.name })} className={dangerButtonClass}>
                  {t('common.delete')}
                </button>
                <button type="button" onClick={() => move(statistic, -1)} disabled={index === 0} aria-label={t('statistics.moveUp', { name: statistic.name })} className={secondaryButtonClass}>
                  ↑
                </button>
                <button type="button" onClick={() => move(statistic, 1)} disabled={index === tiles.length - 1} aria-label={t('statistics.moveDown', { name: statistic.name })} className={secondaryButtonClass}>
                  ↓
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {hidden.length > 0 && (
        <div className="text-sm text-slate-600 dark:text-slate-400">
          <p className="mb-1 font-medium">{t('statistics.hiddenTitle')}</p>
          <ul className="space-y-1">
            {hidden.map((statistic) => (
              <li key={statistic.id} className="flex flex-wrap items-center gap-2">
                <span>{statistic.name}</span>
                <button type="button" onClick={() => setEditing(statistic)} aria-label={t('statistics.editNamed', { name: statistic.name })} className={secondaryButtonClass}>
                  {t('common.edit')}
                </button>
                <button type="button" onClick={() => setDeleting(statistic)} aria-label={t('statistics.deleteNamed', { name: statistic.name })} className={dangerButtonClass}>
                  {t('common.delete')}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {editing && (
        <StatisticEditor
          table={table}
          repositorySlug={repositorySlug}
          filters={filters}
          statistic={editing === 'new' ? undefined : editing}
          onClose={() => setEditing(null)}
          onSaved={async () => {
            setEditing(null)
            await load()
          }}
        />
      )}
      {deleting && (
        <ConfirmDialog
          title={t('statistics.deleteTitle', { name: deleting.name })}
          message={t('statistics.deleteMessage')}
          confirmLabel={t('common.delete')}
          danger
          onConfirm={() => confirmDelete(deleting)}
          onClose={() => setDeleting(null)}
        />
      )}
    </section>
  )
}
