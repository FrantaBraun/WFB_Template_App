/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'
import { apiFetch } from '../api/client'
import { useAuth } from '../context/AuthContext'
import usePageMeta from '../hooks/usePageMeta'

const PENDING_TOKEN_KEY = 'pending_team_invitation_token'

interface TeamSummaryData {
  id: string
  name: string
}

type Status = 'idle' | 'accepting' | 'success' | 'error'

/**
 * There's no generic redirect-back-after-login mechanism in this codebase
 * (AuthContext's login() always navigates to "/" on success) - so a
 * signed-out visitor is asked to sign in and simply return to this same
 * link afterward, rather than this page inventing one. The pending token is
 * kept in localStorage (not component state) specifically so it survives
 * that round-trip: this component unmounts the moment the user clicks
 * through to /login, and login() navigates to "/" rather than back here.
 *
 * The stash below runs unconditionally (not only when signed out) so the
 * accept effect's own "a user is present and a token is pending" check also
 * covers the simpler case of opening this link while already signed in.
 */
export default function AcceptInvitation() {
  const { t } = useTranslation()
  const { token } = useParams<{ token: string }>()
  const { user, loading: authLoading } = useAuth()

  const [status, setStatus] = useState<Status>('idle')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [team, setTeam] = useState<TeamSummaryData | null>(null)
  const acceptedTokenRef = useRef<string | null>(null)

  usePageMeta({ title: t('teams.accept.pageTitle'), description: t('teams.accept.pageDescription') })

  useEffect(() => {
    if (!token) return
    localStorage.setItem(PENDING_TOKEN_KEY, token)
  }, [token])

  useEffect(() => {
    if (authLoading || !user || !token) return
    if (!localStorage.getItem(PENDING_TOKEN_KEY)) return
    // Guards against React StrictMode's dev-only double-invoke firing this
    // network mutation twice for the same token.
    if (acceptedTokenRef.current === token) return
    acceptedTokenRef.current = token

    setStatus('accepting')
    apiFetch(`/api/teams/invitations/${token}/accept`, { method: 'POST' })
      .then(async (resp) => {
        localStorage.removeItem(PENDING_TOKEN_KEY)
        if (!resp.ok) {
          if (resp.status === 403) {
            setErrorMessage(t('teams.accept.wrongEmail'))
          } else if (resp.status === 410) {
            setErrorMessage(t('teams.accept.expiredOrRevoked'))
          } else if (resp.status === 404) {
            setErrorMessage(t('teams.accept.notFound'))
          } else {
            setErrorMessage(t('teams.accept.genericError'))
          }
          setStatus('error')
          return
        }
        const data: TeamSummaryData = await resp.json()
        setTeam(data)
        setStatus('success')
      })
      .catch(() => {
        localStorage.removeItem(PENDING_TOKEN_KEY)
        setErrorMessage(t('teams.accept.genericError'))
        setStatus('error')
      })
  }, [authLoading, user, token, t])

  if (authLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-900 dark:text-slate-100">
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('common.loading')}</p>
      </div>
    )
  }

  if (!user) {
    return (
      <div className="mx-auto flex min-h-screen max-w-sm flex-col justify-center gap-4 px-6 text-center text-slate-900 dark:text-slate-100">
        <h1 className="text-2xl font-semibold tracking-tight">{t('teams.accept.title')}</h1>
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('teams.accept.needsLogin')}</p>
        <Link
          to="/login"
          className="rounded-lg bg-slate-900 px-4 py-2 font-medium text-slate-100 dark:bg-slate-100 dark:text-slate-900"
        >
          {t('common.login')}
        </Link>
      </div>
    )
  }

  if (status === 'idle' || status === 'accepting') {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-900 dark:text-slate-100">
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('common.loading')}</p>
      </div>
    )
  }

  if (status === 'success') {
    return (
      <div className="mx-auto flex min-h-screen max-w-sm flex-col justify-center gap-4 px-6 text-center text-slate-900 dark:text-slate-100">
        <h1 className="text-2xl font-semibold tracking-tight">{t('teams.accept.successTitle')}</h1>
        <p className="text-sm text-slate-600 dark:text-slate-400">
          {t('teams.accept.successMessage', { team: team?.name })}
        </p>
        {team && (
          <Link
            to={`/teams/${team.id}`}
            className="rounded-lg bg-slate-900 px-4 py-2 font-medium text-slate-100 dark:bg-slate-100 dark:text-slate-900"
          >
            {t('teams.accept.viewTeam')}
          </Link>
        )}
      </div>
    )
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-sm flex-col justify-center gap-4 px-6 text-center text-slate-900 dark:text-slate-100">
      <h1 className="text-2xl font-semibold tracking-tight">{t('teams.accept.errorTitle')}</h1>
      <p className="text-sm text-red-600 dark:text-red-400">{errorMessage}</p>
      <Link to="/teams" className="text-sm text-slate-900 underline dark:text-slate-100">
        {t('teams.accept.backToTeams')}
      </Link>
    </div>
  )
}
