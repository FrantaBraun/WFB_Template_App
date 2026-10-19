/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import usePageMeta from '../../hooks/usePageMeta'
import { API_BASE, MANAGE_PATH, PORTFOLIO_PATH, deleteRequest, editPath, fetchJson, sendJson, type AdminItem } from './api'
import {
  AdminGate,
  StatusBadge,
  cardClass,
  container,
  dangerButtonClass,
  mutedText,
  primaryButtonClass,
  secondaryButtonClass,
} from './ui'

function ManageList() {
  const { t } = useTranslation('portfolio')
  const [items, setItems] = useState<AdminItem[] | null>(null)
  const [loadError, setLoadError] = useState(false)
  const [actionError, setActionError] = useState(false)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [reload, setReload] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoadError(false)
    fetchJson<AdminItem[]>(`${API_BASE}/manage/items`)
      .then((found) => !cancelled && setItems(found))
      .catch(() => !cancelled && setLoadError(true))
    return () => {
      cancelled = true
    }
  }, [reload])

  /** One action at a time: the row's controls are disabled until the server has answered. */
  async function run(id: string, action: () => Promise<void>) {
    setBusyId(id)
    setActionError(false)
    try {
      await action()
    } catch {
      setActionError(true)
    } finally {
      setBusyId(null)
    }
  }

  const move = (item: AdminItem, direction: 'up' | 'down') =>
    run(item.id, async () => {
      // The answer is the whole list in its new order.
      setItems(await sendJson<AdminItem[]>(`${API_BASE}/manage/items/${item.id}/move`, 'POST', { direction }))
    })

  const togglePublished = (item: AdminItem) =>
    run(item.id, async () => {
      const updated = await sendJson<AdminItem>(`${API_BASE}/manage/items/${item.id}`, 'PATCH', { published: !item.published })
      setItems((current) => current?.map((other) => (other.id === updated.id ? updated : other)) ?? current)
    })

  const remove = (item: AdminItem) => {
    if (!window.confirm(t('manage.confirmDelete', { title: item.title_cs }))) return Promise.resolve()
    return run(item.id, async () => {
      await deleteRequest(`${API_BASE}/manage/items/${item.id}`)
      setItems((current) => current?.filter((other) => other.id !== item.id) ?? current)
    })
  }

  return (
    <div className={`${container} py-12 text-slate-900 dark:text-slate-100`}>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-3xl font-semibold tracking-tight">{t('manage.title')}</h1>
        <div className="flex flex-wrap items-center gap-2">
          <Link to={PORTFOLIO_PATH} className={secondaryButtonClass}>
            {t('manage.viewPublic')}
          </Link>
          <Link to={`${MANAGE_PATH}/new`} className={primaryButtonClass}>
            {t('manage.new')}
          </Link>
        </div>
      </div>
      <p className={`mb-6 max-w-2xl text-sm ${mutedText}`}>{t('manage.intro')}</p>

      {actionError && (
        <p role="alert" className="mb-4 text-sm text-red-700 dark:text-red-400">
          {t('manage.actionError')}
        </p>
      )}

      {loadError && (
        <div role="alert" className="space-y-3">
          <p className="text-red-700 dark:text-red-400">{t('manage.loadError')}</p>
          <button type="button" onClick={() => setReload((n) => n + 1)} className={secondaryButtonClass}>
            {t('common.retry')}
          </button>
        </div>
      )}
      {items === null && !loadError && <p role="status" className={mutedText}>{t('common.loading')}</p>}
      {items && items.length === 0 && <p className={mutedText}>{t('manage.empty')}</p>}

      {items && items.length > 0 && (
        <ol className={`${cardClass} divide-y divide-slate-200 overflow-hidden dark:divide-slate-800`}>
          {items.map((item, index) => {
            const busy = busyId === item.id
            return (
              <li key={item.id} className="flex flex-wrap items-center gap-x-4 gap-y-3 px-4 py-3">
                <span aria-hidden="true" className="w-5 shrink-0 text-sm text-slate-400 dark:text-slate-500">
                  {index + 1}.
                </span>
                <div className="min-w-0 flex-1 basis-48">
                  <p className="break-words font-medium">{item.title_cs}</p>
                  <p className={`break-all text-sm ${mutedText}`}>
                    {PORTFOLIO_PATH}/{item.slug}
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <StatusBadge status={item.status} />
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={item.published}
                      disabled={busy}
                      onChange={() => togglePublished(item)}
                      aria-label={t('manage.publishedFor', { title: item.title_cs })}
                    />
                    {t('manage.published')}
                  </label>
                  {!item.published && (
                    <span className="rounded-full bg-slate-200 px-2.5 py-0.5 text-xs font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                      {t('manage.unpublished')}
                    </span>
                  )}
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    disabled={busy || index === 0}
                    onClick={() => move(item, 'up')}
                    aria-label={t('manage.moveUp', { title: item.title_cs })}
                    title={t('manage.moveUpShort')}
                    className={secondaryButtonClass}
                  >
                    <span aria-hidden="true">↑</span>
                  </button>
                  <button
                    type="button"
                    disabled={busy || index === items.length - 1}
                    onClick={() => move(item, 'down')}
                    aria-label={t('manage.moveDown', { title: item.title_cs })}
                    title={t('manage.moveDownShort')}
                    className={secondaryButtonClass}
                  >
                    <span aria-hidden="true">↓</span>
                  </button>
                  <Link to={editPath(item.id)} className={secondaryButtonClass} aria-label={t('manage.editFor', { title: item.title_cs })}>
                    {t('manage.edit')}
                  </Link>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => remove(item)}
                    aria-label={t('manage.deleteFor', { title: item.title_cs })}
                    className={dangerButtonClass}
                  >
                    {t('manage.delete')}
                  </button>
                </div>
              </li>
            )
          })}
        </ol>
      )}
    </div>
  )
}

/** /portfolio/manage - every project, hidden ones too: order, visibility, edit and delete. */
export default function ManagePage() {
  const { t } = useTranslation('portfolio')
  usePageMeta({ title: t('manage.title'), noindex: true })
  return (
    <AdminGate>
      <ManageList />
    </AdminGate>
  )
}
