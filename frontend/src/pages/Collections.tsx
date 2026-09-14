/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { apiFetch } from '../api/client'
import { useAuth } from '../context/AuthContext'
import usePageMeta from '../hooks/usePageMeta'

interface CollectionSummaryData {
  id: string
  name: string
  team_id: string
  is_public: boolean
  document_count: number
  created_at: string
}

interface TeamSummaryData {
  id: string
  name: string
  role: string
  member_count: number
  created_at: string
}

type Tab = 'public' | 'mine'

function CollectionList({ collections, emptyText }: { collections: CollectionSummaryData[]; emptyText: string }) {
  const { t } = useTranslation()

  if (collections.length === 0) {
    return <p className="text-sm text-slate-600 dark:text-slate-400">{emptyText}</p>
  }

  return (
    <div className="divide-y divide-slate-200 overflow-hidden rounded-2xl border border-slate-200 bg-white dark:divide-slate-800 dark:border-slate-800 dark:bg-slate-900">
      {collections.map((collection) => (
        <Link
          key={collection.id}
          to={`/collections/${collection.id}`}
          className="flex items-center justify-between gap-4 px-6 py-4 hover:bg-slate-50 dark:hover:bg-slate-800/50"
        >
          <div>
            <p className="font-medium text-slate-900 dark:text-slate-100">{collection.name}</p>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {collection.document_count}{' '}
              {t(collection.document_count === 1 ? 'collections.list.documentSingular' : 'collections.list.documentPlural')}
            </p>
          </div>
          <span aria-hidden className="text-slate-400">
            →
          </span>
        </Link>
      ))}
    </div>
  )
}

/**
 * Public/My Collections toggle, mirroring ApiDocs.tsx one level up the
 * domain model exactly (Public default tab, My Collections needs a session,
 * the "New" action needs both a session AND at least one team). Unlike
 * NewApiDoc.tsx, collection creation has no dedicated route - the form is an
 * inline panel toggled by the "New" button and, on success, stays on this
 * page with the new collection appended to My Collections (same
 * create-and-stay pattern as Teams.tsx's own create form).
 */
