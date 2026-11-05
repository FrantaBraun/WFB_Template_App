/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { SignInError, signInErrorMessage, type MfaChallenge, type MfaMethod } from '../api/authFlow'
import { useAuth } from '../context/AuthContext'

/**
 * The second step of a sign-in, for a user who has two-factor authentication:
 * a code from the authenticator app, or - when the account still has unused
 * ones - a backup code. Shared by /login (after the password) and
 * /oauth/callback (after Google), which both end up with the same
 * MfaChallenge. Signing in successfully navigates away (AuthContext), so this
 * only has to show a failure.
 *
 * `onCancel` returns to the first step; given a message when going back is the
 * only way on (the challenge expired after 5 minutes) so the page can show it.
 */
export default function MfaForm({
  challenge,
  onCancel,
}: {
  challenge: MfaChallenge
  onCancel: (message?: string) => void
}) {
  const { t } = useTranslation()
  const { completeMfa } = useAuth()
  const [method, setMethod] = useState<MfaMethod>(challenge.methods[0])
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const otherMethod: MfaMethod | null =
    challenge.methods.length > 1 ? challenge.methods.find((m) => m !== method) ?? null : null

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await completeMfa(challenge, code, method)
      // Signed in: AuthContext has navigated on (or to /consent).
    } catch (err) {
      if (err instanceof SignInError && err.kind === 'expired') {
        // The first step has to be done again - this challenge can no longer be answered.
        onCancel(t('login.mfa.expired'))
        return
      }
      setError(signInErrorMessage(err, t, t('login.failed')))
      if (err instanceof SignInError && err.kind === 'invalid_code') setCode('')
      setLoading(false)
    }
  }

  function switchMethod(next: MfaMethod) {
    setMethod(next)
    setCode('')
    setError(null)
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-sm flex-col justify-center px-6 text-slate-900 dark:text-slate-100">
      <h1 className="mb-2 text-2xl font-semibold tracking-tight">{t('login.mfa.title')}</h1>
      <p className="mb-6 text-sm text-slate-600 dark:text-slate-400">
        {method === 'totp' ? t('login.mfa.totpHint') : t('login.mfa.backupHint')}
      </p>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="mfa-code" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
            {method === 'totp' ? t('login.mfa.totpLabel') : t('login.mfa.backupLabel')}
          </label>
          <input
            id="mfa-code"
            type="text"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            required
            autoFocus
            autoComplete="one-time-code"
            inputMode={method === 'totp' ? 'numeric' : 'text'}
            maxLength={64}
            className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 tracking-widest text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
          />
        </div>

        {error && (
          <p role="alert" className="text-sm text-red-600 dark:text-red-400">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-lg bg-slate-900 px-4 py-2 font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
        >
          {loading ? t('login.mfa.submitting') : t('login.mfa.submit')}
        </button>
      </form>

      <div className="mt-4 flex flex-col items-center gap-2 text-sm">
        {otherMethod && (
          <button
            type="button"
            onClick={() => switchMethod(otherMethod)}
            className="text-slate-600 underline dark:text-slate-400"
          >
            {otherMethod === 'backup_code' ? t('login.mfa.useBackup') : t('login.mfa.useTotp')}
          </button>
        )}
        <button type="button" onClick={() => onCancel()} className="text-slate-600 underline dark:text-slate-400">
          {t('login.mfa.back')}
        </button>
      </div>
    </div>
  )
}
