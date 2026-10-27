/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'
import usePageMeta from '../../hooks/usePageMeta'
import {
  API_BASE,
  TICKETS_PATH,
  TICKET_TYPES,
  deleteRequest,
  errorStatus,
  fetchJson,
  formatDateTime,
  partnerPath,
  sendJson,
  type PartnerOption,
  type TicketDetail,
  type TicketStatus,
  type TicketType,
} from './api'
import EntryView from './EntryView'
import TicketComposer from './TicketComposer'
import {
  BackLink,
  PageMessage,
  PartnerPicker,
  StatusBadge,
  TicketsGate,
  TypeBadge,
  cardClass,
  dangerButtonClass,
  inputClass,
  labelClass,
  primaryButtonClass,
  secondaryButtonClass,
  useCrmEnabled,
  useErrorText,
  useMinutesLabel,
} from './ui'

function HeaderEditor({ ticket, onSaved, onCancel }: { ticket: TicketDetail; onSaved: (next: TicketDetail) => void; onCancel: () => void }) {
  const { t } = useTranslation('tickets')
  const errorText = useErrorText()
  const crmEnabled = useCrmEnabled()
  const [subject, setSubject] = useState(ticket.subject)
  const [requesterName, setRequesterName] = useState(ticket.requester_name ?? '')
  const [requesterEmail, setRequesterEmail] = useState(ticket.requester_email ?? '')
  const [partner, setPartner] = useState<PartnerOption | null>(
    ticket.partner ? { id: ticket.partner.id, name: ticket.partner.name, company: ticket.partner.company, email: null } : null,
  )
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      onSaved(
        await sendJson<TicketDetail>(`${API_BASE}/${ticket.number}`, 'PATCH', {
          subject: subject.trim(),
          requester_name: requesterName.trim() || null,
          requester_email: requesterEmail.trim() || null,
          // Only while the CRM is on: with it off the link can't be validated, so it is left as it is.
          ...(crmEnabled ? { partner_id: partner?.id ?? null } : {}),
        }),
      )
    } catch (e) {
      setError(errorText(e, 'detail.saveError'))
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="edit-subject" className={labelClass}>{t('fields.subject')}</label>
        <input id="edit-subject" required maxLength={200} value={subject} onChange={(e) => setSubject(e.target.value)} className={inputClass} />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="edit-requester-name" className={labelClass}>{t('fields.requesterName')}</label>
          <input id="edit-requester-name" maxLength={200} value={requesterName} onChange={(e) => setRequesterName(e.target.value)} className={inputClass} />
        </div>
        <div>
          <label htmlFor="edit-requester-email" className={labelClass}>{t('fields.requesterEmail')}</label>
          <input id="edit-requester-email" type="email" value={requesterEmail} onChange={(e) => setRequesterEmail(e.target.value)} className={inputClass} />
        </div>
      </div>
      {crmEnabled && (
        <div>
          <span className={labelClass}>{t('fields.partner')}</span>
          <PartnerPicker value={partner} onChange={setPartner} />
        </div>
      )}
      {error && <p role="alert" className="text-sm text-red-600 dark:text-red-400">{error}</p>}
      <div className="flex gap-2">
        <button type="submit" disabled={saving || !subject.trim()} className={primaryButtonClass}>{saving ? t('common.saving') : t('common.save')}</button>
        <button type="button" onClick={onCancel} className={secondaryButtonClass}>{t('common.cancel')}</button>
      </div>
    </form>
  )
}

