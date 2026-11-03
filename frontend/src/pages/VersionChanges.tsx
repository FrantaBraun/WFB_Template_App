/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../api/client'
import ChangeSummaryBadges, { type ChangeSummaryData } from '../components/ChangeSummaryBadges'
import usePageMeta from '../hooks/usePageMeta'

type Severity = 'breaking' | 'warning' | 'info'

/** One structural change (backend SpecChangeOut) - the wording is made here, from kind and detail. */
interface SpecChange {
  kind: string
  severity: Severity
  method: string | null
  path: string | null
  scope: string | null
  status: string | null
  media_type: string | null
  location: string
  detail: Record<string, unknown>
}

interface VersionRef {
  id: string
  version: string
  fetched_at: string
  content_changed: boolean
}

interface VersionChangesData {
  base: VersionRef
  target: VersionRef
  summary: ChangeSummaryData
  changes: SpecChange[]
  truncated: boolean
}

const SEVERITY_STYLE: Record<Severity, string> = {
  breaking: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
  warning: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300',
  info: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300',
}

function formatDateTime(iso: string, locale: string): string {
  return new Date(iso).toLocaleString(locale, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

/** A list from the backend's `detail` as one string for the sentence ("a, b"), a dash when it is empty. */
function listText(value: unknown): string {
  if (!Array.isArray(value) || value.length === 0) return '–'
  return value.map((item) => (typeof item === 'string' ? item : JSON.stringify(item))).join(', ')
}

/**
 * What a change is about, as the sentence's values: the few facts the
 * backend sends in `detail`, turned into text, plus the i18next `context`
 * that picks between wordings of one kind (a required or an optional
 * parameter added, a property that may now be null or no longer may be).
 */
function sentenceOptions(change: SpecChange): Record<string, unknown> {
  const { kind, detail } = change
  const options: Record<string, unknown> = {
    from: detail.from,
    to: detail.to,
    values: listText(detail.values),
    schemes: listText(detail.schemes),
    added: listText(detail.added),
    removed: listText(detail.removed),
  }
  if (typeof detail.required === 'boolean') options.context = detail.required ? 'required' : 'optional'
  if (kind === 'nullable_changed') options.context = String(detail.nullable === true)
  return options
}

/** Where inside the operation a change is: "Response 200 · application/json · address.zip". */
function whereText(change: SpecChange, t: (key: string, options?: Record<string, unknown>) => string): string {
  const parts: string[] = []
  if (change.scope) parts.push(t(`changes.scope.${change.scope}`, { status: change.status ?? '' }))
  if (change.media_type) parts.push(change.media_type)
  if (change.location) parts.push(change.location)
  return parts.join(' · ')
}

/**
 * What changed between two versions of a document - the page the version
 * history's "Changes" link, and the link in the e-mail about a new version,
 * lead to (GET /api/api-docs/:id/versions/:versionId/changes). The newer
 * version is in the address; the older one is `?against=` or, when that is
 * left out, the version just before it. Changes arrive most severe first and
 * are shown grouped by operation, the group with the worst change on top;
 * "only what matters" hides the harmless ones.
 *
 * The backend sends changes as data (kind, operation, location, detail) and
 * not as sentences, so they read right in either language - the wording is
 * `changes.kinds.<kind>`. Public documents can be looked at while signed out.
 */
export default function VersionChanges() {
  const { t, i18n } = useTranslation()
  usePageMeta({ title: t('changes.pageTitle'), noindex: true })
  const { id, versionId } = useParams<{ id: string; versionId: string }>()
  const [search] = useSearchParams()
  const against = search.get('against')

  const [data, setData] = useState<VersionChangesData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [onlyWhatMatters, setOnlyWhatMatters] = useState(false)

  useEffect(() => {
    if (!id || !versionId) return
    let cancelled = false
    setData(null)
    setError(null)
    const query = against ? `?against=${encodeURIComponent(against)}` : ''
    apiFetch(`/api/api-docs/${id}/versions/${versionId}/changes${query}`)
      .then(async (resp) => {
        if (resp.status === 404) throw new Error(t('changes.notFound'))
        if (!resp.ok) throw new Error(t('changes.loadError'))
        return resp.json()
      })
      .then((result: VersionChangesData) => {
        if (!cancelled) setData(result)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : t('changes.loadError'))
      })
    return () => {
      cancelled = true
    }
  }, [id, versionId, against, t])

  const groups = useMemo(() => {
    const visible = (data?.changes ?? []).filter((change) => !onlyWhatMatters || change.severity !== 'info')
    const byOperation = new Map<string, SpecChange[]>()
    for (const change of visible) {
      const key = change.method && change.path ? `${change.method} ${change.path}` : ''
      byOperation.set(key, [...(byOperation.get(key) ?? []), change])
    }
    return [...byOperation.entries()]
  }, [data, onlyWhatMatters])

  const backLink = (
    <Link to={`/api-docs/${id}`} className="text-sm text-slate-600 underline dark:text-slate-400">
      {t('changes.back')}
    </Link>
  )

  if (error) {
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-4 px-6 py-16 text-center text-slate-900 dark:text-slate-100">
        <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
        {backLink}
      </div>
    )
  }

  if (!data) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-900 dark:text-slate-100">
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('common.loading')}</p>
      </div>
    )
  }

  const hidden = data.changes.length - groups.reduce((sum, [, changes]) => sum + changes.length, 0)

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 px-6 py-16 text-slate-900 dark:text-slate-100">
      <div className="flex items-start justify-between gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">{t('changes.pageTitle')}</h1>
        {backLink}
      </div>

      <p className="text-sm text-slate-600 dark:text-slate-400">
        {t('changes.compared', {
          base: data.base.version,
          baseDate: formatDateTime(data.base.fetched_at, i18n.language),
          target: data.target.version,
          targetDate: formatDateTime(data.target.fetched_at, i18n.language),
        })}
      </p>

      <div className="flex flex-wrap items-center gap-2">
        <ChangeSummaryBadges summary={data.summary} showInfo />
        {data.changes.length > 0 && (
          <label className="ml-auto flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
            <input
              type="checkbox"
              checked={onlyWhatMatters}
              onChange={(e) => setOnlyWhatMatters(e.target.checked)}
              className="h-4 w-4 rounded border-slate-300 dark:border-slate-700"
            />
            {t('changes.onlyWhatMatters')}
          </label>
        )}
      </div>

      {data.changes.length === 0 && (
        <p className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
          {t('changes.none')}
        </p>
      )}
      {hidden > 0 && groups.length === 0 && (
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('changes.allHidden', { count: hidden })}</p>
      )}

      {groups.map(([operation, changes]) => (
        <section
          key={operation || 'general'}
          className="space-y-3 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900"
        >
          <h2 className="break-all font-mono text-sm font-semibold">{operation || t('changes.general')}</h2>
          <ul className="divide-y divide-slate-200 dark:divide-slate-800">
            {changes.map((change, index) => (
              <li key={`${change.kind}:${change.scope}:${change.status}:${change.media_type}:${change.location}:${index}`} className="flex flex-wrap items-start gap-3 py-2 text-sm">
                <span className={`mt-0.5 shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${SEVERITY_STYLE[change.severity]}`}>
                  {t(`changes.severity.${change.severity}`)}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="break-words text-slate-900 dark:text-slate-100">
                    {t(`changes.kinds.${change.kind}`, { ...sentenceOptions(change), defaultValue: change.kind })}
                  </p>
                  {whereText(change, t) && (
                    <p className="break-all font-mono text-xs text-slate-500 dark:text-slate-400">{whereText(change, t)}</p>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </section>
      ))}

      {data.truncated && (
        <p className="text-sm text-amber-700 dark:text-amber-300">{t('changes.truncated', { count: data.changes.length })}</p>
      )}
    </div>
  )
}
