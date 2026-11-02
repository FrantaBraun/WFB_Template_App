/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { apiFetch } from '../api/client'
import { useAuth } from '../context/AuthContext'
import usePageMeta from '../hooks/usePageMeta'

interface AuthorMessageData {
  id: string
  sender_name: string | null
  sender_email: string | null
  target: { kind: 'document' | 'collection'; id: string; title: string }
  body: string
  created_at: string
}

const PAGE_SIZE = 50

function formatDateTime(iso: string, locale: string): string {
  return new Date(iso).toLocaleString(locale, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/**
 * The messages other users wrote to the signed-in user as the author of a
 * document or collection (GET /api/author-messages) - where the header bell's
 * message notifications lead. The text is always rendered as plain text, and
 * the sender's address (they were told it is passed on) only becomes a mailto
 * link to answer by e-mail.
 */
export default function AuthorMessages() {
  const { t, i18n } = useTranslation()
  usePageMeta({
    title: t('author.messages.pageTitle'),
    description: t('author.messages.pageDescription'),
    noindex: true,
  })
  const { user, loading: authLoading } = useAuth()
  const navigate = useNavigate()

  const [messages, setMessages] = useState<AuthorMessageData[] | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!authLoading && !user) navigate('/login', { replace: true })
  }, [authLoading, user, navigate])

  async function load(offset: number): Promise<AuthorMessageData[]> {
    const resp = await apiFetch(`/api/author-messages?limit=${PAGE_SIZE}&offset=${offset}`)
    if (!resp.ok) throw new Error()
    return resp.json()
  }

  useEffect(() => {
    if (!user) return
    let cancelled = false
    load(0)
      .then((page) => {
        if (cancelled) return
        setMessages(page)
        setHasMore(page.length === PAGE_SIZE)
      })
      .catch(() => {
        if (!cancelled) setError(t('author.messages.loadError'))
      })
    return () => {
      cancelled = true
    }
  }, [user, t])

  async function handleLoadMore() {
    if (!messages) return
    setLoadingMore(true)
    setError(null)
    try {
      const page = await load(messages.length)
      setMessages([...messages, ...page])
      setHasMore(page.length === PAGE_SIZE)
    } catch {
      setError(t('author.messages.loadError'))
    } finally {
      setLoadingMore(false)
    }
  }

  if (authLoading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-900 dark:text-slate-100">
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('common.loading')}</p>
      </div>
    )
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 px-6 py-16 text-slate-900 dark:text-slate-100">
      <h1 className="text-2xl font-semibold tracking-tight">{t('author.messages.pageTitle')}</h1>

      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
      {messages === null && !error && <p className="text-sm text-slate-600 dark:text-slate-400">{t('common.loading')}</p>}
      {messages && messages.length === 0 && (
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('author.messages.empty')}</p>
      )}

      {messages && messages.length > 0 && (
        <ul className="space-y-4">
          {messages.map((message) => {
            const sender = message.sender_name ?? t('author.messages.unknownSender')
            const targetPath = message.target.kind === 'document' ? 'api-docs' : 'collections'
            const replySubject = encodeURIComponent(`Re: ${message.target.title}`)
            return (
              <li
                key={message.id}
                className="space-y-3 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900"
              >
                <div className="text-sm">
                  <p className="break-words font-medium text-slate-900 dark:text-slate-100">
                    {t('author.messages.from', { name: sender })}
                  </p>
                  <p className="break-words text-slate-500 dark:text-slate-400">
                    {t(message.target.kind === 'document' ? 'author.messages.aboutDocument' : 'author.messages.aboutCollection')}
                    {': '}
                    <Link to={`/${targetPath}/${message.target.id}`} className="underline">
                      {message.target.title}
                    </Link>
                    {' · '}
                    {formatDateTime(message.created_at, i18n.language)}
                  </p>
                </div>
                <p className="whitespace-pre-wrap break-words text-sm text-slate-800 dark:text-slate-200">{message.body}</p>
                {message.sender_email && (
                  <a
                    href={`mailto:${message.sender_email}?subject=${replySubject}`}
                    className="inline-block rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-700 dark:border-slate-700 dark:text-slate-300"
                  >
                    {t('author.messages.reply')}
                  </a>
                )}
              </li>
            )
          })}
        </ul>
      )}

      {hasMore && (
        <button
          type="button"
          onClick={handleLoadMore}
          disabled={loadingMore}
          className="self-start rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-700 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300"
        >
          {loadingMore ? t('common.loading') : t('author.messages.loadMore')}
        </button>
      )}
    </div>
  )
}
