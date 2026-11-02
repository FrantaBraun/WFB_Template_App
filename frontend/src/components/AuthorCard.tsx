/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation } from 'react-router-dom'
import { apiFetch } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { requestNotificationsRefresh } from '../utils/notificationsRefresh'
import { rememberReturnPath } from '../utils/returnPath'

/** The `author` block of a document's / collection's detail (backend AuthorOut). */
export interface AuthorData {
  display_name: string | null
  team_name: string | null
  accepts_messages: boolean
  is_self: boolean
}

/** Same limit as the backend's MAX_MESSAGE_LENGTH (app/services/author_contact.py). */
const MAX_MESSAGE_LENGTH = 2000

type Outcome = { type: 'success' | 'error'; text: string } | null

/**
 * Who made this document / collection and the way to write to them. The
 * backend sends only a name and the owning team - never an e-mail address -
 * and delivers the message itself (an e-mail with the sender's address in
 * Reply-To, plus a notification in the author's bell), so the form below
 * says up front that the sender's name and address are passed on.
 *
 * `contactPath` is the endpoint to POST to (`/api/api-docs/:id/contact-author`
 * or `/api/collections/:id/contact-author`); `kind` only picks wording. An
 * anonymous visitor sees the author but is sent to sign in, and the author
 * is told there is nobody to write to - `is_self` is computed by the server.
 */
export default function AuthorCard({
  author,
  contactPath,
  kind,
}: {
  author: AuthorData
  contactPath: string
  kind: 'document' | 'collection'
}) {
  const { t } = useTranslation()
  const { user } = useAuth()
  const location = useLocation()

  const [open, setOpen] = useState(false)
  const [message, setMessage] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [outcome, setOutcome] = useState<Outcome>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!message.trim()) return
    setSending(true)
    setError(null)
    try {
      const resp = await apiFetch(contactPath, { method: 'POST', body: JSON.stringify({ message }) })
      if (resp.status === 429) throw new Error(t('author.contact.rateLimited'))
      if (resp.status === 403) throw new Error(t('author.contact.notAccepting'))
      if (!resp.ok) throw new Error(t('author.contact.error'))
      const result: { email_sent: boolean } = await resp.json()
      setOutcome({
        type: 'success',
        text: t(result.email_sent ? 'author.contact.sent' : 'author.contact.sentInAppOnly'),
      })
      setMessage('')
      setOpen(false)
      // Nothing new for the sender, but a user writing to a colleague on a
      // page they also watch should see their own bell stay accurate.
      requestNotificationsRefresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : t('author.contact.error'))
    } finally {
      setSending(false)
    }
  }

  const name = author.display_name ?? t('author.unknownName')

  return (
    <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
        {t('author.title')}
      </h2>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
        <dt className="text-slate-500 dark:text-slate-400">{t('author.nameLabel')}</dt>
        <dd className="break-words font-medium text-slate-900 dark:text-slate-100">
          {name}
          {author.is_self && <span className="ml-2 text-xs font-normal text-slate-500 dark:text-slate-400">({t('author.you')})</span>}
        </dd>
        {author.team_name && (
          <>
            <dt className="text-slate-500 dark:text-slate-400">{t('author.teamLabel')}</dt>
            <dd className="break-words text-slate-900 dark:text-slate-100">{author.team_name}</dd>
          </>
        )}
      </dl>

      {outcome && (
        <p
          role="status"
          className={`text-sm ${
            outcome.type === 'success' ? 'text-emerald-700 dark:text-emerald-300' : 'text-red-600 dark:text-red-400'
          }`}
        >
          {outcome.text}
        </p>
      )}

      {author.is_self ? null : !author.accepts_messages ? (
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('author.contact.notAccepting')}</p>
      ) : !user ? (
        <p className="text-sm text-slate-600 dark:text-slate-400">
          <Link
            to="/login"
            onClick={() => rememberReturnPath(location.pathname + location.search)}
            className="text-slate-900 underline dark:text-slate-100"
          >
            {t('author.contact.signIn')}
          </Link>{' '}
          {t('author.contact.signInSuffix')}
        </p>
      ) : !open ? (
        <button
          type="button"
          onClick={() => {
            setOpen(true)
            setOutcome(null)
          }}
          className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-700 dark:border-slate-700 dark:text-slate-300"
        >
          {t('author.contact.open')}
        </button>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-3 border-t border-slate-200 pt-4 dark:border-slate-800">
          <div>
            <label htmlFor="author-message" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
              {t(kind === 'document' ? 'author.contact.labelDocument' : 'author.contact.labelCollection', { name })}
            </label>
            <textarea
              id="author-message"
              rows={5}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              maxLength={MAX_MESSAGE_LENGTH}
              required
              className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
            />
            <p className="mt-1 text-right text-xs text-slate-500 dark:text-slate-400">
              {message.length} / {MAX_MESSAGE_LENGTH}
            </p>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400">{t('author.contact.privacyNote')}</p>
          {error && (
            <p role="alert" className="text-sm text-red-600 dark:text-red-400">
              {error}
            </p>
          )}
          <div className="flex gap-3">
            <button
              type="submit"
              disabled={sending || !message.trim()}
              className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-700 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300"
            >
              {sending ? t('author.contact.sending') : t('author.contact.send')}
            </button>
            <button
              type="button"
              onClick={() => {
                setOpen(false)
                setError(null)
              }}
              disabled={sending}
              className="rounded-lg px-3 py-1.5 text-sm text-slate-600 underline disabled:opacity-50 dark:text-slate-400"
            >
              {t('common.cancel')}
            </button>
          </div>
        </form>
      )}
    </div>
  )
}
