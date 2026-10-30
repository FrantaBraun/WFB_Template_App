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
 * First step of password reset: asks the auth service to e-mail a link to
 * /reset-password. The answer is the same whether or not the address is
 * registered, so the confirmation text says "if an account exists".
 */
export default function ForgotPassword() {
  const { t } = useTranslation()
  usePageMeta({ title: t('forgotPassword.pageTitle'), description: t('forgotPassword.pageDescription'), noindex: true })
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const resp = await apiFetch('/api/auth/password-reset/request', {
        method: 'POST',
        body: JSON.stringify({ email }),
      })
      if (!resp.ok) throw new Error()
      setSent(true)
    } catch {
      setError(t('forgotPassword.failed'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-sm flex-col justify-center px-6 text-slate-900 dark:text-slate-100">
      {sent ? (
        <>
          <h1 className="mb-4 text-2xl font-semibold tracking-tight">{t('forgotPassword.sentTitle')}</h1>
          <p className="text-sm text-slate-600 dark:text-slate-400">{t('forgotPassword.sentText', { email })}</p>
        </>
      ) : (
        <>
          <h1 className="mb-2 text-2xl font-semibold tracking-tight">{t('forgotPassword.title')}</h1>
          <p className="mb-6 text-sm text-slate-600 dark:text-slate-400">{t('forgotPassword.intro')}</p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
                {t('forgotPassword.emailLabel')}
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
              />
            </div>

            {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-slate-900 px-4 py-2 font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
            >
              {loading ? t('forgotPassword.submitting') : t('forgotPassword.submit')}
            </button>
          </form>
        </>
      )}

      <p className="mt-6 text-center text-sm text-slate-600 dark:text-slate-400">
        <Link to="/login" className="text-slate-900 underline dark:text-slate-100">
          {t('forgotPassword.backToLogin')}
        </Link>
      </p>
    </div>
  )
}
