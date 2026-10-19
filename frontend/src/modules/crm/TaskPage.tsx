/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'
import usePageMeta from '../../hooks/usePageMeta'
import { API_BASE, deleteRequest, errorStatus, fetchJson, formatDate, formatPrice, partnerPath, taskPath, type TaskDetail } from './api'
import InvoiceList from './InvoiceList'
import { BackLink, CrmGate, PageMessage, StatusBadge, cardClass, dangerButtonClass, secondaryButtonClass } from './ui'

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-sm text-slate-500 dark:text-slate-400">{label}</dt>
      <dd className="whitespace-pre-line break-words">{children}</dd>
    </div>
  )
}

function TaskDetailView({ taskId }: { taskId: string }) {
  const { t, i18n } = useTranslation('crm')
  const navigate = useNavigate()
  const [task, setTask] = useState<TaskDetail | null>(null)
  const [loadError, setLoadError] = useState<'notFound' | 'error' | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setTask(await fetchJson<TaskDetail>(`${API_BASE}/tasks/${taskId}`))
    } catch (e) {
      setLoadError(errorStatus(e) === 404 ? 'notFound' : 'error')
    }
  }, [taskId])

  useEffect(() => {
    load()
  }, [load])

  if (loadError) return <PageMessage error>{t(loadError === 'notFound' ? 'task.notFound' : 'task.loadError')}</PageMessage>
  if (!task) return <PageMessage>{t('common.loading')}</PageMessage>

  async function handleDelete() {
    if (!task || !window.confirm(t('task.confirmDelete'))) return
    setActionError(null)
    try {
      await deleteRequest(`${API_BASE}/tasks/${taskId}`)
      navigate(partnerPath(task.partner.id))
    } catch (e) {
      setActionError(t(errorStatus(e) === 409 ? 'task.deleteBlocked' : 'task.actionError'))
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-8 px-6 py-12 text-slate-900 dark:text-slate-100">
      <div className="space-y-3">
        <BackLink to={partnerPath(task.partner.id)}>{task.partner.name}</BackLink>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h1 className="break-words text-3xl font-semibold tracking-tight">{task.title}</h1>
            <div className="mt-2 flex flex-wrap items-center gap-3 text-slate-500 dark:text-slate-400">
              <StatusBadge status={task.status} />
              <Link to={partnerPath(task.partner.id)} className="hover:underline">
                {[task.partner.name, task.partner.company].filter(Boolean).join(' · ')}
              </Link>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link to={`${taskPath(task.id)}/edit`} className={secondaryButtonClass}>{t('common.edit')}</Link>
            <button type="button" onClick={handleDelete} className={dangerButtonClass}>{t('common.delete')}</button>
          </div>
        </div>
        {actionError && <p role="alert" className="text-sm text-red-600 dark:text-red-400">{actionError}</p>}
      </div>

      <dl className={`${cardClass} grid gap-4 p-5 sm:grid-cols-3`}>
        <Field label={t('task.fields.price')}>{formatPrice(task.price, task.currency, i18n.language)}</Field>
        <Field label={t('task.fields.startDate')}>{formatDate(task.start_date, i18n.language)}</Field>
        <Field label={t('task.fields.dueDate')}>{formatDate(task.due_date, i18n.language)}</Field>
        <div className="sm:col-span-3">
          <Field label={t('task.fields.description')}>{task.description || '—'}</Field>
        </div>
      </dl>

      <InvoiceList taskId={task.id} invoices={task.invoices} onChange={load} />
    </div>
  )
}

/** /crm/tasks/:taskId - one task, with its invoices. */
export default function TaskPage() {
  const { t } = useTranslation('crm')
  const { taskId } = useParams<{ taskId: string }>()
  usePageMeta({ title: t('tasks.title') })
  return (
    <CrmGate>
      <TaskDetailView key={taskId} taskId={taskId ?? ''} />
    </CrmGate>
  )
}
