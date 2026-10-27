/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useSearchParams } from 'react-router-dom'
import RichTextEditor from '../../components/RichTextEditor'
import usePageMeta from '../../hooks/usePageMeta'
import {
  API_BASE,
  CRM_API_BASE,
  TICKETS_PATH,
  TICKET_TYPES,
  fetchJson,
  sendJson,
  ticketPath,
  type PartnerOption,
  type TicketDetail,
  type TicketType,
} from './api'
import {
  BackLink,
  PartnerPicker,
  TicketsGate,
  cardClass,
  inputClass,
  labelClass,
  primaryButtonClass,
  useCrmEnabled,
  useErrorText,
} from './ui'

function TicketForm() {
  const { t } = useTranslation('tickets')
  const errorText = useErrorText()
  const navigate = useNavigate()
  const crmEnabled = useCrmEnabled()
  const [params] = useSearchParams()
  const [subject, setSubject] = useState('')
  const [type, setType] = useState<TicketType>('general')
  const [requesterName, setRequesterName] = useState('')
  const [requesterEmail, setRequesterEmail] = useState('')
  const [partner, setPartner] = useState<PartnerOption | null>(null)
  const [description, setDescription] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // /tickets/new?partner=<id> (the link on a CRM partner's page) starts with that partner chosen.
  const presetPartnerId = params.get('partner')
  useEffect(() => {
    if (!crmEnabled || !presetPartnerId) return
    fetchJson<PartnerOption>(`${CRM_API_BASE}/partners/${presetPartnerId}`)
      .then((found) => setPartner(found))
      .catch(() => undefined)
  }, [crmEnabled, presetPartnerId])

  function choosePartner(chosen: PartnerOption | null) {
    setPartner(chosen)
    // The partner's own details fill in what was left empty; whatever was typed stays.
    if (chosen) {
      if (!requesterName.trim()) setRequesterName(chosen.name)
      if (!requesterEmail.trim() && chosen.email) setRequesterEmail(chosen.email)
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const created = await sendJson<TicketDetail>(API_BASE, 'POST', {
        subject: subject.trim(),
        type,
        requester_name: requesterName.trim() || null,
        requester_email: requesterEmail.trim() || null,
        partner_id: partner?.id ?? null,
        description_html: description,
      })
      navigate(ticketPath(created.number))
    } catch (e) {
      setError(errorText(e, 'form.saveError'))
      setSaving(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 px-6 py-12 text-slate-900 dark:text-slate-100">
      <div className="space-y-3">
        <BackLink to={TICKETS_PATH}>{t('detail.backToList')}</BackLink>
        <h1 className="text-3xl font-semibold tracking-tight">{t('form.title')}</h1>
      </div>

      <form onSubmit={handleSubmit} className={`${cardClass} space-y-5 p-6`}>
        <div>
          <label htmlFor="ticket-subject" className={labelClass}>{t('fields.subject')}</label>
          <input id="ticket-subject" required maxLength={200} value={subject} onChange={(e) => setSubject(e.target.value)} className={inputClass} />
        </div>

        <div>
          <label htmlFor="ticket-type" className={labelClass}>{t('fields.type')}</label>
          <select id="ticket-type" value={type} onChange={(e) => setType(e.target.value as TicketType)} className={inputClass}>
            {TICKET_TYPES.map((value) => (
              <option key={value} value={value}>{t(`type.${value}`)}</option>
            ))}
          </select>
        </div>

        {crmEnabled && (
          <div>
            <span className={labelClass}>{t('fields.partner')}</span>
            <PartnerPicker value={partner} onChange={choosePartner} />
          </div>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="ticket-requester-name" className={labelClass}>{t('fields.requesterName')}</label>
            <input id="ticket-requester-name" maxLength={200} value={requesterName} onChange={(e) => setRequesterName(e.target.value)} className={inputClass} />
          </div>
          <div>
            <label htmlFor="ticket-requester-email" className={labelClass}>{t('fields.requesterEmail')}</label>
            <input id="ticket-requester-email" type="email" value={requesterEmail} onChange={(e) => setRequesterEmail(e.target.value)} className={inputClass} />
          </div>
        </div>

        <div>
          <span className={labelClass}>{t('form.description')}</span>
          {/* No picture upload here: pictures belong to a ticket, which does not exist yet - add them in a note. */}
          <RichTextEditor value={description} onChange={setDescription} />
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{t('form.descriptionHint')}</p>
        </div>

        {error && <p role="alert" className="text-sm text-red-600 dark:text-red-400">{error}</p>}

        <button type="submit" disabled={saving || !subject.trim()} className={primaryButtonClass}>
          {saving ? t('common.saving') : t('form.create')}
        </button>
      </form>
    </div>
  )
}

/** /tickets/new - a ticket typed in by hand, optionally linked to a CRM partner. */
export default function TicketFormPage() {
  const { t } = useTranslation('tickets')
  usePageMeta({ title: t('form.title') })
  return (
    <TicketsGate>
      <TicketForm />
    </TicketsGate>
  )
}
