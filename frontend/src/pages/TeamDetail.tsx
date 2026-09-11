/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { apiFetch } from '../api/client'
import { useAuth } from '../context/AuthContext'
import usePageMeta from '../hooks/usePageMeta'

interface TeamMemberData {
  user_id: string
  email: string | null
  role: string
  joined_at: string
}

interface TeamDetailData {
  id: string
  name: string
  members: TeamMemberData[]
}

interface InvitationOutData {
  id: string
  team_id: string
  email: string
  status: string
  created_at: string
  expires_at: string
}

type Message = { type: 'success' | 'error'; text: string } | null

function formatDate(iso: string, locale: string): string {
  return new Date(iso).toLocaleDateString(locale, { year: 'numeric', month: 'short', day: 'numeric' })
}

/**
 * Member list with roles, invite-by-email, remove/leave, and pending
 * invitations with revoke - everything GET /api/teams/{id} (member-only)
 * unlocks. Role-based button visibility below is a convenience only: the
 * backend is the real enforcement, so the last-owner/last-member guards it
 * applies are deliberately not replicated here - a rejected attempt just
 * surfaces the server's own error message instead.
 *
 * "Which member row is mine" can't be found by comparing useAuth().user.id
 * (the upstream auth service's own id, from /api/auth/me) against a row's
 * user_id (the LOCAL users.id that TeamMembership actually stores) - those
 * are two different id spaces. /api/account/me returns the local id, so it
 * is fetched here purely to resolve that match.
 */
