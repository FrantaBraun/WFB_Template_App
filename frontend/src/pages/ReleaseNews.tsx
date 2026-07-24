/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { getApiUrl } from '../api/client'
import usePageMeta from '../hooks/usePageMeta'
import { compareVersions, parseMajorMinor } from '../utils/version'

interface ReleaseEntry {
  version: string
  release_date: string
  changes: string[]
}

interface ReleaseNewsData {
  unreleased: string[]
  releases: ReleaseEntry[]
}

type FetchState = {
  data: ReleaseNewsData | null
  error: string | null
  loading: boolean
}

// Shared fetch/loading/error state for both the backend and frontend release_news.json calls below.
function useReleaseNewsFetch(url: string): FetchState {
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

// Groups releases by "major.minor" (newest patch first within each group) so
// backend/frontend releases for the same compatible generation can be
// rendered side by side - same major.minor compatibility rule as Version.tsx.
function groupByMajorMinor(releases: ReleaseEntry[]): Map<string, ReleaseEntry[]> {
  const groups = new Map<string, ReleaseEntry[]>()
  for (const release of releases) {
    const { major, minor } = parseMajorMinor(release.version)
    const key = `${major}.${minor}`
    const group = groups.get(key)
    if (group) {
      group.push(release)
    } else {
      groups.set(key, [release])
    }
  }
  for (const group of groups.values()) {
    group.sort((a, b) => compareVersions(b.version, a.version))
  }
  return groups
}

// Sorts "major.minor" keys numerically descending (newest generation first).
function sortGenerationKeys(keys: string[]): string[] {
  return [...keys].sort((a, b) => compareVersions(`${b}.0`, `${a}.0`))
}

function ChangeList({ changes }: { changes: string[] }) {
  return (
    <ul className="space-y-1 text-sm text-slate-600 dark:text-slate-400">
      {changes.map((change, i) => (
        <li key={i}>• {change}</li>
      ))}
    </ul>
  )
}

function UnreleasedCard({ title, changes }: { title: string; changes: string[] }) {
  const { t } = useTranslation()
  if (changes.length === 0) return null

  return (
    <div className="rounded-2xl border border-amber-500/30 bg-amber-500/5 p-4">
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-amber-300">
        {title} — {t('releaseNews.unreleased')}
      </h3>
      <ChangeList changes={changes} />
    </div>
  )
}

function ReleaseColumn({ title, releases }: { title: string; releases: ReleaseEntry[] }) {
  const { t } = useTranslation()

  return (
    <div>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</h3>
      {releases.length === 0 ? (
        <p className="text-sm text-slate-400 dark:text-slate-600">{t('releaseNews.noCompatibleRelease')}</p>
      ) : (
        releases.map((release) => (
          <div key={release.version} className="mb-4 last:mb-0">
            <p className="mb-1 text-sm font-medium text-slate-800 dark:text-slate-200">
              v{release.version} <span className="text-slate-500">— {release.release_date}</span>
            </p>
            <ChangeList changes={release.changes} />
          </div>
        ))
      )}
    </div>
  )
}

/**
 * Backend and frontend release history side by side, grouped by major.minor
 * so a compatible generation (both sides shipped that version line) is
 * visually obvious - an empty column marks a generation only one side
 * has released, i.e. a currently-incompatible pairing.
 */
export default function ReleaseNews() {
  const { t } = useTranslation()
  usePageMeta({ title: t('releaseNews.pageTitle'), description: t('releaseNews.pageDescription') })

  const backend = useReleaseNewsFetch(`${getApiUrl()}/api/public/release-news`)
  const frontend = useReleaseNewsFetch('/release_news.json')

  const loading = backend.loading || frontend.loading
  const hasError = Boolean(backend.error || frontend.error)

  const backendGroups = groupByMajorMinor(backend.data?.releases ?? [])
  const frontendGroups = groupByMajorMinor(frontend.data?.releases ?? [])
  const generationKeys = sortGenerationKeys([
    ...new Set([...backendGroups.keys(), ...frontendGroups.keys()]),
  ])

  return (
    <div className="mx-auto max-w-3xl px-6 py-16 text-slate-900 dark:text-slate-100">
      <h1 className="mb-1 text-2xl font-semibold tracking-tight">{t('releaseNews.title')}</h1>
      <p className="mb-8 text-sm text-slate-500">{t('releaseNews.subtitle')}</p>

      {loading && <p className="text-sm text-slate-500">{t('common.loading')}</p>}
      {hasError && <p className="mb-6 text-sm text-red-600 dark:text-red-400">{t('releaseNews.loadError')}</p>}

      {!loading && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-4">
            <UnreleasedCard title={t('releaseNews.backend')} changes={backend.data?.unreleased ?? []} />
            <UnreleasedCard title={t('releaseNews.frontend')} changes={frontend.data?.unreleased ?? []} />
          </div>

          {generationKeys.map((key) => {
            const backendReleases = backendGroups.get(key) ?? []
            const frontendReleases = frontendGroups.get(key) ?? []
            const compatible = backendReleases.length > 0 && frontendReleases.length > 0

            return (
              <div
                key={key}
                className={`rounded-2xl border p-6 ${
                  compatible
                    ? 'border-emerald-500/30 bg-emerald-500/5'
                    : 'border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900'
                }`}
              >
                <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
                  v{key} {compatible && `— ${t('releaseNews.compatible')}`}
                </h2>
                <div className="grid grid-cols-2 gap-6">
                  <ReleaseColumn title={t('releaseNews.backend')} releases={backendReleases} />
                  <ReleaseColumn title={t('releaseNews.frontend')} releases={frontendReleases} />
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
