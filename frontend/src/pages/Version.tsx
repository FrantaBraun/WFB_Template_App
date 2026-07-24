/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { getApiUrl } from '../api/client'
import usePageMeta from '../hooks/usePageMeta'
import { parseMajorMinor } from '../utils/version'

type VersionInfo = Record<string, unknown> & { version?: string }

type FetchState = {
  data: VersionInfo | null
  error: string | null
  loading: boolean
}

// Shared fetch/loading/error state for both the backend and frontend version.json calls below.
function useVersionFetch(url: string): FetchState {
  const [state, setState] = useState<FetchState>({ data: null, error: null, loading: true })

  useEffect(() => {
    let cancelled = false

    fetch(url)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data) => {
        if (!cancelled) setState({ data, error: null, loading: false })
      })
      .catch((err) => {
        if (!cancelled) setState({ data: null, error: err?.message ?? String(err), loading: false })
      })

    return () => {
      cancelled = true
    }
  }, [url])

  return state
}

// Renders whatever fields the version.json/endpoint happens to contain, in
// whatever order Object.entries yields them - not tied to a fixed schema.
function VersionCard({ title, state }: { title: string; state: FetchState }) {
  const { t } = useTranslation()
  const { data, error, loading } = state
  const fields = data
    ? Object.entries(data).filter(([, value]) => value !== null && value !== undefined && value !== '')
    : []

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">{title}</h2>

      {loading && <p className="text-sm text-slate-500">{t('version.loading')}</p>}
      {error && (
        <p className="text-sm text-red-600 dark:text-red-400">
          {t('version.loadFailed')}: {error}
        </p>
      )}

      {!loading && !error && (
        <dl className="space-y-2">
          {fields.map(([key, value]) => (
            <div
              key={key}
              className="flex items-baseline justify-between gap-4 border-b border-slate-200/60 pb-2 last:border-0 last:pb-0 dark:border-slate-800/60"
            >
              <dt className="text-xs uppercase tracking-wide text-slate-500">{key.replace(/_/g, ' ')}</dt>
              <dd className="truncate text-right font-mono text-sm text-slate-900 dark:text-slate-100">{String(value)}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  )
}

/**
 * Diagnostics page comparing this backend's /api/public/version against the
 * frontend's own bundled /version.json, flagging a mismatch when their
 * major.minor versions differ (the two are versioned/deployed independently).
 */
export default function Version() {
  const { t } = useTranslation()
  usePageMeta({ title: t('version.pageTitle'), description: t('version.pageDescription') })

  const backend = useVersionFetch(`${getApiUrl()}/api/public/version`)
  const frontend = useVersionFetch('/version.json')

  const backendVersion = backend.data?.version
  const frontendVersion = frontend.data?.version
  const bothLoaded = Boolean(backendVersion && frontendVersion)
  // Only major.minor are compared for compatibility - patch-level drift between
  // backend/frontend is expected since they release independently (see build.py).
  const compatible =
    bothLoaded &&
    (() => {
      const b = parseMajorMinor(backendVersion)
      const f = parseMajorMinor(frontendVersion)
      return b.major === f.major && b.minor === f.minor
    })()

  return (
    <div className="mx-auto max-w-2xl px-6 py-16 text-slate-900 dark:text-slate-100">
      <h1 className="mb-1 text-2xl font-semibold tracking-tight">{t('version.title')}</h1>
      <p className="mb-8 text-sm text-slate-500">{t('version.subtitle')}</p>

      {bothLoaded && (
        <div
          className={`mb-8 rounded-xl border px-4 py-3 text-sm ${
            compatible
              ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
              : 'border-amber-500/30 bg-amber-500/10 text-amber-300'
          }`}
        >
          {compatible
            ? t('version.compatible', { backend: backendVersion, frontend: frontendVersion })
            : t('version.mismatch', { backend: backendVersion, frontend: frontendVersion })}
        </div>
      )}

      <div className="space-y-4">
        <VersionCard title={t('version.backend')} state={backend} />
        <VersionCard title={t('version.frontend')} state={frontend} />
      </div>
    </div>
  )
}
