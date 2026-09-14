/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { apiFetch } from '../api/client'
import { useAuth } from '../context/AuthContext'
import usePageMeta from '../hooks/usePageMeta'

interface IntegrationSummaryData {
  id: string
  name: string
  team_id: string
  collection_count: number
  document_count: number
  created_at: string
}

interface IntegrationDetailData {
  id: string
  team_id: string
  name: string
  description: string | null
  collection_count: number
  direct_document_count: number
  created_at: string
}

interface TeamSummaryData {
  id: string
  name: string
  role: string
  member_count: number
  created_at: string
}

/**
 * Signed-in-only list page - unlike ApiDocs.tsx/Collections.tsx there is no
 * public listing endpoint at all (Integration has no is_public concept, per
 * CLAUDE.md), so this follows Teams.tsx's redirect-to-/login guard instead
 * of a public/mine tab split. Integration creation has no dedicated route -
 * the inline toggled create form mirrors Collections.tsx's own
 * create-and-stay panel, not ApiDocs.tsx's separate /new page.
 */
export default function Integrations() {
  const { t } = useTranslation()
  usePageMeta({ title: t('integrations.pageTitle'), description: t('integrations.pageDescription') })
  const { user, loading: authLoading } = useAuth()
  const navigate = useNavigate()

  const [integrations, setIntegrations] = useState<IntegrationSummaryData[] | null>(null)
  const [listError, setListError] = useState<string | null>(null)

  const [teams, setTeams] = useState<TeamSummaryData[] | null>(null)

  const [showCreateForm, setShowCreateForm] = useState(false)
  const [createTeamId, setCreateTeamId] = useState('')
  const [createName, setCreateName] = useState('')
  const [createDescription, setCreateDescription] = useState('')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  useEffect(() => {
    if (!authLoading && !user) {
      navigate('/login', { replace: true })
    }
  }, [authLoading, user, navigate])

  useEffect(() => {
    if (!user) return
    apiFetch('/api/integrations')
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setIntegrations)
      .catch(() => setListError(t('integrations.list.loadError')))
    apiFetch('/api/teams')
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data: TeamSummaryData[]) => {
        setTeams(data)
        if (data.length > 0) setCreateTeamId(data[0].id)
      })
      .catch(() => setTeams([]))
  }, [user, t])

  if (authLoading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-900 dark:text-slate-100">
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('common.loading')}</p>
      </div>
    )
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault()
    if (!createTeamId) return
    setCreating(true)
    setCreateError(null)
    try {
      const resp = await apiFetch('/api/integrations', {
        method: 'POST',
        body: JSON.stringify({ team_id: createTeamId, name: createName, description: createDescription || null }),
      })
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}))
        throw new Error(typeof body.detail === 'string' ? body.detail : t('integrations.create.error'))
      }
      const created: IntegrationDetailData = await resp.json()
      const summary: IntegrationSummaryData = {
        id: created.id,
        name: created.name,
        team_id: created.team_id,
        collection_count: created.collection_count,
        document_count: created.direct_document_count,
        created_at: created.created_at,
      }
      setIntegrations((prev) => [...(prev ?? []), summary].sort((a, b) => a.name.localeCompare(b.name)))
      setCreateName('')
      setCreateDescription('')
      setShowCreateForm(false)
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : t('integrations.create.error'))
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 px-6 py-16 text-slate-900 dark:text-slate-100">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">{t('integrations.pageTitle')}</h1>
        {teams && teams.length > 0 && (
          <button
            type="button"
            onClick={() => setShowCreateForm((prev) => !prev)}
            className="shrink-0 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-slate-100 dark:bg-slate-100 dark:text-slate-900"
          >
            {t('integrations.newButton')}
          </button>
        )}
      </div>

      {teams && teams.length === 0 && (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-4 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
          {t('integrations.noTeamsMessage')}{' '}
          <Link to="/teams" className="text-slate-900 underline dark:text-slate-100">
            {t('integrations.noTeamsLink')}
          </Link>
        </div>
      )}

      {showCreateForm && teams && teams.length > 0 && (
        <form
          onSubmit={handleCreate}
          className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900"
        >
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
            {t('integrations.create.title')}
          </h2>

          <div>
            <label htmlFor="integration-team" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
              {t('integrations.create.teamLabel')}
            </label>
            <select
              id="integration-team"
              value={createTeamId}
              onChange={(e) => setCreateTeamId(e.target.value)}
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
            <label htmlFor="integration-name" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
              {t('integrations.create.nameLabel')}
            </label>
            <input
              id="integration-name"
              type="text"
              value={createName}
              onChange={(e) => setCreateName(e.target.value)}
              required
              className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
            />
          </div>

          <div>
            <label htmlFor="integration-description" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
              {t('integrations.create.descriptionLabel')}
            </label>
            <textarea
              id="integration-description"
              rows={3}
              value={createDescription}
              onChange={(e) => setCreateDescription(e.target.value)}
              className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
            />
          </div>

          {createError && <p className="text-sm text-red-600 dark:text-red-400">{createError}</p>}

          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={creating}
              className="rounded-lg bg-slate-900 px-4 py-2 font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
            >
              {creating ? t('common.saving') : t('integrations.create.submit')}
            </button>
            <button
              type="button"
              onClick={() => setShowCreateForm(false)}
              className="text-sm text-slate-600 underline dark:text-slate-400"
            >
              {t('common.cancel')}
            </button>
          </div>
        </form>
      )}

      {listError && <p className="text-sm text-red-600 dark:text-red-400">{listError}</p>}
      {integrations === null && !listError && <p className="text-sm text-slate-600 dark:text-slate-400">{t('common.loading')}</p>}
      {integrations && integrations.length === 0 && (
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('integrations.list.empty')}</p>
      )}
      {integrations && integrations.length > 0 && (
        <div className="divide-y divide-slate-200 overflow-hidden rounded-2xl border border-slate-200 bg-white dark:divide-slate-800 dark:border-slate-800 dark:bg-slate-900">
          {integrations.map((integration) => (
            <Link
              key={integration.id}
              to={`/integrations/${integration.id}`}
              className="flex items-center justify-between gap-4 px-6 py-4 hover:bg-slate-50 dark:hover:bg-slate-800/50"
            >
              <div>
                <p className="font-medium text-slate-900 dark:text-slate-100">{integration.name}</p>
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  {integration.collection_count}{' '}
                  {t(
                    integration.collection_count === 1
                      ? 'integrations.list.collectionSingular'
                      : 'integrations.list.collectionPlural',
                  )}
                  {' · '}
                  {integration.document_count}{' '}
                  {t(
                    integration.document_count === 1
                      ? 'integrations.list.documentSingular'
                      : 'integrations.list.documentPlural',
                  )}
                </p>
              </div>
              <span aria-hidden className="text-slate-400">
                →
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
