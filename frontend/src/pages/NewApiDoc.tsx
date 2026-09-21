/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState, type ChangeEvent, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { apiFetch, apiUpload } from '../api/client'
import { useAuth } from '../context/AuthContext'
import usePageMeta from '../hooks/usePageMeta'

interface TeamSummaryData {
  id: string
  name: string
  role: string
  member_count: number
  created_at: string
}

type SourceMode = 'url' | 'upload'
type RecheckPeriod = 'manual' | 'daily' | 'weekly' | 'monthly'
const RECHECK_PERIODS: RecheckPeriod[] = ['manual', 'daily', 'weekly', 'monthly']

/**
 * Team picker + title/notes + a From URL/Upload a file toggle, matching
 * Teams.tsx's "no auto-provisioned personal team" empty state when the
 * caller has zero teams. recheck_period only applies in URL mode - the
 * upload endpoint always forces "manual" server-side, so it's neither
 * shown nor sent in that mode.
 */
export default function NewApiDoc() {
  const { t } = useTranslation()
  usePageMeta({ title: t('apiDocs.new.pageTitle') })
  const { user, loading: authLoading } = useAuth()
  const navigate = useNavigate()

  const [teams, setTeams] = useState<TeamSummaryData[] | null>(null)
  const [teamsError, setTeamsError] = useState<string | null>(null)
  const [teamId, setTeamId] = useState('')

  const [mode, setMode] = useState<SourceMode>('url')
  const [title, setTitle] = useState('')
  const [notes, setNotes] = useState('')
  const [docsUrl, setDocsUrl] = useState('')
  const [sourceUrl, setSourceUrl] = useState('')
  const [recheckPeriod, setRecheckPeriod] = useState<RecheckPeriod>('manual')
  const [file, setFile] = useState<File | null>(null)

  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!authLoading && !user) {
      navigate('/login', { replace: true })
    }
  }, [authLoading, user, navigate])

  useEffect(() => {
    if (!user) return
    apiFetch('/api/teams')
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data: TeamSummaryData[]) => {
        setTeams(data)
        if (data.length > 0) setTeamId(data[0].id)
      })
      .catch(() => setTeamsError(t('apiDocs.new.teamsLoadError')))
  }, [user, t])

  if (authLoading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-900 dark:text-slate-100">
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('common.loading')}</p>
      </div>
    )
  }

  function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    setFile(e.target.files?.[0] ?? null)
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!teamId) return
    setSubmitting(true)
    setError(null)
    try {
      let resp: Response
      if (mode === 'url') {
        resp = await apiFetch('/api/api-docs', {
          method: 'POST',
          body: JSON.stringify({
            team_id: teamId,
            title,
            notes: notes || null,
            source_url: sourceUrl,
            docs_url: docsUrl || null,
            recheck_period: recheckPeriod,
          }),
        })
      } else {
        if (!file) {
          setError(t('apiDocs.new.fileRequired'))
          setSubmitting(false)
          return
        }
        const formData = new FormData()
        formData.append('team_id', teamId)
        formData.append('title', title)
        if (notes) formData.append('notes', notes)
        if (docsUrl) formData.append('docs_url', docsUrl)
        formData.append('file', file)
        resp = await apiUpload('/api/api-docs/upload', formData)
      }

      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}))
        throw new Error(typeof body.detail === 'string' ? body.detail : t('apiDocs.new.error'))
      }
      const created: { id: string } = await resp.json()
      navigate(`/api-docs/${created.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('apiDocs.new.error'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 px-6 py-16 text-slate-900 dark:text-slate-100">
      <h1 className="text-2xl font-semibold tracking-tight">{t('apiDocs.new.pageTitle')}</h1>

      {teamsError && <p className="text-sm text-red-600 dark:text-red-400">{teamsError}</p>}

      {teams === null && !teamsError && <p className="text-sm text-slate-600 dark:text-slate-400">{t('common.loading')}</p>}

      {teams && teams.length === 0 && (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-6 text-center dark:border-slate-700 dark:bg-slate-900">
          <p className="font-medium text-slate-900 dark:text-slate-100">{t('apiDocs.noTeamsMessage')}</p>
          <Link to="/teams" className="mt-2 inline-block text-sm text-slate-900 underline dark:text-slate-100">
            {t('apiDocs.noTeamsLink')}
          </Link>
        </div>
      )}

      {teams && teams.length > 0 && (
        <form
          onSubmit={handleSubmit}
          className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900"
        >
          <div>
            <label htmlFor="doc-team" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
              {t('apiDocs.new.teamLabel')}
            </label>
            <select
              id="doc-team"
              value={teamId}
              onChange={(e) => setTeamId(e.target.value)}
              required
              className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
            >
              {teams.map((team) => (
                <option key={team.id} value={team.id}>
                  {team.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="doc-title" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
              {t('apiDocs.new.titleLabel')}
            </label>
            <input
              id="doc-title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
            />
          </div>

          <div>
            <label htmlFor="doc-notes" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
              {t('apiDocs.new.notesLabel')}
            </label>
            <textarea
              id="doc-notes"
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
            />
          </div>

          <div>
            <label htmlFor="doc-docs-url" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
              {t('apiDocs.new.docsUrlLabel')}
            </label>
            <input
              id="doc-docs-url"
              type="url"
              value={docsUrl}
              onChange={(e) => setDocsUrl(e.target.value)}
              className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
            />
          </div>

          <div className="flex gap-2 border-b border-slate-200 pb-4 dark:border-slate-800">
            <button
              type="button"
              onClick={() => setMode('url')}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium ${
                mode === 'url'
                  ? 'bg-slate-900 text-slate-100 dark:bg-slate-100 dark:text-slate-900'
                  : 'border border-slate-200 text-slate-700 dark:border-slate-700 dark:text-slate-300'
              }`}
            >
              {t('apiDocs.new.modeUrl')}
            </button>
            <button
              type="button"
              onClick={() => setMode('upload')}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium ${
                mode === 'upload'
                  ? 'bg-slate-900 text-slate-100 dark:bg-slate-100 dark:text-slate-900'
                  : 'border border-slate-200 text-slate-700 dark:border-slate-700 dark:text-slate-300'
              }`}
            >
              {t('apiDocs.new.modeUpload')}
            </button>
          </div>

          {mode === 'url' ? (
            <>
              <div>
                <label htmlFor="doc-source-url" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
                  {t('apiDocs.new.sourceUrlLabel')}
                </label>
                <input
                  id="doc-source-url"
                  type="url"
                  value={sourceUrl}
                  onChange={(e) => setSourceUrl(e.target.value)}
                  required
                  placeholder="https://example.com/openapi.json"
                  className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
                />
              </div>
              <div>
                <label htmlFor="doc-recheck-period" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
                  {t('apiDocs.new.recheckPeriodLabel')}
                </label>
                <select
                  id="doc-recheck-period"
                  value={recheckPeriod}
                  onChange={(e) => setRecheckPeriod(e.target.value as RecheckPeriod)}
                  className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
                >
                  {RECHECK_PERIODS.map((period) => (
                    <option key={period} value={period}>
                      {t(`apiDocs.recheckPeriods.${period}`)}
                    </option>
                  ))}
                </select>
              </div>
            </>
          ) : (
            <div>
              <label htmlFor="doc-file" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
                {t('apiDocs.new.fileLabel')}
              </label>
              <input
                id="doc-file"
                type="file"
                accept=".json,.yaml,.yml"
                onChange={handleFileChange}
                required
                className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
              />
            </div>
          )}

          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

          <button
            type="submit"
            disabled={submitting}
            className="rounded-lg bg-slate-900 px-4 py-2 font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
          >
            {submitting ? t('common.saving') : t('apiDocs.new.submit')}
          </button>
        </form>
      )}
    </div>
  )
}
