/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { API_BASE, TICKETS_PATH, fetchJson, formatDate, ticketPath, type TicketPage } from './api'
import { StatusBadge, TypeBadge, cardClass, secondaryButtonClass, useMinutesLabel } from './ui'

const SHOWN = 10

/**
 * The tickets of a CRM partner, on the partner's page: this module's
 * contribution to the CRM's "crm.partner" slot (context `{ partner }`, the
 * partner being shown). Only mounted by the CRM's own pages, which are behind
 * its administrators-only gate; the backend checks User.is_admin regardless.
 */
export default function PartnerTickets({ context }: { context: { partner?: { id: string } } }) {
  const { t, i18n } = useTranslation('tickets')
  const minutesLabel = useMinutesLabel()
  const partnerId = context.partner?.id
  const [data, setData] = useState<TicketPage | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    if (!partnerId) return
    let cancelled = false
    fetchJson<TicketPage>(`${API_BASE}?partner_id=${partnerId}&page_size=${SHOWN}`)
      .then((result) => {
        if (!cancelled) setData(result)
      })
      .catch(() => {
        if (!cancelled) setError(true)
      })
    return () => {
      cancelled = true
    }
  }, [partnerId])

  if (!partnerId) return null

  return (
    <section>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold tracking-tight">{t('partnerPanel.title')}</h2>
        <Link to={`${TICKETS_PATH}/new?partner=${partnerId}`} className={secondaryButtonClass}>{t('list.new')}</Link>
      </div>
      {error ? (
        <p role="alert" className="text-red-600 dark:text-red-400">{t('list.loadError')}</p>
      ) : !data ? (
        <p className="text-slate-500 dark:text-slate-400">{t('common.loading')}</p>
      ) : data.items.length === 0 ? (
        <p className="text-slate-500 dark:text-slate-400">{t('partnerPanel.empty')}</p>
      ) : (
        <>
          <ul className={`${cardClass} divide-y divide-slate-200 overflow-hidden dark:divide-slate-800`}>
            {data.items.map((ticket) => (
              <li key={ticket.id}>
                <Link to={ticketPath(ticket.number)} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-800/60">
                  <span className="w-20 shrink-0 font-mono text-sm text-slate-500 dark:text-slate-400">#{ticket.number}</span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{ticket.subject}</span>
                    <span className="block text-sm text-slate-500 dark:text-slate-400">
                      {[formatDate(ticket.last_activity_at, i18n.language), ticket.total_minutes > 0 ? minutesLabel(ticket.total_minutes) : null].filter(Boolean).join(' · ')}
                    </span>
                  </span>
                  <TypeBadge type={ticket.type} />
                  <StatusBadge status={ticket.status} />
                </Link>
              </li>
            ))}
          </ul>
          {data.total > data.items.length && (
            <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">{t('partnerPanel.more', { count: data.total - data.items.length })}</p>
          )}
        </>
      )}
    </section>
  )
}
