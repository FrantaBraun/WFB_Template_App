/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { SignInError, signInErrorMessage, type MfaChallenge } from '../api/authFlow'
import MfaForm from '../components/MfaForm'
import { useAuth } from '../context/AuthContext'
import usePageMeta from '../hooks/usePageMeta'

/**
 * Landing page for the Google redirect. The auth service appends a short-lived,
 * single-use `code` (never tokens) to the address; it is traded for tokens
 * through our backend at once. For a user with two-factor authentication the
 * trade answers with a challenge instead, and this page asks for the code
 * (MfaForm) - the Google code is spent by then, so a failure sends the visitor
 * back to /login rather than retrying it.
 */
export default function OAuthCallback() {
  const { t } = useTranslation()
  usePageMeta({ title: t('oauthCallback.pageTitle'), noindex: true })
  const navigate = useNavigate()
  const { signInWithGoogleCode } = useAuth()
  const [challenge, setChallenge] = useState<MfaChallenge | null>(null)
  const ran = useRef(false)

  useEffect(() => {
    // StrictMode/dev double-invokes effects; without this guard the code would
    // be redeemed twice - and it works only once.
    if (ran.current) return
    ran.current = true

    const params = new URLSearchParams(window.location.search)
    const code = params.get('code')
    const oauthError = params.get('error')

    // Drop the code from the address bar and the history at once: it is a
    // credential, and it must not survive in a bookmark, a screenshot or a reload.
    window.history.replaceState(window.history.state, '', window.location.pathname)

    if (oauthError || !code) {
      navigate('/login', { state: { flash: oauthError || t('oauthCallback.googleFailed') } })
      return
    }

    signInWithGoogleCode(code)
      .then((next) => {
        // Signed in (AuthContext navigated on, or to /consent when consent is
        // pending) - nothing to do. A challenge means a second factor is due.
        if (next) setChallenge(next)
      })
      .catch((err) => {
        // A 401 here is a code that is unknown, expired or already used - the
        // sign-in has to start over from the sign-in page. The specific
        // failures (rate limit, a stronger sign-in demanded) are worded
        // as such; the rest is the plain "Google sign-in failed", not the auth
        // service's English text.
        const specific = err instanceof SignInError && err.kind !== 'other'
        navigate('/login', {
          state: { flash: specific ? signInErrorMessage(err, t, '') : t('oauthCallback.googleFailed') },
          replace: true,
        })
      })
  }, [navigate, signInWithGoogleCode, t])

  if (challenge) {
    return (
      <MfaForm
        challenge={challenge}
        onCancel={(message) => navigate('/login', { state: message ? { flash: message } : undefined, replace: true })}
      />
    )
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 px-6 text-center text-slate-900 dark:text-slate-100">
      <p className="text-sm text-slate-600 dark:text-slate-400">{t('oauthCallback.signingIn')}</p>
    </div>
  )
}
