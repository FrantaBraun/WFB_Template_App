/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'
import usePageMeta from '../../hooks/usePageMeta'
import {
  API_BASE,
  TICKETS_PATH,
  TICKET_TYPES,
  fetchJson,
  formatDate,
  formatDateTime,
  sendJson,
  ticketPath,
  type MailboxStatus,
  type TicketPage,
} from './api'
import {
  StatusBadge,
  TicketsGate,
  TypeBadge,
  cardClass,
  inputClass,
  primaryButtonClass,
  secondaryButtonClass,
  useErrorText,
  useMinutesLabel,
} from './ui'

const PAGE_SIZE = 25

function MailboxBar() {
  const { t, i18n } = useTranslation('tickets')
  const errorText = useErrorText()
  const [status, setStatus] = useState<MailboxStatus | null>(null)
  const [checking, setChecking] = useState(false)
  const [message, setMessage] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null)

  const load = useCallback(async () => {
    try {
      setStatus(await fetchJson<MailboxStatus>(`${API_BASE}/mailbox`))
    } catch {
      setStatus(null)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function checkNow() {
    setChecking(true)
    setMessage(null)
    try {
      const result = await sendJson<{ created: number; attached: number }>(`${API_BASE}/mailbox/poll`, 'POST', {})
      setMessage({ kind: 'ok', text: t('mailbox.checked', { created: result.created, attached: result.attached }) })
    } catch (e) {
      setMessage({ kind: 'error', text: errorText(e, 'mailbox.checkError') })
    } finally {
      setChecking(false)
      load()
    }
  }

  if (!status) return null
  return (
    <div className={`${cardClass} flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 text-sm`}>
      {status.configured ? (
        <>
          <span className="text-slate-700 dark:text-slate-300">
            {t('mailbox.connected', { address: status.address ?? '' })}
            {status.last_checked_at && ` · ${t('mailbox.lastCheck', { time: formatDateTime(status.last_checked_at, i18n.language) })}`}
          </span>
          <button type="button" onClick={checkNow} disabled={checking} className={secondaryButtonClass}>
            {checking ? t('mailbox.checking') : t('mailbox.checkNow')}
          </button>
          {status.last_error && (
            <span role="alert" className="text-red-600 dark:text-red-400">
              {t('mailbox.error')}
            </span>
          )}
        </>
      ) : (
        <span className="text-slate-500 dark:text-slate-400">{t('mailbox.notConfigured')}</span>
      )}
      {message && (
        <span role="status" className={message.kind === 'ok' ? 'text-emerald-700 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}>
          {message.text}
        </span>
      )}
    </div>
  )
}

function TicketList() {
  const { t, i18n } = useTranslation('tickets')
  const minutesLabel = useMinutesLabel()
  const [params, setParams] = useSearchParams()
  const status = params.get('status') ?? 'open'
  const type = params.get('type') ?? ''
  const page = Math.max(1, Number(params.get('page')) || 1)
  const urlQuery = params.get('q') ?? ''
  const [search, setSearch] = useState(urlQuery)
  const [data, setData] = useState<TicketPage | null>(null)
  const [error, setError] = useState(false)

  function update(changes: Record<string, string | null>) {
    const next = new URLSearchParams(params)
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value)
      else next.delete(key)
    }
    setParams(next, { replace: true })
  }

  // The search box is applied after a pause, not on every key.
  useEffect(() => {
    if (search === urlQuery) return
    const timer = setTimeout(() => update({ q: search.trim() || null, page: null }), 300)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search])

  useEffect(() => {
    let cancelled = false
    const query = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) })
    if (status !== 'all') query.set('status', status)
    if (type) query.set('type', type)
    if (urlQuery) query.set('q', urlQuery)
    fetchJson<TicketPage>(`${API_BASE}?${query}`)
      .then((result) => {
        if (!cancelled) {
          setData(result)
          setError(false)
        }
      })
      .catch(() => {
        if (!cancelled) setError(true)
      })
    return () => {
      cancelled = true
    }
  }, [status, type, page, urlQuery])

  const pageCount = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1

  return (
    <div className="mx-auto max-w-5xl space-y-6 px-6 py-12 text-slate-900 dark:text-slate-100">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-3xl font-semibold tracking-tight">{t('list.title')}</h1>
        <Link to={`${TICKETS_PATH}/new`} className={primaryButtonClass}>
          {t('list.new')}
        </Link>
      </div>

      <MailboxBar />

      <div className="grid gap-3 sm:grid-cols-[1fr_auto_auto]">
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t('list.search')}
          aria-label={t('list.search')}
          className={inputClass}
        />
        <select value={status} onChange={(e) => update({ status: e.target.value === 'open' ? null : e.target.value, page: null })} aria-label={t('list.statusFilter')} className={inputClass}>
          <option value="open">{t('status.open')}</option>
          <option value="closed">{t('status.closed')}</option>
          <option value="all">{t('list.allStatuses')}</option>
        </select>
        <select value={type} onChange={(e) => update({ type: e.target.value || null, page: null })} aria-label={t('list.typeFilter')} className={inputClass}>
          <option value="">{t('list.allTypes')}</option>
          {TICKET_TYPES.map((value) => (
            <option key={value} value={value}>
              {t(`type.${value}`)}
            </option>
          ))}
        </select>
      </div>

      {error ? (
        <p role="alert" className="text-red-600 dark:text-red-400">{t('list.loadError')}</p>
      ) : !data ? (
        <p className="text-slate-500 dark:text-slate-400">{t('common.loading')}</p>
      ) : data.items.length === 0 ? (
        <p className="text-slate-500 dark:text-slate-400">{urlQuery || type || status !== 'open' ? t('list.emptyFiltered') : t('list.empty')}</p>
      ) : (
        <ul className={`${cardClass} divide-y divide-slate-200 overflow-hidden dark:divide-slate-800`}>
          {data.items.map((ticket) => (
            <li key={ticket.id}>
              <Link to={ticketPath(ticket.number)} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-800/60">
                <span className="w-20 shrink-0 font-mono text-sm text-slate-500 dark:text-slate-400">#{ticket.number}</span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">{ticket.subject}</span>
                  <span className="block truncate text-sm text-slate-500 dark:text-slate-400">
                    {[
                      ticket.partner?.name ?? ticket.requester_name ?? ticket.requester_email,
                      t(`source.${ticket.source}`),
                      t('list.entries', { count: ticket.entry_count }),
                      formatDate(ticket.last_activity_at, i18n.language),
                    ]
                      .filter(Boolean)
                      .join(' · ')}
                  </span>
                </span>
                {ticket.total_minutes > 0 && (
                  <span className="text-sm text-slate-600 dark:text-slate-300">{minutesLabel(ticket.total_minutes)}</span>
                )}
                <TypeBadge type={ticket.type} />
                <StatusBadge status={ticket.status} />
              </Link>
            </li>
          ))}
        </ul>
      )}

      {data && data.total > data.page_size && (
        <div className="flex items-center justify-between gap-3 text-sm">
          <button type="button" disabled={page <= 1} onClick={() => update({ page: page > 2 ? String(page - 1) : null })} className={secondaryButtonClass}>
            {t('list.previous')}
          </button>
          <span className="text-slate-500 dark:text-slate-400">{t('list.pageOf', { page, pages: pageCount, total: data.total })}</span>
          <button type="button" disabled={page >= pageCount} onClick={() => update({ page: String(page + 1) })} className={secondaryButtonClass}>
            {t('list.next')}
          </button>
        </div>
      )}
    </div>
  )
}

/** /tickets - every ticket, newest activity first, with the mailbox status. */
export default function TicketsPage() {
  const { t } = useTranslation('tickets')
  usePageMeta({ title: t('list.title') })
  return (
    <TicketsGate>
      <TicketList />
    </TicketsGate>
  )
}
