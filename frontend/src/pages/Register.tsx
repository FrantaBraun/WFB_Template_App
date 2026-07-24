/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { apiFetch } from '../api/client'
import usePageMeta from '../hooks/usePageMeta'

/**
 * Account creation form. Registration alone issues no tokens - on success the
 * user is shown a confirmation and must log in separately afterward.
 */
export default function Register() {
  const { t, i18n } = useTranslation()
  usePageMeta({ title: t('register.pageTitle'), description: t('register.pageDescription') })

  const [email, setEmail] = useState('')
  const [login, setLogin] = useState('')
  const [password, setPassword] = useState('')
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const resp = await apiFetch('/api/auth/register', {
        method: 'POST',
        body: JSON.stringify({
          email,
          login,
          password,
          first_name: firstName,
          last_name: lastName,
          language_code: i18n.language,
        }),
      })
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}))
        throw new Error(typeof body.detail === 'string' ? body.detail : t('register.failed'))
      }
      setSuccess(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('register.failed'))
    } finally {
      setLoading(false)
    }
  }

  if (success) {
    return (
      <div className="mx-auto flex min-h-screen max-w-sm flex-col justify-center px-6 text-center text-slate-900 dark:text-slate-100">
        <h1 className="mb-2 text-2xl font-semibold tracking-tight">{t('register.successTitle')}</h1>
        <p className="mb-6 text-sm text-slate-600 dark:text-slate-400">{t('register.successMessage')}</p>
        <Link
          to="/login"
          className="w-full rounded-lg bg-slate-900 px-4 py-2 font-medium text-slate-100 dark:bg-slate-100 dark:text-slate-900"
        >
          {t('register.loginLink')}
        </Link>
      </div>
    )
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-sm flex-col justify-center px-6 text-slate-900 dark:text-slate-100">
      <h1 className="mb-6 text-2xl font-semibold tracking-tight">{t('register.title')}</h1>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="email" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
            {t('register.emailLabel')}
          </label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
          />
        </div>

        <div>
          <label htmlFor="login" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
            {t('register.loginLabel')}
          </label>
          <input
            id="login"
            type="text"
            value={login}
            onChange={(e) => setLogin(e.target.value)}
            required
            className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
          />
        </div>

        <div>
          <label htmlFor="password" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
            {t('register.passwordLabel')}
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

        <div className="flex gap-3">
          <div className="flex-1">
            <label htmlFor="firstName" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
              {t('register.firstNameLabel')}
            </label>
            <input
              id="firstName"
              type="text"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              required
              className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
            />
          </div>
          <div className="flex-1">
            <label htmlFor="lastName" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
              {t('register.lastNameLabel')}
            </label>
            <input
              id="lastName"
              type="text"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              required
              className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
            />
          </div>
        </div>

        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-lg bg-slate-900 px-4 py-2 font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
        >
          {loading ? t('register.submitting') : t('register.submit')}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-slate-600 dark:text-slate-400">
        {t('register.haveAccount')}{' '}
        <Link to="/login" className="text-slate-900 underline dark:text-slate-100">
          {t('common.login')}
        </Link>
      </p>
    </div>
  )
}
