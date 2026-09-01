/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../api/client'
import { useAuth } from '../../context/AuthContext'
import usePageMeta from '../../hooks/usePageMeta'

/**
 * Contact form - subject + message always, plus a required reply-to email
 * when signed out (the backend derives both name and email from the JWT
 * when signed in, so those fields are hidden rather than merely optional).
 * A successful submit swaps the form out for a thank-you message rather
 * than resetting it, matching the spec's "instead of the form".
 */
export default function ContactPage() {
  const { t } = useTranslation('kontaktni_formular')
  const { user } = useAuth()
  usePageMeta({ title: t('page.title') })

  const [subject, setSubject] = useState('')
  const [message, setMessage] = useState('')
  const [replyTo, setReplyTo] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sent, setSent] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const resp = await apiFetch('/api/modules/kontaktni_formular/submit', {
        method: 'POST',
        body: JSON.stringify({ subject, message, reply_to: user ? undefined : replyTo }),
      })
      if (!resp.ok) throw new Error()
      setSent(true)
    } catch {
      setError(t('page.error'))
    } finally {
      setSubmitting(false)
    }
  }

  if (sent) {
    return (
      <div className="mx-auto flex max-w-lg flex-col items-center gap-4 px-6 py-24 text-center text-slate-900 dark:text-slate-100">
        <h1 className="text-2xl font-semibold tracking-tight">{t('page.thanksTitle')}</h1>
        <p className="text-slate-600 dark:text-slate-400">{t('page.thanksMessage')}</p>
        <Link
          to="/"
          className="rounded-lg bg-slate-900 px-4 py-2 font-medium text-slate-100 dark:bg-slate-100 dark:text-slate-900"
        >
          {t('page.backHome')}
        </Link>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-lg px-6 py-16 text-slate-900 dark:text-slate-100">
      <h1 className="mb-6 text-2xl font-semibold tracking-tight">{t('page.title')}</h1>

      <form onSubmit={handleSubmit} className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
        {user && (
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {t('page.signedInAs', { name: user.first_name || user.email })}
          </p>
        )}

        <div>
          <label htmlFor="contact-subject" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
            {t('page.subjectLabel')}
          </label>
          <input
            id="contact-subject"
            required
            maxLength={200}
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
          />
        </div>

        <div>
          <label htmlFor="contact-message" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
            {t('page.messageLabel')}
          </label>
          <textarea
            id="contact-message"
            required
            rows={6}
            maxLength={5000}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
          />
        </div>

        {!user && (
          <div>
            <label htmlFor="contact-reply-to" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
              {t('page.emailLabel')}
            </label>
            <input
              id="contact-reply-to"
              type="email"
              required
              value={replyTo}
              onChange={(e) => setReplyTo(e.target.value)}
              className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
            />
          </div>
        )}

        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="rounded-lg bg-slate-900 px-4 py-2 font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
        >
          {submitting ? t('page.submitting') : t('page.submit')}
        </button>
      </form>
    </div>
  )
}