function TicketDetailView({ number }: { number: number }) {
  const { t, i18n } = useTranslation('tickets')
  const errorText = useErrorText()
  const minutesLabel = useMinutesLabel()
  const crmEnabled = useCrmEnabled()
  const navigate = useNavigate()
  const [ticket, setTicket] = useState<TicketDetail | null>(null)
  const [loadError, setLoadError] = useState<'notFound' | 'error' | null>(null)
  const [editing, setEditing] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setTicket(await fetchJson<TicketDetail>(`${API_BASE}/${number}`))
      setLoadError(null)
    } catch (e) {
      setLoadError(errorStatus(e) === 404 ? 'notFound' : 'error')
    }
  }, [number])

  useEffect(() => {
    load()
  }, [load])

  usePageMeta({ title: ticket ? `#${ticket.number} ${ticket.subject}` : t('list.title') })

  if (loadError) return <PageMessage error>{t(loadError === 'notFound' ? 'detail.notFound' : 'detail.loadError')}</PageMessage>
  if (!ticket) return <PageMessage>{t('common.loading')}</PageMessage>

  async function change(changes: { type?: TicketType; status?: TicketStatus }) {
    setActionError(null)
    try {
      setTicket(await sendJson<TicketDetail>(`${API_BASE}/${number}`, 'PATCH', changes))
    } catch (e) {
      setActionError(errorText(e, 'detail.saveError'))
    }
  }

  async function handleDelete() {
    if (!window.confirm(t('detail.confirmDelete'))) return
    setActionError(null)
    try {
      await deleteRequest(`${API_BASE}/${number}`)
      navigate(TICKETS_PATH)
    } catch (e) {
      setActionError(errorText(e, 'detail.deleteError'))
    }
  }

  const requester = [ticket.requester_name, ticket.requester_email ? `<${ticket.requester_email}>` : null].filter(Boolean).join(' ')

  return (
    <div className="mx-auto max-w-4xl space-y-8 px-6 py-12 text-slate-900 dark:text-slate-100">
      <div className="space-y-3">
        <BackLink to={TICKETS_PATH}>{t('detail.backToList')}</BackLink>

        <div className={`${cardClass} space-y-4 p-6`}>
          {editing ? (
            <HeaderEditor
              ticket={ticket}
              onSaved={(next) => {
                setTicket(next)
                setEditing(false)
              }}
              onCancel={() => setEditing(false)}
            />
          ) : (
            <>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-mono text-sm text-slate-500 dark:text-slate-400">#{ticket.number}</p>
                  <h1 className="break-words text-2xl font-semibold tracking-tight">{ticket.subject}</h1>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <StatusBadge status={ticket.status} />
                  <button type="button" onClick={() => change({ status: ticket.status === 'open' ? 'closed' : 'open' })} className={secondaryButtonClass}>
                    {t(ticket.status === 'open' ? 'detail.close' : 'detail.reopen')}
                  </button>
                  <button type="button" onClick={() => setEditing(true)} className={secondaryButtonClass}>{t('common.edit')}</button>
                  <button type="button" onClick={handleDelete} className={dangerButtonClass}>{t('common.delete')}</button>
                </div>
              </div>

              <dl className="grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
                <div>
                  <dt className="text-slate-500 dark:text-slate-400">{t('fields.type')}</dt>
                  <dd>
                    <select
                      value={ticket.type}
                      onChange={(e) => change({ type: e.target.value as TicketType })}
                      aria-label={t('fields.type')}
                      className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-1 dark:border-slate-800 dark:bg-slate-950"
                    >
                      {TICKET_TYPES.map((value) => (
                        <option key={value} value={value}>{t(`type.${value}`)}</option>
                      ))}
                    </select>
                    <span className="ms-2 align-middle"><TypeBadge type={ticket.type} /></span>
                  </dd>
                </div>
                <div>
                  <dt className="text-slate-500 dark:text-slate-400">{t('detail.totalTime')}</dt>
                  <dd className="text-lg font-semibold">{minutesLabel(ticket.total_minutes)}</dd>
                </div>
                <div className="min-w-0">
                  <dt className="text-slate-500 dark:text-slate-400">{t('fields.requester')}</dt>
                  <dd className="break-words">{requester || '—'}</dd>
                </div>
                <div className="min-w-0">
                  <dt className="text-slate-500 dark:text-slate-400">{t('fields.partner')}</dt>
                  <dd className="break-words">
                    {ticket.partner ? (
                      crmEnabled ? (
                        <Link to={partnerPath(ticket.partner.id)} className="underline">{ticket.partner.name}</Link>
                      ) : (
                        ticket.partner.name
                      )
                    ) : (
                      '—'
                    )}
                  </dd>
                </div>
              </dl>

              <p className="text-sm text-slate-500 dark:text-slate-400">
                {t('detail.origin', { source: t(`source.${ticket.source}`), date: formatDateTime(ticket.created_at, i18n.language) })}
              </p>
            </>
          )}
          {actionError && <p role="alert" className="text-sm text-red-600 dark:text-red-400">{actionError}</p>}
        </div>
      </div>

      <section className="space-y-4" aria-label={t('detail.thread')}>
        {ticket.entries.length === 0 ? (
          <p className="text-slate-500 dark:text-slate-400">{t('detail.noEntries')}</p>
        ) : (
          ticket.entries.map((entry) => <EntryView key={entry.id} ticketNumber={ticket.number} entry={entry} onChanged={load} />)
        )}
      </section>

      <TicketComposer ticket={ticket} onAdded={load} />
    </div>
  )
}

/** /tickets/:number - one ticket: its header (type, time, requester, partner), the thread and the form below it. */
export default function TicketPage() {
  const { number } = useParams<{ number: string }>()
  return (
    <TicketsGate>
      <TicketDetailView key={number} number={Number(number)} />
    </TicketsGate>
  )
}
