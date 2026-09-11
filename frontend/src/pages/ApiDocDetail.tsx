/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { apiFetch, apiUpload, getApiUrl } from '../api/client'
import VersionBanner from '../components/VersionBanner'
import usePageMeta from '../hooks/usePageMeta'

interface ApiDocumentCurrentVersionData {
  id: string
  version: string
  spec_title: string | null
  format: string
  fetched_at: string
  source: string
}

interface ApiDocumentDetailData {
  id: string
  team_id: string
  title: string
  notes: string | null
  source_url: string | null
  recheck_period: string
  is_public: boolean
  last_checked_at: string | null
  last_check_error: string | null
  created_at: string
  current_version: ApiDocumentCurrentVersionData | null
  can_edit: boolean
  is_subscribed: boolean | null
}

interface ApiDocumentVersionOutData {
  id: string
  version: string
  spec_title: string | null
  fetched_at: string
  archived_at: string | null
  source: string
}

type RecheckPeriod = 'manual' | 'daily' | 'weekly' | 'monthly'
const RECHECK_PERIODS: RecheckPeriod[] = ['manual', 'daily', 'weekly', 'monthly']
type Message = { type: 'success' | 'error'; text: string } | null

function formatDateTime(iso: string, locale: string): string {
  return new Date(iso).toLocaleString(locale, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * Same-URL, different-capability page for anonymous vs. signed-in visitors
 * (the concrete precedent here is kontaktni_formular/ContactPage.tsx) - it
 * fetches through get_current_user_optional-backed endpoints and never
 * redirects to /login, since a public document is fully viewable while
 * signed out. can_edit (server-computed, never re-derived client-side per
 * CLAUDE.md) alone gates the edit form and the recheck/upload-version
 * actions below.
 */
export default function ApiDocDetail() {
  const { t, i18n } = useTranslation()
  const { id } = useParams<{ id: string }>()

  const [doc, setDoc] = useState<ApiDocumentDetailData | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [versions, setVersions] = useState<ApiDocumentVersionOutData[] | null>(null)
  const [versionsError, setVersionsError] = useState<string | null>(null)

  const [editTitle, setEditTitle] = useState('')
  const [editNotes, setEditNotes] = useState('')
  const [editRecheckPeriod, setEditRecheckPeriod] = useState<RecheckPeriod>('manual')
  const [editSourceUrl, setEditSourceUrl] = useState('')
  const [editIsPublic, setEditIsPublic] = useState(false)
  const [editSaving, setEditSaving] = useState(false)
  const [editMessage, setEditMessage] = useState<Message>(null)

  const [rechecking, setRechecking] = useState(false)
  const [recheckError, setRecheckError] = useState<string | null>(null)

  const [versionFile, setVersionFile] = useState<File | null>(null)
  const [uploadingVersion, setUploadingVersion] = useState(false)
  const [uploadVersionError, setUploadVersionError] = useState<string | null>(null)

  const [subscribing, setSubscribing] = useState(false)
  const [subscribeError, setSubscribeError] = useState<string | null>(null)

  usePageMeta({ title: doc?.title ?? t('apiDocs.detail.pageTitleFallback') })

  useEffect(() => {
    if (!id) return
    // :id can change without unmounting (e.g. navigating straight from one
    // doc's page to another's) - guard against a slow-resolving fetch for
    // the PREVIOUS id overwriting state once a newer id's fetch has landed
    // (same pattern as TeamDetail.tsx).
    let cancelled = false
    setDoc(null)
    setNotFound(false)
    setLoadError(null)
    setVersions(null)
    setVersionsError(null)

    apiFetch(`/api/api-docs/${id}`)
      .then((r) => {
        if (r.status === 404) {
          if (!cancelled) setNotFound(true)
          return null
        }
        if (!r.ok) return Promise.reject()
        return r.json()
      })
      .then((data: ApiDocumentDetailData | null) => {
        if (cancelled || !data) return
        setDoc(data)
        setEditTitle(data.title)
        setEditNotes(data.notes ?? '')
        setEditRecheckPeriod(data.recheck_period as RecheckPeriod)
        setEditSourceUrl(data.source_url ?? '')
        setEditIsPublic(data.is_public)
      })
      .catch(() => {
        if (!cancelled) setLoadError(t('apiDocs.detail.loadError'))
      })

    apiFetch(`/api/api-docs/${id}/versions`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data: ApiDocumentVersionOutData[]) => {
        if (!cancelled) setVersions(data)
      })
      .catch(() => {
        if (!cancelled) setVersionsError(t('apiDocs.detail.versionsLoadError'))
      })

    return () => {
      cancelled = true
    }
  }, [id, t])

  async function refreshVersions() {
    if (!id) return
    const resp = await apiFetch(`/api/api-docs/${id}/versions`)
    if (resp.ok) setVersions(await resp.json())
  }

  async function handleEditSubmit(e: FormEvent) {
    e.preventDefault()
    if (!id) return
    setEditSaving(true)
    setEditMessage(null)
    try {
      const resp = await apiFetch(`/api/api-docs/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          title: editTitle,
          notes: editNotes || null,
          recheck_period: editRecheckPeriod,
          source_url: editSourceUrl || null,
          is_public: editIsPublic,
        }),
      })
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}))
        throw new Error(typeof body.detail === 'string' ? body.detail : t('apiDocs.detail.editCard.error'))
      }
      const updated: ApiDocumentDetailData = await resp.json()
      setDoc(updated)
      setEditMessage({ type: 'success', text: t('apiDocs.detail.editCard.success') })
    } catch (err) {
      setEditMessage({ type: 'error', text: err instanceof Error ? err.message : t('apiDocs.detail.editCard.error') })
    } finally {
      setEditSaving(false)
    }
  }

  async function handleRecheck() {
    if (!id) return
    setRechecking(true)
    setRecheckError(null)
    try {
      const resp = await apiFetch(`/api/api-docs/${id}/recheck`, { method: 'POST' })
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}))
        throw new Error(typeof body.detail === 'string' ? body.detail : t('apiDocs.detail.recheckError'))
      }
      setDoc(await resp.json())
      await refreshVersions()
    } catch (err) {
      setRecheckError(err instanceof Error ? err.message : t('apiDocs.detail.recheckError'))
    } finally {
      setRechecking(false)
    }
  }

  async function handleUploadVersion(e: FormEvent) {
    e.preventDefault()
    if (!id || !versionFile) return
    setUploadingVersion(true)
    setUploadVersionError(null)
    try {
      const formData = new FormData()
      formData.append('file', versionFile)
      const resp = await apiUpload(`/api/api-docs/${id}/upload-version`, formData)
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}))
        throw new Error(typeof body.detail === 'string' ? body.detail : t('apiDocs.detail.uploadVersionError'))
      }
      setDoc(await resp.json())
      setVersionFile(null)
      await refreshVersions()
    } catch (err) {
      setUploadVersionError(err instanceof Error ? err.message : t('apiDocs.detail.uploadVersionError'))
    } finally {
      setUploadingVersion(false)
    }
  }

  async function handleToggleSubscribe() {
    if (!doc || doc.is_subscribed === null) return
    setSubscribing(true)
    setSubscribeError(null)
    try {
      const resp = await apiFetch(`/api/api-docs/${doc.id}/subscribe`, {
        method: doc.is_subscribed ? 'DELETE' : 'POST',
      })
      if (!resp.ok) throw new Error(t('notifications.subscribe.error'))
      setDoc((prev) => (prev ? { ...prev, is_subscribed: !prev.is_subscribed } : prev))
    } catch (err) {
      setSubscribeError(err instanceof Error ? err.message : t('notifications.subscribe.error'))
    } finally {
      setSubscribing(false)
    }
  }

  if (notFound) {
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-4 px-6 py-16 text-center text-slate-900 dark:text-slate-100">
        <h1 className="text-2xl font-semibold tracking-tight">{t('apiDocs.detail.notFoundTitle')}</h1>
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('apiDocs.detail.notFoundMessage')}</p>
        <Link to="/api-docs" className="text-sm text-slate-900 underline dark:text-slate-100">
          {t('apiDocs.detail.backToList')}
        </Link>
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-4 px-6 py-16 text-center text-slate-900 dark:text-slate-100">
        <p className="text-sm text-red-600 dark:text-red-400">{loadError}</p>
        <Link to="/api-docs" className="text-sm text-slate-900 underline dark:text-slate-100">
          {t('apiDocs.detail.backToList')}
        </Link>
      </div>
    )
  }

  if (!doc) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-900 dark:text-slate-100">
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('common.loading')}</p>
      </div>
    )
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 px-6 py-16 text-slate-900 dark:text-slate-100">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{doc.title}</h1>
          <span
            className={`mt-1 inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
              doc.is_public
                ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300'
                : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'
            }`}
          >
            {doc.is_public ? t('apiDocs.detail.public') : t('apiDocs.detail.private')}
          </span>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-2">
          {doc.is_subscribed !== null && (
            <button
              type="button"
              onClick={handleToggleSubscribe}
              disabled={subscribing}
              className={`rounded-lg border px-3 py-1.5 text-sm font-medium disabled:opacity-50 ${
                doc.is_subscribed
                  ? 'border-emerald-200 bg-emerald-100 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300'
                  : 'border-slate-200 text-slate-700 dark:border-slate-700 dark:text-slate-300'
              }`}
            >
              {subscribing
                ? t('common.saving')
                : doc.is_subscribed
                  ? t('notifications.subscribe.unsubscribe')
                  : t('notifications.subscribe.subscribe')}
            </button>
          )}
          <Link to="/api-docs" className="text-sm text-slate-600 underline dark:text-slate-400">
            {t('apiDocs.detail.backToList')}
          </Link>
        </div>
      </div>
      {subscribeError && <p className="text-sm text-red-600 dark:text-red-400">{subscribeError}</p>}

      <VersionBanner documentationId={doc.id} />

      {doc.notes && <p className="text-slate-700 dark:text-slate-300">{doc.notes}</p>}

      <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
          {t('apiDocs.detail.currentVersionCard.title')}
        </h2>

        {doc.current_version ? (
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            <dt className="text-slate-500 dark:text-slate-400">{t('apiDocs.detail.currentVersionCard.version')}</dt>
            <dd className="text-slate-900 dark:text-slate-100">{doc.current_version.version}</dd>
            {doc.current_version.spec_title && (
              <>
                <dt className="text-slate-500 dark:text-slate-400">{t('apiDocs.detail.currentVersionCard.specTitle')}</dt>
                <dd className="text-slate-900 dark:text-slate-100">{doc.current_version.spec_title}</dd>
              </>
            )}
            <dt className="text-slate-500 dark:text-slate-400">{t('apiDocs.detail.currentVersionCard.format')}</dt>
            <dd className="text-slate-900 dark:text-slate-100">{doc.current_version.format}</dd>
            <dt className="text-slate-500 dark:text-slate-400">{t('apiDocs.detail.currentVersionCard.fetchedAt')}</dt>
            <dd className="text-slate-900 dark:text-slate-100">{formatDateTime(doc.current_version.fetched_at, i18n.language)}</dd>
          </dl>
        ) : (
          <p className="text-sm text-slate-600 dark:text-slate-400">{t('apiDocs.detail.currentVersionCard.none')}</p>
        )}

        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 border-t border-slate-200 pt-4 text-sm dark:border-slate-800">
          <dt className="text-slate-500 dark:text-slate-400">{t('apiDocs.detail.sourceUrlLabel')}</dt>
          <dd className="break-all text-slate-900 dark:text-slate-100">
            {doc.source_url ? (
              <a href={doc.source_url} target="_blank" rel="noreferrer" className="underline">
                {doc.source_url}
              </a>
            ) : (
              t('apiDocs.detail.noSourceUrl')
            )}
          </dd>
          <dt className="text-slate-500 dark:text-slate-400">{t('apiDocs.detail.recheckPeriodLabel')}</dt>
          <dd className="text-slate-900 dark:text-slate-100">
            {t(`apiDocs.recheckPeriods.${doc.recheck_period}`, { defaultValue: doc.recheck_period })}
          </dd>
          {doc.last_checked_at && (
            <>
              <dt className="text-slate-500 dark:text-slate-400">{t('apiDocs.detail.lastCheckedAtLabel')}</dt>
              <dd className="text-slate-900 dark:text-slate-100">{formatDateTime(doc.last_checked_at, i18n.language)}</dd>
            </>
          )}
        </dl>

        {doc.last_check_error && (
          <p className="text-sm text-red-600 dark:text-red-400">
            {t('apiDocs.detail.lastCheckErrorLabel')}: {doc.last_check_error}
          </p>
        )}
      </div>

      {doc.can_edit && (
        <>
          <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
              {t('apiDocs.detail.actionsCard.title')}
            </h2>

            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={handleRecheck}
                disabled={rechecking || !doc.source_url}
                className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-700 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300"
              >
                {rechecking ? t('common.saving') : t('apiDocs.detail.actionsCard.recheckNow')}
              </button>
              {!doc.source_url && (
                <span className="text-xs text-slate-500 dark:text-slate-400">{t('apiDocs.detail.actionsCard.recheckDisabledHint')}</span>
              )}
            </div>
            {recheckError && <p className="text-sm text-red-600 dark:text-red-400">{recheckError}</p>}

            <form
              onSubmit={handleUploadVersion}
              className="flex flex-wrap items-end gap-3 border-t border-slate-200 pt-4 dark:border-slate-800"
            >
              <div className="flex-1">
                <label htmlFor="upload-version-file" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
                  {t('apiDocs.detail.actionsCard.uploadVersionLabel')}
                </label>
                <input
                  id="upload-version-file"
                  type="file"
                  accept=".json,.yaml,.yml"
                  onChange={(e) => setVersionFile(e.target.files?.[0] ?? null)}
                  className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
                />
              </div>
              <button
                type="submit"
                disabled={uploadingVersion || !versionFile}
                className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-700 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300"
              >
                {uploadingVersion ? t('common.saving') : t('apiDocs.detail.actionsCard.uploadVersionSubmit')}
              </button>
            </form>
            {uploadVersionError && <p className="text-sm text-red-600 dark:text-red-400">{uploadVersionError}</p>}
          </div>

          <form
            onSubmit={handleEditSubmit}
            className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900"
          >
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
              {t('apiDocs.detail.editCard.title')}
            </h2>

            <div>
              <label htmlFor="edit-title" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
                {t('apiDocs.new.titleLabel')}
              </label>
              <input
                id="edit-title"
                type="text"
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                required
                className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
              />
            </div>

            <div>
              <label htmlFor="edit-notes" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
                {t('apiDocs.new.notesLabel')}
              </label>
              <textarea
                id="edit-notes"
                rows={3}
                value={editNotes}
                onChange={(e) => setEditNotes(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
              />
            </div>

            <div>
              <label htmlFor="edit-source-url" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
                {t('apiDocs.new.sourceUrlLabel')}
              </label>
              <input
                id="edit-source-url"
                type="url"
                value={editSourceUrl}
                onChange={(e) => setEditSourceUrl(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
              />
            </div>

            <div>
              <label htmlFor="edit-recheck-period" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
                {t('apiDocs.new.recheckPeriodLabel')}
              </label>
              <select
                id="edit-recheck-period"
                value={editRecheckPeriod}
                onChange={(e) => setEditRecheckPeriod(e.target.value as RecheckPeriod)}
                className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
              >
                {RECHECK_PERIODS.map((period) => (
                  <option key={period} value={period}>
                    {t(`apiDocs.recheckPeriods.${period}`)}
                  </option>
                ))}
              </select>
            </div>

            <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
              <input
                type="checkbox"
                checked={editIsPublic}
                onChange={(e) => setEditIsPublic(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300 dark:border-slate-700"
              />
              {t('apiDocs.detail.editCard.isPublicLabel')}
            </label>

            {editMessage && (
              <p
                className={`text-sm ${
                  editMessage.type === 'success' ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'
                }`}
              >
                {editMessage.text}
              </p>
            )}

            <button
              type="submit"
              disabled={editSaving}
              className="rounded-lg bg-slate-900 px-4 py-2 font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
            >
              {editSaving ? t('common.saving') : t('common.save')}
            </button>
          </form>
        </>
      )}

      <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
          {t('apiDocs.detail.versionsCard.title')}
        </h2>
        {versionsError && <p className="text-sm text-red-600 dark:text-red-400">{versionsError}</p>}
        {versions && versions.length === 0 && (
          <p className="text-sm text-slate-600 dark:text-slate-400">{t('apiDocs.detail.versionsCard.empty')}</p>
        )}
        {versions && versions.length > 0 && (
          <ul className="divide-y divide-slate-200 dark:divide-slate-800">
            {versions.map((version) => (
              <li key={version.id} className="flex items-center justify-between gap-4 py-3 text-sm">
                <div>
                  <p className="font-medium text-slate-900 dark:text-slate-100">
                    {version.version}
                    {version.archived_at === null && (
                      <span className="ml-2 rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300">
                        {t('apiDocs.detail.versionsCard.current')}
                      </span>
                    )}
                  </p>
                  <p className="text-slate-500 dark:text-slate-400">
                    {formatDateTime(version.fetched_at, i18n.language)}
                    {' · '}
                    {t(`apiDocs.versionSources.${version.source}`, { defaultValue: version.source })}
                  </p>
                </div>
                <a
                  href={`${getApiUrl()}/api/api-docs/${doc.id}/versions/${version.id}/spec`}
                  target="_blank"
                  rel="noreferrer"
                  className="shrink-0 rounded-lg border border-slate-200 px-3 py-1.5 text-slate-700 dark:border-slate-700 dark:text-slate-300"
                >
                  {t('apiDocs.detail.versionsCard.viewSpec')}
                </a>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