export default function Collections() {
  const { t } = useTranslation()
  usePageMeta({ title: t('collections.pageTitle'), description: t('collections.pageDescription') })
  const { user } = useAuth()

  const [tab, setTab] = useState<Tab>('public')

  const [publicCollections, setPublicCollections] = useState<CollectionSummaryData[] | null>(null)
  const [publicError, setPublicError] = useState<string | null>(null)

  const [myCollections, setMyCollections] = useState<CollectionSummaryData[] | null>(null)
  const [myError, setMyError] = useState<string | null>(null)

  const [teams, setTeams] = useState<TeamSummaryData[] | null>(null)

  const [showCreateForm, setShowCreateForm] = useState(false)
  const [createTeamId, setCreateTeamId] = useState('')
  const [createName, setCreateName] = useState('')
  const [createDescription, setCreateDescription] = useState('')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  useEffect(() => {
    apiFetch('/api/public/collections')
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setPublicCollections)
      .catch(() => setPublicError(t('collections.list.loadError')))
  }, [t])

  useEffect(() => {
    if (!user) return
    apiFetch('/api/collections')
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setMyCollections)
      .catch(() => setMyError(t('collections.list.loadError')))
    apiFetch('/api/teams')
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data: TeamSummaryData[]) => {
        setTeams(data)
        if (data.length > 0) setCreateTeamId(data[0].id)
      })
      .catch(() => setTeams([]))
  }, [user, t])

  async function handleCreate(e: FormEvent) {
    e.preventDefault()
    if (!createTeamId) return
    setCreating(true)
    setCreateError(null)
    try {
      const resp = await apiFetch('/api/collections', {
        method: 'POST',
        body: JSON.stringify({ team_id: createTeamId, name: createName, description: createDescription || null }),
      })
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}))
        throw new Error(typeof body.detail === 'string' ? body.detail : t('collections.create.error'))
      }
      const created: CollectionSummaryData = await resp.json()
      setMyCollections((prev) => [...(prev ?? []), created].sort((a, b) => a.name.localeCompare(b.name)))
      setCreateName('')
      setCreateDescription('')
      setShowCreateForm(false)
      setTab('mine')
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : t('collections.create.error'))
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 px-6 py-16 text-slate-900 dark:text-slate-100">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">{t('collections.pageTitle')}</h1>
        {user && teams && teams.length > 0 && (
          <button
            type="button"
            onClick={() => setShowCreateForm((prev) => !prev)}
            className="shrink-0 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-slate-100 dark:bg-slate-100 dark:text-slate-900"
          >
            {t('collections.newButton')}
          </button>
        )}
      </div>

      {user && teams && teams.length === 0 && (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-4 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
          {t('collections.noTeamsMessage')}{' '}
          <Link to="/teams" className="text-slate-900 underline dark:text-slate-100">
            {t('collections.noTeamsLink')}
          </Link>
        </div>
      )}

      {showCreateForm && teams && teams.length > 0 && (
        <form
          onSubmit={handleCreate}
          className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900"
        >
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
            {t('collections.create.title')}
          </h2>

          <div>
            <label htmlFor="collection-team" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
              {t('collections.create.teamLabel')}
            </label>
            <select
              id="collection-team"
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
            <label htmlFor="collection-name" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
              {t('collections.create.nameLabel')}
            </label>
            <input
              id="collection-name"
              type="text"
              value={createName}
              onChange={(e) => setCreateName(e.target.value)}
              required
              className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
            />
          </div>

          <div>
            <label htmlFor="collection-description" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
              {t('collections.create.descriptionLabel')}
            </label>
            <textarea
              id="collection-description"
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
              {creating ? t('common.saving') : t('collections.create.submit')}
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

      <div className="flex gap-2 border-b border-slate-200 dark:border-slate-800">
        <button
          type="button"
          onClick={() => setTab('public')}
          className={`px-3 py-2 text-sm font-medium ${
            tab === 'public'
              ? 'border-b-2 border-slate-900 text-slate-900 dark:border-slate-100 dark:text-slate-100'
              : 'text-slate-500 dark:text-slate-400'
          }`}
        >
          {t('collections.tabs.public')}
        </button>
        <button
          type="button"
          onClick={() => setTab('mine')}
          className={`px-3 py-2 text-sm font-medium ${
            tab === 'mine'
              ? 'border-b-2 border-slate-900 text-slate-900 dark:border-slate-100 dark:text-slate-100'
              : 'text-slate-500 dark:text-slate-400'
          }`}
        >
          {t('collections.tabs.mine')}
        </button>
      </div>

      {tab === 'public' && (
        <>
          {publicError && <p className="text-sm text-red-600 dark:text-red-400">{publicError}</p>}
          {publicCollections === null && !publicError && (
            <p className="text-sm text-slate-600 dark:text-slate-400">{t('common.loading')}</p>
          )}
          {publicCollections && <CollectionList collections={publicCollections} emptyText={t('collections.list.empty')} />}
        </>
      )}

      {tab === 'mine' && (
        <>
          {!user && (
            <p className="text-sm text-slate-600 dark:text-slate-400">
              {t('collections.signInPrompt')}{' '}
              <Link to="/login" className="text-slate-900 underline dark:text-slate-100">
                {t('common.login')}
              </Link>
            </p>
          )}
          {user && myError && <p className="text-sm text-red-600 dark:text-red-400">{myError}</p>}
          {user && myCollections === null && !myError && (
            <p className="text-sm text-slate-600 dark:text-slate-400">{t('common.loading')}</p>
          )}
          {user && myCollections && <CollectionList collections={myCollections} emptyText={t('collections.list.empty')} />}
        </>
      )}
    </div>
  )
}
