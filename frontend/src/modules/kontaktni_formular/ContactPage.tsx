/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../api/client'
import { useAuth } from '../../context/AuthContext'
import usePageMeta from '../../hooks/usePageMeta'

interface ContactInfo {
  title: string
  intro: string
  aside: string
  details: { email: string | null; address: string | null; github_url: string | null; linkedin_url: string | null }
}

/** The backend already limits these to http(s) URLs; checked again here because they end up in an href. */
const isWebUrl = (url: string | null | undefined): url is string => !!url && /^https?:\/\//i.test(url)

/** "https://www.github.com/x" -> "github.com/x", for showing a link as text. */
const shortUrl = (url: string) => url.replace(/^https?:\/\/(www\.)?/i, '').replace(/\/$/, '')

/** Paragraphs are separated by a blank line in the configured texts. */
const paragraphsOf = (text: string | undefined) =>
  (text ?? '')
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean)

/**
 * Contact form - subject + message always, plus a required reply-to email
 * when signed out (the backend derives both name and email from the JWT
 * when signed in, so those fields are hidden rather than merely optional).
 * A successful submit swaps the form out for a thank-you message rather
 * than resetting it, matching the spec's "instead of the form".
 *
 * Around the form it shows what the deployment configured (GET /info): a
 * heading and an introduction, contact details (address, GitHub, LinkedIn,
 * and the email when the module config allows it) and a short note. With
 * none of that configured - or if the request fails - the page is just the
 * form, as it was before /info existed.
 */
export default function ContactPage() {
  const { t, i18n } = useTranslation('kontaktni_formular')
  const { user } = useAuth()
  const language = i18n.resolvedLanguage ?? i18n.language
  const [info, setInfo] = useState<ContactInfo | null>(null)

  useEffect(() => {
    let cancelled = false
    apiFetch(`/api/modules/kontaktni_formular/info?language=${encodeURIComponent(language)}`)
      .then((resp) => (resp.ok ? resp.json() : null))
      .then((data: ContactInfo | null) => {
        if (!cancelled) setInfo(data)
      })
      .catch(() => {
        // the form works without the surrounding texts
      })
    return () => {
      cancelled = true
    }
  }, [language])

  const heading = info?.title || t('page.title')
  const introParagraphs = paragraphsOf(info?.intro)
  const asideParagraphs = paragraphsOf(info?.aside)
  const details = info?.details
  const detailRows = [
    {
      key: 'email',
      label: t('page.emailDetail'),
      value: details?.email,
      href: details?.email ? `mailto:${details.email}` : null,
    },
    { key: 'address', label: t('page.addressDetail'), value: details?.address, href: null },
    {
      key: 'github',
      label: t('page.githubDetail'),
      value: isWebUrl(details?.github_url) ? shortUrl(details.github_url) : null,
      href: details?.github_url,
    },
    {
      key: 'linkedin',
      label: t('page.linkedinDetail'),
      value: isWebUrl(details?.linkedin_url) ? shortUrl(details.linkedin_url) : null,
      href: details?.linkedin_url,
    },
  ].filter((row) => row.value)
  const hasSide = detailRows.length > 0 || asideParagraphs.length > 0

  usePageMeta({ title: heading, description: introParagraphs[0]?.slice(0, 160) || t('page.metaDescription') })

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
        // language picks the confirmation email's template on the backend
        // (falling back to its configured default_language)
        body: JSON.stringify({
          subject,
          message,
          reply_to: user ? undefined : replyTo,
          language,
        }),
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
    <div className={`mx-auto px-6 py-16 text-slate-900 dark:text-slate-100 ${hasSide ? 'max-w-4xl' : 'max-w-lg'}`}>
      <h1 className="mb-4 text-2xl font-semibold tracking-tight">{heading}</h1>
      {introParagraphs.length > 0 && (
        <div className="mb-8 max-w-2xl space-y-3 text-slate-600 dark:text-slate-400">
          {introParagraphs.map((paragraph, i) => (
            <p key={i} className="whitespace-pre-line">{paragraph}</p>
          ))}
        </div>
      )}

      <div className={hasSide ? 'grid gap-8 md:grid-cols-[minmax(0,1fr)_18rem] md:items-start' : ''}>
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

        {hasSide && (
          <aside className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
            {detailRows.length > 0 && (
              <>
                <h2 className="text-lg font-semibold tracking-tight">{t('page.detailsHeading')}</h2>
                <dl className="space-y-3">
                  {detailRows.map((row) => (
                    <div key={row.key}>
                      <dt className="text-sm text-slate-500 dark:text-slate-400">{row.label}</dt>
                      <dd className="break-words">
                        {row.href ? (
                          <a
                            href={row.href}
                            {...(row.key === 'email' ? {} : { target: '_blank', rel: 'noopener noreferrer' })}
                            className="font-medium text-slate-900 underline decoration-slate-300 underline-offset-4 hover:decoration-slate-900 dark:text-slate-100 dark:decoration-slate-600 dark:hover:decoration-slate-100"
                          >
                            {row.value}
                          </a>
                        ) : (
                          <span className="whitespace-pre-line">{row.value}</span>
                        )}
                      </dd>
                    </div>
                  ))}
                </dl>
              </>
            )}
            {asideParagraphs.length > 0 && (
              <div className="space-y-3 text-sm text-slate-600 dark:text-slate-400">
                {asideParagraphs.map((paragraph, i) => (
                  <p key={i} className="whitespace-pre-line">{paragraph}</p>
                ))}
              </div>
            )}
          </aside>
        )}
      </div>
    </div>
  )
}