export default function TeamDetail() {
  const { t, i18n } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const { user, loading: authLoading } = useAuth()
  const navigate = useNavigate()

  const [team, setTeam] = useState<TeamDetailData | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [myAccountId, setMyAccountId] = useState<string | null>(null)

  const [invitations, setInvitations] = useState<InvitationOutData[] | null>(null)
  const [invitationsError, setInvitationsError] = useState<string | null>(null)

  const [nameDraft, setNameDraft] = useState('')
  const [renameSaving, setRenameSaving] = useState(false)
  const [renameMessage, setRenameMessage] = useState<Message>(null)

  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteSaving, setInviteSaving] = useState(false)
  const [inviteMessage, setInviteMessage] = useState<Message>(null)

  const [memberActionError, setMemberActionError] = useState<string | null>(null)
  const [removingUserId, setRemovingUserId] = useState<string | null>(null)
  const [revokingInvitationId, setRevokingInvitationId] = useState<string | null>(null)

  usePageMeta({
    title: team?.name ?? t('teams.detail.pageTitleFallback'),
    description: t('teams.detail.pageDescription'),
  })

  useEffect(() => {
    if (!authLoading && !user) {
      navigate('/login', { replace: true })
    }
  }, [authLoading, user, navigate])

  useEffect(() => {
    if (!user || !id) return
    // :id can change (e.g. clicking straight from one team's page to
    // another's) without unmounting this component - guard against a
    // slow-resolving fetch for the PREVIOUS id overwriting state once a
    // newer id's fetch has already landed.
    let cancelled = false
    setTeam(null)
    setNotFound(false)
    setLoadError(null)
    setInvitations(null)
    setInvitationsError(null)

    apiFetch(`/api/teams/${id}`)
      .then((r) => {
        if (r.status === 404) {
          if (!cancelled) setNotFound(true)
          return null
        }
        if (!r.ok) return Promise.reject()
        return r.json()
      })
      .then((data: TeamDetailData | null) => {
        if (cancelled || !data) return
        setTeam(data)
        setNameDraft(data.name)
        return apiFetch(`/api/teams/${id}/invitations`)
          .then((r) => (r.ok ? r.json() : Promise.reject()))
          .then((inv) => {
            if (!cancelled) setInvitations(inv)
          })
          .catch(() => {
            if (!cancelled) setInvitationsError(t('teams.detail.invitationsLoadError'))
          })
      })
      .catch(() => {
        if (!cancelled) setLoadError(t('teams.detail.loadError'))
      })

    apiFetch('/api/account/me')
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data: { id: string }) => {
        if (!cancelled) setMyAccountId(data.id)
      })
      .catch(() => {})

    return () => {
      cancelled = true
    }
  }, [user, id, t])

  if (authLoading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-900 dark:text-slate-100">
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('common.loading')}</p>
      </div>
    )
  }

  async function handleRename(e: FormEvent) {
    e.preventDefault()
    if (!id) return
    setRenameSaving(true)
    setRenameMessage(null)
    try {
      const resp = await apiFetch(`/api/teams/${id}`, { method: 'PATCH', body: JSON.stringify({ name: nameDraft }) })
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}))
        throw new Error(typeof body.detail === 'string' ? body.detail : t('teams.detail.renameCard.error'))
      }
      const updated: { name: string } = await resp.json()
      setTeam((prev) => (prev ? { ...prev, name: updated.name } : prev))
      setRenameMessage({ type: 'success', text: t('teams.detail.renameCard.success') })
    } catch (err) {
      setRenameMessage({
        type: 'error',
        text: err instanceof Error ? err.message : t('teams.detail.renameCard.error'),
      })
    } finally {
      setRenameSaving(false)
    }
  }

  async function handleInvite(e: FormEvent) {
    e.preventDefault()
    if (!id) return
    setInviteSaving(true)
    setInviteMessage(null)
    try {
      const resp = await apiFetch(`/api/teams/${id}/invitations`, {
        method: 'POST',
        body: JSON.stringify({ email: inviteEmail }),
      })
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}))
        throw new Error(typeof body.detail === 'string' ? body.detail : t('teams.detail.inviteCard.error'))
      }
      const created: InvitationOutData = await resp.json()
      setInvitations((prev) => [created, ...(prev ?? [])])
      setInviteEmail('')
      setInviteMessage({ type: 'success', text: t('teams.detail.inviteCard.success') })
    } catch (err) {
      setInviteMessage({
        type: 'error',
        text: err instanceof Error ? err.message : t('teams.detail.inviteCard.error'),
      })
    } finally {
      setInviteSaving(false)
    }
  }

  async function handleRemoveMember(memberId: string, isSelf: boolean) {
    if (!id) return
    const confirmed = window.confirm(
      isSelf ? t('teams.detail.membersCard.confirmLeave') : t('teams.detail.membersCard.confirmRemove'),
    )
    if (!confirmed) return

    setRemovingUserId(memberId)
    setMemberActionError(null)
    try {
      const resp = await apiFetch(`/api/teams/${id}/members/${memberId}`, { method: 'DELETE' })
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}))
        throw new Error(typeof body.detail === 'string' ? body.detail : t('teams.detail.membersCard.removeError'))
      }
      if (isSelf) {
        navigate('/teams', { replace: true })
        return
      }
      setTeam((prev) => (prev ? { ...prev, members: prev.members.filter((m) => m.user_id !== memberId) } : prev))
    } catch (err) {
      setMemberActionError(err instanceof Error ? err.message : t('teams.detail.membersCard.removeError'))
    } finally {
      setRemovingUserId(null)
    }
  }

  async function handleRevoke(invitationId: string) {
    if (!id) return
    setRevokingInvitationId(invitationId)
    setInvitationsError(null)
    try {
      const resp = await apiFetch(`/api/teams/${id}/invitations/${invitationId}/revoke`, { method: 'POST' })
      if (!resp.ok) throw new Error()
      // GET .../invitations only ever returns status=="pending" entries, so
      // a just-revoked one belongs out of this list, same as a refetch would show.
      setInvitations((prev) => (prev ? prev.filter((inv) => inv.id !== invitationId) : prev))
    } catch {
      setInvitationsError(t('teams.detail.invitationsCard.revokeError'))
    } finally {
      setRevokingInvitationId(null)
    }
  }

  if (notFound) {
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-4 px-6 py-16 text-center text-slate-900 dark:text-slate-100">
        <h1 className="text-2xl font-semibold tracking-tight">{t('teams.detail.notFoundTitle')}</h1>
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('teams.detail.notFoundMessage')}</p>
        <Link to="/teams" className="text-sm text-slate-900 underline dark:text-slate-100">
          {t('teams.detail.backToList')}
        </Link>
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-4 px-6 py-16 text-center text-slate-900 dark:text-slate-100">
        <p className="text-sm text-red-600 dark:text-red-400">{loadError}</p>
        <Link to="/teams" className="text-sm text-slate-900 underline dark:text-slate-100">
          {t('teams.detail.backToList')}
        </Link>
      </div>
    )
  }

  if (!team) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-900 dark:text-slate-100">
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('common.loading')}</p>
      </div>
    )
  }

  const myRole = team.members.find((m) => m.user_id === myAccountId)?.role

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 px-6 py-16 text-slate-900 dark:text-slate-100">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">{team.name}</h1>
        <Link to="/teams" className="text-sm text-slate-600 underline dark:text-slate-400">
          {t('teams.detail.backToList')}
        </Link>
      </div>

      <form
        onSubmit={handleRename}
        className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900"
      >
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
          {t('teams.detail.renameCard.title')}
        </h2>
        <div>
          <label htmlFor="team-rename" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
            {t('teams.detail.renameCard.nameLabel')}
          </label>
          <input
            id="team-rename"
            type="text"
            value={nameDraft}
            onChange={(e) => setNameDraft(e.target.value)}
            required
            className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
          />
        </div>
        {renameMessage && (
          <p
            className={`text-sm ${
              renameMessage.type === 'success' ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'
            }`}
          >
            {renameMessage.text}
          </p>
        )}
        <button
          type="submit"
          disabled={renameSaving}
          className="rounded-lg bg-slate-900 px-4 py-2 font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
        >
          {renameSaving ? t('common.saving') : t('common.save')}
        </button>
      </form>

      <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
          {t('teams.detail.membersCard.title')}
        </h2>
        {memberActionError && <p className="text-sm text-red-600 dark:text-red-400">{memberActionError}</p>}
        <ul className="divide-y divide-slate-200 dark:divide-slate-800">
          {team.members.map((member) => {
            const isSelf = member.user_id === myAccountId
            const canRemove = isSelf || myRole === 'owner' || member.role !== 'owner'
            return (
              <li key={member.user_id} className="flex items-center justify-between gap-4 py-3">
                <div>
                  <p className="font-medium text-slate-900 dark:text-slate-100">
                    {member.email ?? t('teams.detail.membersCard.unknownEmail')}
                    {isSelf && (
                      <span className="ml-1 text-slate-500 dark:text-slate-400">
                        ({t('teams.detail.membersCard.you')})
                      </span>
                    )}
                  </p>
                  <p className="text-sm text-slate-500 dark:text-slate-400">
                    {t(`teams.roles.${member.role}`, { defaultValue: member.role })} ·{' '}
                    {t('teams.detail.membersCard.joined')} {formatDate(member.joined_at, i18n.language)}
                  </p>
                </div>
                {canRemove && (
                  <button
                    type="button"
                    onClick={() => handleRemoveMember(member.user_id, isSelf)}
                    disabled={removingUserId === member.user_id}
                    className="shrink-0 rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-700 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300"
                  >
                    {isSelf ? t('teams.detail.membersCard.leaveButton') : t('teams.detail.membersCard.removeButton')}
                  </button>
                )}
              </li>
            )
          })}
        </ul>
      </div>

      <form
        onSubmit={handleInvite}
        className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900"
      >
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
          {t('teams.detail.inviteCard.title')}
        </h2>
        <div>
          <label htmlFor="invite-email" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
            {t('teams.detail.inviteCard.emailLabel')}
          </label>
          <input
            id="invite-email"
            type="email"
            value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
            required
            className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
          />
        </div>
        {inviteMessage && (
          <p
            className={`text-sm ${
              inviteMessage.type === 'success' ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'
            }`}
          >
            {inviteMessage.text}
          </p>
        )}
        <button
          type="submit"
          disabled={inviteSaving}
          className="rounded-lg bg-slate-900 px-4 py-2 font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
        >
          {inviteSaving ? t('common.saving') : t('teams.detail.inviteCard.submit')}
        </button>
      </form>

      <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
          {t('teams.detail.invitationsCard.title')}
        </h2>
        {invitationsError && <p className="text-sm text-red-600 dark:text-red-400">{invitationsError}</p>}
        {invitations && invitations.length === 0 && (
          <p className="text-sm text-slate-600 dark:text-slate-400">{t('teams.detail.invitationsCard.empty')}</p>
        )}
        {invitations && invitations.length > 0 && (
          <ul className="divide-y divide-slate-200 dark:divide-slate-800">
            {invitations.map((invitation) => (
              <li key={invitation.id} className="flex items-center justify-between gap-4 py-3">
                <div>
                  <p className="font-medium text-slate-900 dark:text-slate-100">{invitation.email}</p>
                  <p className="text-sm text-slate-500 dark:text-slate-400">
                    {t('teams.detail.invitationsCard.expiresAt')} {formatDate(invitation.expires_at, i18n.language)}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => handleRevoke(invitation.id)}
                  disabled={revokingInvitationId === invitation.id}
                  className="shrink-0 rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-700 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300"
                >
                  {t('teams.detail.invitationsCard.revoke')}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
