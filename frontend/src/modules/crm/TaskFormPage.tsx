/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'
import usePageMeta from '../../hooks/usePageMeta'
import {
  API_BASE,
  TASK_STATUSES,
  errorStatus,
  fetchJson,
  partnerPath,
  sendJson,
  taskPath,
  type Task,
  type TaskDetail,
  type TaskStatus,
} from './api'
import { BackLink, CrmGate, PageMessage, inputClass, labelClass, primaryButtonClass } from './ui'

interface FormState {
  title: string
  description: string
  status: TaskStatus
  price: string
  currency: string
  start_date: string
  due_date: string
}

const EMPTY: FormState = { title: '', description: '', status: 'new', price: '', currency: 'CZK', start_date: '', due_date: '' }

function toForm(task: Task): FormState {
  return {
    title: task.title,
    description: task.description,
    status: task.status,
    price: task.price ?? '',
    currency: task.currency,
    start_date: task.start_date ?? '',
    due_date: task.due_date ?? '',
  }
}

/** Blank optional inputs go to the backend as null, not as an empty string it would reject. */
function toPayload(form: FormState) {
  return {
    ...form,
    price: form.price.trim() === '' ? null : form.price.trim(),
    start_date: form.start_date || null,
    due_date: form.due_date || null,
  }
}

function TaskForm({ partnerId, taskId }: { partnerId: string | undefined; taskId: string | undefined }) {
  const { t } = useTranslation('crm')
  const navigate = useNavigate()
  const [form, setForm] = useState<FormState | null>(taskId ? null : EMPTY)
  // Where "back" goes: the partner when creating, the task when editing.
  const [backTo, setBackTo] = useState(partnerId ? partnerPath(partnerId) : null)
  const [loadError, setLoadError] = useState<'notFound' | 'error' | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  useEffect(() => {
    if (!taskId) return
    let cancelled = false
    fetchJson<TaskDetail>(`${API_BASE}/tasks/${taskId}`)
      .then((task) => {
        if (cancelled) return
        setForm(toForm(task))
        setBackTo(taskPath(task.id))
      })
      .catch((e) => !cancelled && setLoadError(errorStatus(e) === 404 ? 'notFound' : 'error'))
    return () => {
      cancelled = true
    }
  }, [taskId])

  if (loadError) return <PageMessage error>{t(loadError === 'notFound' ? 'task.notFound' : 'task.loadError')}</PageMessage>
  if (form === null || backTo === null) return <PageMessage>{t('common.loading')}</PageMessage>

  function update<K extends keyof FormState>(field: K, value: FormState[K]) {
    setForm((current) => (current ? { ...current, [field]: value } : current))
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setSaving(true)
    setSaveError(null)
    try {
      const saved = taskId
        ? await sendJson<Task>(`${API_BASE}/tasks/${taskId}`, 'PATCH', toPayload(form as FormState))
        : await sendJson<Task>(`${API_BASE}/partners/${partnerId}/tasks`, 'POST', toPayload(form as FormState))
      navigate(taskPath(saved.id))
    } catch (error) {
      setSaveError(t(errorStatus(error) === 422 ? 'task.form.invalid' : 'task.form.saveError'))
      setSaving(false)
    }
  }

  const f = form
  return (
    <form onSubmit={handleSubmit} className="mx-auto max-w-4xl space-y-5 px-6 py-12 text-slate-900 dark:text-slate-100">
      <BackLink to={backTo}>{t('common.back')}</BackLink>
      <h1 className="text-3xl font-semibold tracking-tight">{t(taskId ? 'task.form.editTitle' : 'task.form.newTitle')}</h1>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <label htmlFor="crm-task-title" className={labelClass}>{t('task.fields.title')}</label>
          <input id="crm-task-title" required maxLength={200} value={f.title} onChange={(e) => update('title', e.target.value)} className={inputClass} />
        </div>
        <div className="sm:col-span-2">
          <label htmlFor="crm-task-description" className={labelClass}>{t('task.fields.description')}</label>
          <textarea id="crm-task-description" rows={5} maxLength={10000} value={f.description} onChange={(e) => update('description', e.target.value)} className={inputClass} />
        </div>
        <div>
          <label htmlFor="crm-task-status" className={labelClass}>{t('task.fields.status')}</label>
          <select id="crm-task-status" value={f.status} onChange={(e) => update('status', e.target.value as TaskStatus)} className={inputClass}>
            {TASK_STATUSES.map((status) => (
              <option key={status} value={status}>{t(`status.${status}`)}</option>
            ))}
          </select>
        </div>
        <div className="grid grid-cols-[1fr_6rem] gap-3">
          <div>
            <label htmlFor="crm-task-price" className={labelClass}>{t('task.fields.price')}</label>
            <input id="crm-task-price" type="number" min="0" step="0.01" inputMode="decimal" value={f.price} onChange={(e) => update('price', e.target.value)} className={inputClass} />
          </div>
          <div>
            <label htmlFor="crm-task-currency" className={labelClass}>{t('task.fields.currency')}</label>
            <input
              id="crm-task-currency"
              required
              minLength={3}
              maxLength={3}
              pattern="[A-Za-z]{3}"
              value={f.currency}
              onChange={(e) => update('currency', e.target.value.toUpperCase())}
              className={`${inputClass} font-mono uppercase`}
            />
          </div>
        </div>
        <div>
          <label htmlFor="crm-task-start" className={labelClass}>{t('task.fields.startDate')}</label>
          <input id="crm-task-start" type="date" value={f.start_date} max={f.due_date || undefined} onChange={(e) => update('start_date', e.target.value)} className={inputClass} />
        </div>
        <div>
          <label htmlFor="crm-task-due" className={labelClass}>{t('task.fields.dueDate')}</label>
          <input id="crm-task-due" type="date" value={f.due_date} min={f.start_date || undefined} onChange={(e) => update('due_date', e.target.value)} className={inputClass} />
        </div>
      </div>

      {saveError && <p role="alert" className="text-sm text-red-600 dark:text-red-400">{saveError}</p>}

      <button type="submit" disabled={saving} className={primaryButtonClass}>
        {t(saving ? 'common.saving' : 'common.save')}
      </button>
    </form>
  )
}

/** /crm/partners/:partnerId/tasks/new and /crm/tasks/:taskId/edit. */
export default function TaskFormPage() {
  const { t } = useTranslation('crm')
  const { partnerId, taskId } = useParams<{ partnerId: string; taskId: string }>()
  usePageMeta({ title: t(taskId ? 'task.form.editTitle' : 'task.form.newTitle') })
  return (
    <CrmGate>
      <TaskForm key={taskId ?? partnerId} partnerId={partnerId} taskId={taskId} />
    </CrmGate>
  )
}
