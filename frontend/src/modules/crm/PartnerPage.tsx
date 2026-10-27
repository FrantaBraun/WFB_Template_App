/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'
import usePageMeta from '../../hooks/usePageMeta'
import ModuleSlot from '../ModuleSlot'
import {
  API_BASE,
  CRM_PATH,
  deleteRequest,
  errorStatus,
  fetchJson,
  formatDate,
  formatPrice,
  partnerPath,
  sendJson,
  taskPath,
  type Partner,
  type TaskListItem,
} from './api'
import { BackLink, CrmGate, PageMessage, StatusBadge, cardClass, dangerButtonClass, secondaryButtonClass } from './ui'

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-sm text-slate-500 dark:text-slate-400">{label}</dt>
      <dd className="whitespace-pre-line break-words">{children}</dd>
    </div>
  )
}

function PartnerDetail({ partnerId }: { partnerId: string }) {
  const { t, i18n } = useTranslation('crm')
  const navigate = useNavigate()
  const [partner, setPartner] = useState<Partner | null>(null)
  const [tasks, setTasks] = useState<TaskListItem[] | null>(null)
  const [loadError, setLoadError] = useState<'notFound' | 'error' | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const [loadedPartner, loadedTasks] = await Promise.all([
        fetchJson<Partner>(`${API_BASE}/partners/${partnerId}`),
        fetchJson<TaskListItem[]>(`${API_BASE}/partners/${partnerId}/tasks`),
      ])
      setPartner(loadedPartner)
      setTasks(loadedTasks)
    } catch (e) {
      setLoadError(errorStatus(e) === 404 ? 'notFound' : 'error')
    }
  }, [partnerId])

  useEffect(() => {
    load()
  }, [load])

  if (loadError) return <PageMessage error>{t(loadError === 'notFound' ? 'partner.notFound' : 'partner.loadError')}</PageMessage>
  if (!partner || !tasks) return <PageMessage>{t('common.loading')}</PageMessage>

  async function toggleArchived() {
    if (!partner) return
    setActionError(null)
    try {
      setPartner(await sendJson<Partner>(`${API_BASE}/partners/${partnerId}`, 'PATCH', { archived: !partner.archived }))
    } catch {
      setActionError(t('partner.actionError'))
    }
  }

  async function handleDelete() {
    if (!window.confirm(t('partner.confirmDelete'))) return
    setActionError(null)
    try {
      await deleteRequest(`${API_BASE}/partners/${partnerId}`)
      navigate(CRM_PATH)
    } catch (e) {
      setActionError(t(errorStatus(e) === 409 ? 'partner.deleteBlocked' : 'partner.actionError'))
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-8 px-6 py-12 text-slate-900 dark:text-slate-100">
      <div className="space-y-3">
        <BackLink to={CRM_PATH}>{t('partner.backToList')}</BackLink>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h1 className="break-words text-3xl font-semibold tracking-tight">
              {partner.name}
              {partner.archived && (
                <span className="ms-3 align-middle rounded-full bg-slate-200 px-2 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                  {t('partners.archived')}
                </span>
              )}
            </h1>
            {partner.company && <p className="text-slate-500 dark:text-slate-400">{partner.company}</p>}
          </div>
          <div className="flex flex-wrap gap-2">
            <Link to={`${partnerPath(partner.id)}/edit`} className={secondaryButtonClass}>{t('common.edit')}</Link>
            <button type="button" onClick={toggleArchived} className={secondaryButtonClass}>
              {t(partner.archived ? 'partner.restore' : 'partner.archive')}
            </button>
            <button type="button" onClick={handleDelete} className={dangerButtonClass}>{t('common.delete')}</button>
          </div>
        </div>
        {actionError && <p role="alert" className="text-sm text-red-600 dark:text-red-400">{actionError}</p>}
      </div>

      <dl className={`${cardClass} grid gap-4 p-5 sm:grid-cols-2`}>
        <Field label={t('partner.fields.companyId')}>{partner.company_id ?? '—'}</Field>
        <Field label={t('partner.fields.vatId')}>{partner.vat_id ?? '—'}</Field>
        <Field label={t('partner.fields.email')}>
          {partner.email ? <a href={`mailto:${partner.email}`} className="underline">{partner.email}</a> : '—'}
        </Field>
        <Field label={t('partner.fields.phone')}>
          {partner.phone ? <a href={`tel:${partner.phone}`} className="underline">{partner.phone}</a> : '—'}
        </Field>
        <Field label={t('partner.fields.address')}>{partner.address || '—'}</Field>
        <Field label={t('partner.fields.notes')}>{partner.notes || '—'}</Field>
      </dl>

      <section>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-xl font-semibold tracking-tight">{t('tasks.title')}</h2>
          <Link to={`${partnerPath(partner.id)}/tasks/new`} className={secondaryButtonClass}>{t('tasks.new')}</Link>
        </div>
        {tasks.length === 0 ? (
          <p className="text-slate-500 dark:text-slate-400">{t('tasks.empty')}</p>
        ) : (
          <ul className={`${cardClass} divide-y divide-slate-200 overflow-hidden dark:divide-slate-800`}>
            {tasks.map((task) => (
              <li key={task.id}>
                <Link to={taskPath(task.id)} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-800/60">
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{task.title}</span>
                    <span className="block text-sm text-slate-500 dark:text-slate-400">
                      {[
                        task.due_date ? t('tasks.dueOn', { date: formatDate(task.due_date, i18n.language) }) : null,
                        t('tasks.invoiceCount', { count: task.invoice_count }),
                      ].filter(Boolean).join(' · ')}
                    </span>
                  </span>
                  <span className="text-sm text-slate-600 dark:text-slate-300">{formatPrice(task.price, task.currency, i18n.language)}</span>
                  <StatusBadge status={task.status} />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Slot "crm.partner", context { partner }: other modules add their own section about this partner (the tickets module lists its tickets). */}
      <ModuleSlot name="crm.partner" context={{ partner }} />
    </div>
  )
}

/** /crm/partners/:partnerId - one partner's details and tasks. */
export default function PartnerPage() {
  const { t } = useTranslation('crm')
  const { partnerId } = useParams<{ partnerId: string }>()
  usePageMeta({ title: t('partners.title'), noindex: true })
  return (
    <CrmGate>
      <PartnerDetail key={partnerId} partnerId={partnerId ?? ''} />
    </CrmGate>
  )
}
