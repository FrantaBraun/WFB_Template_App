/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../api/client'
import { useAuth } from '../context/AuthContext'
import usePageMeta from '../hooks/usePageMeta'

interface GroupInfo {
  id: string
  name: string
  description: string
  scopes: string[]
}

/**
 * This template's own consent screen (not the auth service's hosted one) -
 * reads `?group=` / `?redirect=` set by AuthContext's redirectToConsent(),
 * fetches scope info via group-info (API key only, no user token needed),
 * then grants/rejects against the auth service before continuing the redirect.
 */
export default function Consent() {
  const { t } = useTranslation()
  usePageMeta({ title: t('consent.pageTitle'), description: t('consent.pageDescription') })
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const { loadUser } = useAuth()
  const groupId = params.get('group')
  const redirectTo = params.get('redirect') || '/'

  const [group, setGroup] = useState<GroupInfo | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!groupId) {
      setError(t('consent.missingGroupId'))
      setLoading(false)
      return
    }
    apiFetch('/api/auth/group-info')
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setGroup)
      .catch(() => setError(t('consent.loadError')))
      .finally(() => setLoading(false))
  }, [groupId, t])

  async function respond(action: 'grant' | 'reject') {
    if (!groupId) return
    setSubmitting(true)
    setError(null)
    try {
      const resp = await apiFetch(`/api/auth/consent/${groupId}/${action}`, { method: 'POST' })
      if (!resp.ok) throw new Error()
      if (action === 'grant') {
        // AuthContext's user is still null from the earlier consent_required
        // response (loadUser() returns early without setting it) - refresh it
        // now that /me will succeed, or a guarded redirectTo would immediately
        // bounce back to /login on the stale null state.
        await loadUser()
        navigate(redirectTo, { replace: true })
      } else {
        navigate('/consent-rejected', { replace: true })
      }
    } catch {
      setError(t('consent.actionError'))
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-900 dark:text-slate-100">
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('common.loading')}</p>
      </div>
    )
  }

  if (!group) {
    return (
      <div className="flex min-h-screen items-center justify-center px-6 text-center text-slate-900 dark:text-slate-100">
        <p className="text-sm text-red-600 dark:text-red-400">{error || t('consent.notFound')}</p>
      </div>
    )
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 text-slate-900 dark:text-slate-100">
      <h1 className="mb-2 text-2xl font-semibold tracking-tight">{t('consent.title')}</h1>
      <p className="mb-6 text-sm text-slate-600 dark:text-slate-400">
        <strong className="text-slate-800 dark:text-slate-200">{group.name}</strong> {t('consent.requestedBy')}
      </p>

      {group.description && <p className="mb-4 text-sm text-slate-600 dark:text-slate-400">{group.description}</p>}

      <ul className="mb-6 space-y-2">
        {group.scopes.map((scope) => (
          <li key={scope} className="flex items-center gap-2 text-sm">
            <span className="text-emerald-600 dark:text-emerald-400">✓</span>
            {/* Falls back to the raw scope id if no consent.scopes.<scope> translation exists yet. */}
            {t(`consent.scopes.${scope}`, scope)}
          </li>
        ))}
      </ul>

      {error && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{error}</p>}

      <div className="flex gap-3">
        <button
          onClick={() => respond('grant')}
          disabled={submitting}
          className="flex-1 rounded-lg bg-slate-900 px-4 py-2 font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
        >
          {t('consent.grant')}
        </button>
        <button
          onClick={() => respond('reject')}
          disabled={submitting}
          className="flex-1 rounded-lg border border-slate-200 bg-white px-4 py-2 font-medium text-slate-900 disabled:opacity-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100"
        >
          {t('consent.reject')}
        </button>
      </div>
    </div>
  )
}
