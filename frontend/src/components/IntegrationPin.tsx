/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { apiFetch } from '../api/client'
import ChangeSummaryBadges, { type ChangeSummaryData } from './ChangeSummaryBadges'

/** The version of a document an integration was built against (backend IntegrationPinOut). */
export interface PinData {
  version_id: string
  version: string
  fetched_at: string
  is_current: boolean
  versions_behind: number
  summary: ChangeSummaryData | null
}

interface VersionOption {
  id: string
  version: string
  fetched_at: string
  archived_at: string | null
}

const BUTTON =
  'rounded-lg border border-slate-200 px-2.5 py-1 text-xs text-slate-700 hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800'

function formatDate(iso: string, locale: string): string {
  return new Date(iso).toLocaleDateString(locale, { year: 'numeric', month: 'short', day: 'numeric' })
}

/**
 * The version of one document an integration was built against, and how far
 * the document has moved since: "Built against 1.2.0 - 2 versions behind -
 * 3 breaking changes - What changed since". Pinning is the answer to "what
 * changed since we integrated?", which stays true across several versions -
 * the newest version's own change summary only says what it brought over the
 * one before it. Anyone on the integration's team may pin the current
 * version in one click, pick any earlier one from the document's history, or
 * unpin; every change goes to the backend and then `onChanged` reloads the
 * list this sits in. The "what changed since" link opens the Changes page
 * with the pinned version as the one to compare against.
 */
export default function IntegrationPin({
  integrationId,
  documentId,
  currentVersionId,
  pin,
  onChanged,
}: {
  integrationId: string
  documentId: string
  currentVersionId: string | null
  pin: PinData | null
  onChanged: () => Promise<void> | void
}) {
  const { t, i18n } = useTranslation()
  const [choosing, setChoosing] = useState(false)
  const [versions, setVersions] = useState<VersionOption[] | null>(null)
  const [selected, setSelected] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const pinUrl = `/api/integrations/${integrationId}/documents/${documentId}/pin`

  async function save(versionId: string) {
    setBusy(true)
    setError(null)
    try {
      const resp = await apiFetch(pinUrl, { method: 'PUT', body: JSON.stringify({ version_id: versionId }) })
      if (!resp.ok) throw new Error()
      setChoosing(false)
      await onChanged()
    } catch {
      setError(t('integrations.detail.pin.saveError'))
    } finally {
      setBusy(false)
    }
  }

  async function unpin() {
    setBusy(true)
    setError(null)
    try {
      const resp = await apiFetch(pinUrl, { method: 'DELETE' })
      if (!resp.ok) throw new Error()
      await onChanged()
    } catch {
      setError(t('integrations.detail.pin.saveError'))
    } finally {
      setBusy(false)
    }
  }

  async function startChoosing() {
    setChoosing(true)
    setError(null)
    if (versions) return
    try {
      const resp = await apiFetch(`/api/api-docs/${documentId}/versions`)
      if (!resp.ok) throw new Error()
      const list: VersionOption[] = await resp.json()
      setVersions(list)
      setSelected(pin?.version_id ?? list[0]?.id ?? '')
    } catch {
      setChoosing(false)
      setError(t('integrations.detail.pin.loadVersionsError'))
    }
  }

  return (
    <div className="mt-2 space-y-2 border-t border-slate-100 pt-2 text-xs dark:border-slate-800">
      <div className="flex flex-wrap items-center gap-2">
        {pin ? (
          <>
            <span className="text-slate-600 dark:text-slate-400">
              {t('integrations.detail.pin.builtAgainst')}{' '}
              <span className="font-medium text-slate-900 dark:text-slate-100">{pin.version}</span>
              <span className="text-slate-500 dark:text-slate-400"> ({formatDate(pin.fetched_at, i18n.language)})</span>
            </span>
            {pin.is_current ? (
              <span className="rounded-full bg-emerald-100 px-2 py-0.5 font-medium text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300">
                {t('integrations.detail.pin.upToDate')}
              </span>
            ) : (
              <>
                <span className="rounded-full bg-amber-100 px-2 py-0.5 font-medium text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
                  {t('integrations.detail.pin.behind', { count: pin.versions_behind })}
                </span>
                <ChangeSummaryBadges summary={pin.summary} />
                {currentVersionId && (
                  <Link
                    to={`/api-docs/${documentId}/versions/${currentVersionId}/changes?against=${pin.version_id}`}
                    title={t('integrations.detail.pin.changesSinceTitle')}
                    className="text-slate-700 underline dark:text-slate-300"
                  >
                    {t('integrations.detail.pin.changesSince')}
                  </Link>
                )}
              </>
            )}
          </>
        ) : (
          <span className="text-slate-500 dark:text-slate-400">{t('integrations.detail.pin.notPinned')}</span>
        )}
      </div>

      {!choosing && (
        <div className="flex flex-wrap items-center gap-2">
          {currentVersionId && !pin?.is_current && (
            <button type="button" disabled={busy} onClick={() => save(currentVersionId)} className={BUTTON}>
              {t('integrations.detail.pin.pinCurrent')}
            </button>
          )}
          <button type="button" disabled={busy} onClick={startChoosing} className={BUTTON}>
            {t('integrations.detail.pin.choose')}
          </button>
          {pin && (
            <button type="button" disabled={busy} onClick={unpin} className={BUTTON}>
              {t('integrations.detail.pin.unpin')}
            </button>
          )}
        </div>
      )}

      {choosing && versions && (
        <div className="flex flex-wrap items-center gap-2">
          <label htmlFor={`pin-${documentId}`} className="sr-only">
            {t('integrations.detail.pin.chooseLabel')}
          </label>
          <select
            id={`pin-${documentId}`}
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-1 text-xs text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
          >
            {versions.map((version) => (
              <option key={version.id} value={version.id}>
                {version.version} · {formatDate(version.fetched_at, i18n.language)}
                {version.archived_at === null ? ` · ${t('integrations.detail.pin.currentSuffix')}` : ''}
              </option>
            ))}
          </select>
          <button type="button" disabled={busy || !selected} onClick={() => save(selected)} className={BUTTON}>
            {t('common.save')}
          </button>
          <button type="button" disabled={busy} onClick={() => setChoosing(false)} className={BUTTON}>
            {t('common.cancel')}
          </button>
        </div>
      )}

      {error && (
        <p role="alert" className="text-red-600 dark:text-red-400">
          {error}
        </p>
      )}
    </div>
  )
}
