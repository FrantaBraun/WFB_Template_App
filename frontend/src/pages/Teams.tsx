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

interface TeamSummaryData {
  id: string
  name: string
  role: string
  member_count: number
  created_at: string
}

/**
 * Caller's own teams, plus a create-team form. There is deliberately no
 * auto-provisioned personal team in this app, so a brand-new user always
 * sees the empty state below until they create or are invited to one.
 */
export default function Teams() {
  const { t } = useTranslation()
  usePageMeta({ title: t('teams.pageTitle'), description: t('teams.pageDescription') })
  const { user, loading: authLoading } = useAuth()
  const navigate = useNavigate()

  const [teams, setTeams] = useState<TeamSummaryData[] | null>(null)
  const [listError, setListError] = useState<string | null>(null)

  const [name, setName] = useState('')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  useEffect(() => {
    if (!authLoading && !user) {
      navigate('/login', { replace: true })
    }
  }, [authLoading, user, navigate])

  useEffect(() => {
    if (!user) return
    apiFetch('/api/teams')
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setTeams)
      .catch(() => setListError(t('teams.loadError')))
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
    setCreateError(null)
    setCreating(true)
    try {
      const resp = await apiFetch('/api/teams', { method: 'POST', body: JSON.stringify({ name }) })
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}))
        throw new Error(typeof body.detail === 'string' ? body.detail : t('teams.createCard.error'))
      }
      const created: TeamSummaryData = await resp.json()
      setTeams((prev) => [...(prev ?? []), created].sort((a, b) => a.name.localeCompare(b.name)))
      setName('')
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : t('teams.createCard.error'))
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 px-6 py-16 text-slate-900 dark:text-slate-100">
      <h1 className="text-2xl font-semibold tracking-tight">{t('teams.pageTitle')}</h1>

      {listError && <p className="text-sm text-red-600 dark:text-red-400">{listError}</p>}

      {teams && teams.length === 0 && (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-6 text-center dark:border-slate-700 dark:bg-slate-900">
          <p className="font-medium text-slate-900 dark:text-slate-100">{t('teams.emptyState.title')}</p>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{t('teams.emptyState.description')}</p>
        </div>
      )}

      {teams && teams.length > 0 && (
        <div className="divide-y divide-slate-200 overflow-hidden rounded-2xl border border-slate-200 bg-white dark:divide-slate-800 dark:border-slate-800 dark:bg-slate-900">
          {teams.map((team) => (
            <Link
              key={team.id}
              to={`/teams/${team.id}`}
              className="flex items-center justify-between gap-4 px-6 py-4 hover:bg-slate-50 dark:hover:bg-slate-800/50"
            >
              <div>
                <p className="font-medium text-slate-900 dark:text-slate-100">{team.name}</p>
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  {t(`teams.roles.${team.role}`, { defaultValue: team.role })} · {team.member_count}{' '}
                  {t(team.member_count === 1 ? 'teams.memberSingular' : 'teams.memberPlural')}
                </p>
              </div>
              <span aria-hidden className="text-slate-400">
                →
              </span>
            </Link>
          ))}
        </div>
      )}

      <form
        onSubmit={handleCreate}
        className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900"
      >
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
          {t('teams.createCard.title')}
        </h2>

        <div>
          <label htmlFor="team-name" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
            {t('teams.createCard.nameLabel')}
          </label>
          <input
            id="team-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
          />
        </div>

        {createError && <p className="text-sm text-red-600 dark:text-red-400">{createError}</p>}

        <button
          type="submit"
          disabled={creating}
          className="rounded-lg bg-slate-900 px-4 py-2 font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
        >
          {creating ? t('common.saving') : t('teams.createCard.submit')}
        </button>
      </form>
    </div>
  )
}
