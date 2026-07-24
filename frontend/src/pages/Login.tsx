/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation } from 'react-router-dom'
import { getAuthUrl } from '../api/client'
import { useAuth } from '../context/AuthContext'
import usePageMeta from '../hooks/usePageMeta'

// Redirects straight to the auth service - it owns the entire Google exchange
// and redirects back to /oauth/callback with tokens, no backend involvement.
function buildGoogleLoginUrl() {
  const redirectUri = `${window.location.origin}/oauth/callback`
  return `${getAuthUrl()}/auth/google?redirect_uri=${encodeURIComponent(redirectUri)}`
}

/**
 * Email/password + Google OAuth entry point. On consent_required, login()
 * (in AuthContext) redirects to /consent internally and returns normally
 * rather than throwing, so the catch block below never sees that case.
 */
export default function Login() {
  const { t } = useTranslation()
  usePageMeta({ title: t('login.pageTitle'), description: t('login.pageDescription') })
  const { login } = useAuth()
  const location = useLocation()
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(
    (location.state as { flash?: string } | null)?.flash ?? null,
  )
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await login(identifier, password)
      // On consent_required, login() already redirected to /consent - it
      // returns normally rather than throwing, so nothing more to do here.
    } catch (err) {
      setError(err instanceof Error ? err.message : t('login.failed'))
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-sm flex-col justify-center px-6 text-slate-900 dark:text-slate-100">
      <h1 className="mb-6 text-2xl font-semibold tracking-tight">{t('login.title')}</h1>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="identifier" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
            {t('login.identifierLabel')}
          </label>
          <input
            id="identifier"
            type="text"
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
            required
            className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
          />
        </div>

        <div>
          <label htmlFor="password" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
            {t('login.passwordLabel')}
          </label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
          />
        </div>

        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-lg bg-slate-900 px-4 py-2 font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
        >
          {loading ? t('login.submitting') : t('login.submit')}
        </button>
      </form>

      <div className="my-4 flex items-center gap-3 text-xs uppercase tracking-wide text-slate-500">
        <div className="h-px flex-1 bg-slate-200 dark:bg-slate-800" />
        {t('login.or')}
        <div className="h-px flex-1 bg-slate-200 dark:bg-slate-800" />
      </div>

      <a
        href={buildGoogleLoginUrl()}
        className="w-full rounded-lg border border-slate-200 bg-white px-4 py-2 text-center font-medium text-slate-900 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100"
      >
        {t('login.google')}
      </a>

      <p className="mt-6 text-center text-sm text-slate-600 dark:text-slate-400">
        {t('login.noAccount')}{' '}
        <Link to="/register" className="text-slate-900 underline dark:text-slate-100">
          {t('login.registerLink')}
        </Link>
      </p>
    </div>
  )
}
