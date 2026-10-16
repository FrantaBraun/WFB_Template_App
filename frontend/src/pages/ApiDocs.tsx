/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { apiFetch } from '../api/client'
import ListSearch from '../components/ListSearch'
import { useAuth } from '../context/AuthContext'
import usePageMeta from '../hooks/usePageMeta'
import useSearchableList from '../hooks/useSearchableList'

interface ApiDocumentSummaryData {
  id: string
  title: string
  team_id: string
  is_public: boolean
  recheck_period: string
  last_checked_at: string | null
  last_check_error: string | null
  current_version: string | null
}

interface TeamSummaryData {
  id: string
  name: string
  role: string
  member_count: number
  created_at: string
}

type Tab = 'public' | 'mine'

function DocList({ docs, emptyText, pending }: { docs: ApiDocumentSummaryData[]; emptyText: string; pending: boolean }) {
  const { t } = useTranslation()

  if (docs.length === 0) {
    return <p className="text-sm text-slate-600 dark:text-slate-400">{emptyText}</p>
  }

  return (
    <div
      aria-busy={pending}
      className={`divide-y divide-slate-200 overflow-hidden rounded-2xl border border-slate-200 bg-white transition-opacity dark:divide-slate-800 dark:border-slate-800 dark:bg-slate-900 ${
        pending ? 'opacity-60' : ''
      }`}
    >
      {docs.map((doc) => (
        <Link
          key={doc.id}
          to={`/api-docs/${doc.id}`}
          className="flex items-center justify-between gap-4 px-6 py-4 hover:bg-slate-50 dark:hover:bg-slate-800/50"
        >
          <div>
            <p className="font-medium text-slate-900 dark:text-slate-100">{doc.title}</p>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              {doc.current_version ? t('apiDocs.list.version', { version: doc.current_version }) : t('apiDocs.list.noVersion')}
              {' · '}
              {t(`apiDocs.recheckPeriods.${doc.recheck_period}`, { defaultValue: doc.recheck_period })}
            </p>
            {doc.last_check_error && <p className="mt-1 text-sm text-red-600 dark:text-red-400">{doc.last_check_error}</p>}
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
 * Public/My Docs toggle - Public is the default tab so a logged-out visitor
 * lands somewhere useful (that tab follows HomePage.tsx's fully-public
 * pattern; My Docs follows Account.tsx's authenticated-list pattern). The
 * "New" action needs both a session AND at least one team, per Teams.tsx's
 * own "no auto-provisioned personal team" rule, so it fetches GET
 * /api/teams itself rather than assuming one exists.
 *
 * The search row sits above the tab strip and filters whichever tab is
 * selected - both lists are searched with the same text, so switching tabs
 * keeps the search and shows its results straight away.
 */
export default function ApiDocs() {
  const { t } = useTranslation()
  usePageMeta({ title: t('apiDocs.pageTitle'), description: t('apiDocs.pageDescription') })
  const { user } = useAuth()

  const [tab, setTab] = useState<Tab>('public')
  const [query, setQuery] = useState('')

  const publicList = useSearchableList<ApiDocumentSummaryData>('/api/public/api-docs', query)
  const myList = useSearchableList<ApiDocumentSummaryData>(user ? '/api/api-docs' : null, query)

  const [teams, setTeams] = useState<TeamSummaryData[] | null>(null)

  useEffect(() => {
    if (!user) return
    apiFetch('/api/teams')
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setTeams)
      .catch(() => setTeams([]))
  }, [user])

  const emptyText = (answeredQuery: string) =>
    answeredQuery ? t('common.search.noMatches', { query: answeredQuery }) : t('apiDocs.list.empty')

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 px-6 py-16 text-slate-900 dark:text-slate-100">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">{t('apiDocs.pageTitle')}</h1>
        {user && teams && teams.length > 0 && (
          <Link
            to="/api-docs/new"
            className="shrink-0 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-slate-100 dark:bg-slate-100 dark:text-slate-900"
          >
            {t('apiDocs.newButton')}
          </Link>
        )}
      </div>

      {user && teams && teams.length === 0 && (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-4 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
          {t('apiDocs.noTeamsMessage')}{' '}
          <Link to="/teams" className="text-slate-900 underline dark:text-slate-100">
            {t('apiDocs.noTeamsLink')}
          </Link>
        </div>
      )}

      <div className="flex flex-col gap-3">
        <ListSearch value={query} onChange={setQuery} label={t('apiDocs.search.label')} />

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
            {t('apiDocs.tabs.public')}
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
            {t('apiDocs.tabs.mine')}
          </button>
        </div>
      </div>

      {tab === 'public' && (
        <>
          {publicList.failed && <p className="text-sm text-red-600 dark:text-red-400">{t('apiDocs.list.loadError')}</p>}
          {publicList.items === null && !publicList.failed && (
            <p className="text-sm text-slate-600 dark:text-slate-400">{t('common.loading')}</p>
          )}
          {publicList.items && (
            <DocList docs={publicList.items} pending={publicList.pending} emptyText={emptyText(publicList.answeredQuery)} />
          )}
        </>
      )}

      {tab === 'mine' && (
        <>
          {!user && (
            <p className="text-sm text-slate-600 dark:text-slate-400">
              {t('apiDocs.signInPrompt')}{' '}
              <Link to="/login" className="text-slate-900 underline dark:text-slate-100">
                {t('common.login')}
              </Link>
            </p>
          )}
          {user && myList.failed && <p className="text-sm text-red-600 dark:text-red-400">{t('apiDocs.list.loadError')}</p>}
          {user && myList.items === null && !myList.failed && (
            <p className="text-sm text-slate-600 dark:text-slate-400">{t('common.loading')}</p>
          )}
          {user && myList.items && (
            <DocList docs={myList.items} pending={myList.pending} emptyText={emptyText(myList.answeredQuery)} />
          )}
        </>
      )}
    </div>
  )
}
