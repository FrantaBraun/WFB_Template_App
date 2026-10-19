/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'
import usePageMeta from '../../hooks/usePageMeta'
import { API_BASE, CRM_PATH, errorStatus, fetchJson, partnerPath, sendJson, type Partner } from './api'
import { BackLink, CrmGate, PageMessage, inputClass, labelClass, primaryButtonClass } from './ui'

interface FormState {
  name: string
  company: string
  company_id: string
  vat_id: string
  email: string
  phone: string
  address: string
  notes: string
}

const EMPTY: FormState = { name: '', company: '', company_id: '', vat_id: '', email: '', phone: '', address: '', notes: '' }

function toForm(partner: Partner): FormState {
  return {
    name: partner.name,
    company: partner.company ?? '',
    company_id: partner.company_id ?? '',
    vat_id: partner.vat_id ?? '',
    email: partner.email ?? '',
    phone: partner.phone ?? '',
    address: partner.address,
    notes: partner.notes,
  }
}

function PartnerForm({ partnerId }: { partnerId: string | undefined }) {
  const { t } = useTranslation('crm')
  const navigate = useNavigate()
  const [form, setForm] = useState<FormState | null>(partnerId ? null : EMPTY)
  const [loadError, setLoadError] = useState<'notFound' | 'error' | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  useEffect(() => {
    if (!partnerId) return
    let cancelled = false
    fetchJson<Partner>(`${API_BASE}/partners/${partnerId}`)
      .then((partner) => !cancelled && setForm(toForm(partner)))
      .catch((e) => !cancelled && setLoadError(errorStatus(e) === 404 ? 'notFound' : 'error'))
    return () => {
      cancelled = true
    }
  }, [partnerId])

  if (loadError) return <PageMessage error>{t(loadError === 'notFound' ? 'partner.notFound' : 'partner.loadError')}</PageMessage>
  if (form === null) return <PageMessage>{t('common.loading')}</PageMessage>

  function update(field: keyof FormState, value: string) {
    setForm((current) => (current ? { ...current, [field]: value } : current))
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setSaving(true)
    setSaveError(null)
    try {
      const saved = partnerId
        ? await sendJson<Partner>(`${API_BASE}/partners/${partnerId}`, 'PATCH', form)
        : await sendJson<Partner>(`${API_BASE}/partners`, 'POST', form)
      navigate(partnerPath(saved.id))
    } catch (error) {
      setSaveError(t(errorStatus(error) === 422 ? 'partner.form.invalid' : 'partner.form.saveError'))
      setSaving(false)
    }
  }

  const f = form
  return (
    <form onSubmit={handleSubmit} className="mx-auto max-w-4xl space-y-5 px-6 py-12 text-slate-900 dark:text-slate-100">
      <BackLink to={partnerId ? partnerPath(partnerId) : CRM_PATH}>{t(partnerId ? 'common.back' : 'partner.backToList')}</BackLink>
      <h1 className="text-3xl font-semibold tracking-tight">{t(partnerId ? 'partner.form.editTitle' : 'partner.form.newTitle')}</h1>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="crm-name" className={labelClass}>{t('partner.fields.name')}</label>
          <input id="crm-name" required maxLength={200} value={f.name} onChange={(e) => update('name', e.target.value)} className={inputClass} />
        </div>
        <div>
          <label htmlFor="crm-company" className={labelClass}>{t('partner.fields.company')}</label>
          <input id="crm-company" maxLength={200} value={f.company} onChange={(e) => update('company', e.target.value)} className={inputClass} />
        </div>
        <div>
          <label htmlFor="crm-company-id" className={labelClass}>{t('partner.fields.companyId')}</label>
          <input id="crm-company-id" maxLength={30} value={f.company_id} onChange={(e) => update('company_id', e.target.value)} className={inputClass} />
        </div>
        <div>
          <label htmlFor="crm-vat-id" className={labelClass}>{t('partner.fields.vatId')}</label>
          <input id="crm-vat-id" maxLength={30} value={f.vat_id} onChange={(e) => update('vat_id', e.target.value)} className={inputClass} />
        </div>
        <div>
          <label htmlFor="crm-email" className={labelClass}>{t('partner.fields.email')}</label>
          <input id="crm-email" type="email" maxLength={254} value={f.email} onChange={(e) => update('email', e.target.value)} className={inputClass} />
        </div>
        <div>
          <label htmlFor="crm-phone" className={labelClass}>{t('partner.fields.phone')}</label>
          <input id="crm-phone" type="tel" maxLength={50} value={f.phone} onChange={(e) => update('phone', e.target.value)} className={inputClass} />
        </div>
        <div className="sm:col-span-2">
          <label htmlFor="crm-address" className={labelClass}>{t('partner.fields.address')}</label>
          <textarea id="crm-address" rows={3} maxLength={1000} value={f.address} onChange={(e) => update('address', e.target.value)} className={inputClass} />
        </div>
        <div className="sm:col-span-2">
          <label htmlFor="crm-notes" className={labelClass}>{t('partner.fields.notes')}</label>
          <textarea id="crm-notes" rows={5} maxLength={10000} value={f.notes} onChange={(e) => update('notes', e.target.value)} className={inputClass} />
        </div>
      </div>

      {saveError && <p role="alert" className="text-sm text-red-600 dark:text-red-400">{saveError}</p>}

      <button type="submit" disabled={saving} className={primaryButtonClass}>
        {t(saving ? 'common.saving' : 'common.save')}
      </button>
    </form>
  )
}

/** /crm/partners/new and /crm/partners/:partnerId/edit. */
export default function PartnerFormPage() {
  const { t } = useTranslation('crm')
  const { partnerId } = useParams<{ partnerId: string }>()
  usePageMeta({ title: t(partnerId ? 'partner.form.editTitle' : 'partner.form.newTitle'), noindex: true })
  return (
    <CrmGate>
      <PartnerForm key={partnerId ?? 'new'} partnerId={partnerId} />
    </CrmGate>
  )
}
