/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../api/client'
import usePageMeta from '../hooks/usePageMeta'

const inputClass =
  'w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100'

/**
 * Second step of password reset, opened from the e-mail link (?token=).
 * Sets the new password through the backend, which forwards the token to
 * the auth service. A missing token gets its own message, pointing at a
 * new reset request, since the token is single-use and expires.
 */
export default function ResetPassword() {
  const { t } = useTranslation()
  usePageMeta({ title: t('resetPassword.pageTitle'), description: t('resetPassword.pageDescription'), noindex: true })
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    if (newPassword !== confirmPassword) {
      setError(t('resetPassword.mismatch'))
      return
    }
    setLoading(true)
    try {
      const resp = await apiFetch('/api/auth/password-reset/confirm', {
        method: 'POST',
        body: JSON.stringify({ token, new_password: newPassword }),
      })
      if (!resp.ok) throw new Error()
      setDone(true)
    } catch {
      setError(t('resetPassword.failed'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-sm flex-col justify-center px-6 text-slate-900 dark:text-slate-100">
      {done ? (
        <>
          <h1 className="mb-4 text-2xl font-semibold tracking-tight">{t('resetPassword.doneTitle')}</h1>
          <p className="mb-6 text-sm text-slate-600 dark:text-slate-400">{t('resetPassword.doneText')}</p>
          <Link
            to="/login"
            className="block w-full rounded-lg bg-slate-900 px-4 py-2 text-center font-medium text-slate-100 dark:bg-slate-100 dark:text-slate-900"
          >
            {t('resetPassword.signIn')}
          </Link>
        </>
      ) : !token ? (
        <>
          <p className="mb-6 text-sm text-red-600 dark:text-red-400">{t('resetPassword.missingToken')}</p>
          <Link to="/forgot-password" className="text-center text-slate-900 underline dark:text-slate-100">
            {t('resetPassword.requestNew')}
          </Link>
        </>
      ) : (
        <>
          <h1 className="mb-6 text-2xl font-semibold tracking-tight">{t('resetPassword.title')}</h1>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="new-password" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
                {t('resetPassword.newPasswordLabel')}
              </label>
              <input
                id="new-password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={8}
                autoComplete="new-password"
                className={inputClass}
              />
            </div>

            <div>
              <label htmlFor="confirm-password" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
                {t('resetPassword.confirmLabel')}
              </label>
              <input
                id="confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                minLength={8}
                autoComplete="new-password"
                className={inputClass}
              />
            </div>

            {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-slate-900 px-4 py-2 font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
            >
              {loading ? t('resetPassword.submitting') : t('resetPassword.submit')}
            </button>
          </form>
        </>
      )}
    </div>
  )
}
