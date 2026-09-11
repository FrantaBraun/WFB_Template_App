/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { apiFetch } from '../api/client'
import { useAuth } from '../context/AuthContext'
import usePageMeta from '../hooks/usePageMeta'

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

function DocList({ docs, emptyText }: { docs: ApiDocumentSummaryData[]; emptyText: string }) {
  const { t } = useTranslation()

  if (docs.length === 0) {
    return <p className="text-sm text-slate-600 dark:text-slate-400">{emptyText}</p>
  }

  return (
    <div className="divide-y divide-slate-200 overflow-hidden rounded-2xl border border-slate-200 bg-white dark:divide-slate-800 dark:border-slate-800 dark:bg-slate-900">
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
 */
export default function ApiDocs() {
  const { t } = useTranslation()
  usePageMeta({ title: t('apiDocs.pageTitle'), description: t('apiDocs.pageDescription') })
  const { user } = useAuth()

  const [tab, setTab] = useState<Tab>('public')

  const [publicDocs, setPublicDocs] = useState<ApiDocumentSummaryData[] | null>(null)
  const [publicError, setPublicError] = useState<string | null>(null)

  const [myDocs, setMyDocs] = useState<ApiDocumentSummaryData[] | null>(null)
  const [myDocsError, setMyDocsError] = useState<string | null>(null)

  const [teams, setTeams] = useState<TeamSummaryData[] | null>(null)

  useEffect(() => {
    apiFetch('/api/public/api-docs')
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setPublicDocs)
      .catch(() => setPublicError(t('apiDocs.list.loadError')))
  }, [t])

  useEffect(() => {
    if (!user) return
    apiFetch('/api/api-docs')
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setMyDocs)
      .catch(() => setMyDocsError(t('apiDocs.list.loadError')))
    apiFetch('/api/teams')
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setTeams)
      .catch(() => setTeams([]))
  }, [user, t])

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

      {tab === 'public' && (
        <>
          {publicError && <p className="text-sm text-red-600 dark:text-red-400">{publicError}</p>}
          {publicDocs === null && !publicError && <p className="text-sm text-slate-600 dark:text-slate-400">{t('common.loading')}</p>}
          {publicDocs && <DocList docs={publicDocs} emptyText={t('apiDocs.list.empty')} />}
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
          {user && myDocsError && <p className="text-sm text-red-600 dark:text-red-400">{myDocsError}</p>}
          {user && myDocs === null && !myDocsError && <p className="text-sm text-slate-600 dark:text-slate-400">{t('common.loading')}</p>}
          {user && myDocs && <DocList docs={myDocs} emptyText={t('apiDocs.list.empty')} />}
        </>
      )}
    </div>
  )
}
