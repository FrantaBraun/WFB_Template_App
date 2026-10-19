/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'
import usePageMeta from '../../hooks/usePageMeta'
import {
  API_BASE,
  ApiError,
  ITEM_STATUSES,
  LIMITS,
  MANAGE_PATH,
  PORTFOLIO_PATH,
  errorStatus,
  fetchJson,
  fieldProblems,
  sendJson,
  type AdminItem,
  type ItemInput,
  type ItemStatus,
} from './api'
import {
  AdminGate,
  BackLink,
  PageMessage,
  cardClass,
  container,
  errorTextClass,
  hintClass,
  inputClass,
  labelClass,
  mutedText,
  primaryButtonClass,
  secondaryButtonClass,
} from './ui'

interface FormState {
  slug: string
  title_cs: string
  summary_cs: string
  description_cs: string
  title_en: string
  summary_en: string
  description_en: string
  url: string
  status: ItemStatus
  tags: string
  published: boolean
}

type TextField = Exclude<keyof FormState, 'status' | 'published'>

const EMPTY: FormState = {
  slug: '',
  title_cs: '',
  summary_cs: '',
  description_cs: '',
  title_en: '',
  summary_en: '',
  description_en: '',
  url: '',
  status: 'live',
  tags: '',
  published: true,
}

/** Where focus goes after a refused save: the first of these that has a problem, in page order. */
const FIELD_ORDER = ['title_cs', 'summary_cs', 'description_cs', 'title_en', 'summary_en', 'description_en', 'slug', 'url', 'status', 'tags']

const fieldId = (field: string) => `portfolio-${field}`

function toForm(item: AdminItem): FormState {
  return {
    slug: item.slug,
    title_cs: item.title_cs,
    summary_cs: item.summary_cs,
    description_cs: item.description_cs,
    title_en: item.title_en,
    summary_en: item.summary_en,
    description_en: item.description_en,
    url: item.url ?? '',
    status: item.status,
    tags: item.tags.join(', '),
    published: item.published,
  }
}

/** What is sent: tags split on commas, an empty URL as null, an empty slug left out when creating (the server makes one). */
function toInput(form: FormState, creating: boolean): ItemInput {
  const input: ItemInput = {
    title_cs: form.title_cs,
    summary_cs: form.summary_cs,
    description_cs: form.description_cs,
    title_en: form.title_en,
    summary_en: form.summary_en,
    description_en: form.description_en,
    url: form.url.trim() === '' ? null : form.url.trim(),
    status: form.status,
    tags: form.tags.split(',').map((tag) => tag.trim()).filter(Boolean),
    published: form.published,
  }
  if (!creating || form.slug.trim() !== '') input.slug = form.slug.trim()
  return input
}

interface TextFieldProps {
  field: TextField
  label: string
  value: string
  onChange: (field: TextField, value: string) => void
  error?: string
  hint?: string
  required?: boolean
  maxLength: number
  rows?: number
  type?: 'text' | 'url'
  counter?: boolean
}

/** A labelled input or textarea with its hint, character counter and error wired up for screen readers. */
function TextFieldControl({ field, label, value, onChange, error, hint, required, maxLength, rows, type = 'text', counter }: TextFieldProps) {
  const { t } = useTranslation('portfolio')
  const id = fieldId(field)
  const describedBy = [hint && `${id}-hint`, error && `${id}-error`].filter(Boolean).join(' ') || undefined
  const common = {
    id,
    value,
    required,
    maxLength,
    'aria-invalid': error ? true : undefined,
    'aria-describedby': describedBy,
    onChange: (e: { target: { value: string } }) => onChange(field, e.target.value),
    className: inputClass,
  }
  return (
    <div>
      <label htmlFor={id} className={labelClass}>
        {label}
        {required && <span aria-hidden="true" className="text-red-700 dark:text-red-400"> *</span>}
      </label>
      {rows ? <textarea rows={rows} {...common} /> : <input type={type} {...(type === 'url' ? { inputMode: 'url' as const } : {})} {...common} />}
      {(hint || counter) && (
        <p id={hint ? `${id}-hint` : undefined} className={`${hintClass} flex flex-wrap justify-between gap-x-4`}>
          <span>{hint}</span>
          {counter && <span>{t('form.count', { current: value.length, max: maxLength })}</span>}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className={errorTextClass}>
          {error}
        </p>
      )}
    </div>
  )
}

function ItemForm({ itemId }: { itemId: string | undefined }) {
  const { t } = useTranslation('portfolio')
  const navigate = useNavigate()
  const creating = itemId === undefined
  const [form, setForm] = useState<FormState | null>(creating ? EMPTY : null)
  const [loadError, setLoadError] = useState<'notFound' | 'error' | null>(null)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  useEffect(() => {
    if (!itemId) return
    let cancelled = false
    fetchJson<AdminItem>(`${API_BASE}/manage/items/${itemId}`)
      .then((item) => !cancelled && setForm(toForm(item)))
      .catch((error) => !cancelled && setLoadError(errorStatus(error) === 404 ? 'notFound' : 'error'))
    return () => {
      cancelled = true
    }
  }, [itemId])

  if (loadError) {
    return (
      <PageMessage error={loadError === 'error'}>
        {t(loadError === 'notFound' ? 'form.notFound' : 'form.loadError')}{' '}
        <Link to={MANAGE_PATH} className="underline">
          {t('form.backToList')}
        </Link>
      </PageMessage>
    )
  }
  if (form === null) return <PageMessage>{t('common.loading')}</PageMessage>

  function setText(field: TextField, value: string) {
    setForm((current) => (current ? { ...current, [field]: value } : current))
    setFieldErrors((current) => {
      if (!current[field]) return current
      const { [field]: _fixed, ...rest } = current
      return rest
    })
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!form) return
    setSaving(true)
    setFormError(null)
    setFieldErrors({})
    try {
      const input = toInput(form, creating)
      if (creating) await sendJson<AdminItem>(`${API_BASE}/manage/items`, 'POST', input)
      else await sendJson<AdminItem>(`${API_BASE}/manage/items/${itemId}`, 'PATCH', input)
      navigate(MANAGE_PATH)
    } catch (error) {
      const status = errorStatus(error)
      const errors: Record<string, string> = {}
      if (status === 409) {
        errors.slug = t('form.errors.slugTaken')
      } else if (status === 422) {
        for (const [field, problem] of Object.entries(fieldProblems(error instanceof ApiError ? error.body : null))) {
          errors[field] = t(problem.key, problem.values)
        }
      }
      setFieldErrors(errors)
      setFormError(t(Object.keys(errors).length > 0 ? 'form.errors.summary' : 'form.errors.saveError'))
      setSaving(false)
      // Put the cursor on the first field with a problem (the controls are still mounted and enabled).
      const first = FIELD_ORDER.find((field) => errors[field])
      if (first) document.getElementById(fieldId(first))?.focus()
    }
  }

  const f = form
  const slugHint = t(creating ? 'form.hints.slugCreate' : 'form.hints.slugEdit', { path: `${PORTFOLIO_PATH}/` })
  return (
    <form onSubmit={handleSubmit} className={`${container} space-y-6 py-12 text-slate-900 dark:text-slate-100`}>
      <BackLink to={MANAGE_PATH}>{t('form.backToList')}</BackLink>
      <h1 className="text-3xl font-semibold tracking-tight">{t(creating ? 'form.newTitle' : 'form.editTitle')}</h1>
      <p className={`text-sm ${mutedText}`}>{t('form.requiredNote')}</p>

      <fieldset className={`${cardClass} min-w-0 space-y-4 p-5`}>
        <legend className="px-1 text-lg font-semibold tracking-tight">{t('form.czech')}</legend>
        <TextFieldControl field="title_cs" label={t('form.fields.title')} value={f.title_cs} onChange={setText} error={fieldErrors.title_cs} required maxLength={LIMITS.title} />
        <TextFieldControl
          field="summary_cs"
          label={t('form.fields.summary')}
          value={f.summary_cs}
          onChange={setText}
          error={fieldErrors.summary_cs}
          hint={t('form.hints.summary')}
          required
          maxLength={LIMITS.summary}
          rows={3}
          counter
        />
        <TextFieldControl
          field="description_cs"
          label={t('form.fields.description')}
          value={f.description_cs}
          onChange={setText}
          error={fieldErrors.description_cs}
          hint={t('form.hints.description')}
          maxLength={LIMITS.description}
          rows={8}
          counter
        />
      </fieldset>

      <fieldset className={`${cardClass} min-w-0 space-y-4 p-5`}>
        <legend className="px-1 text-lg font-semibold tracking-tight">{t('form.english')}</legend>
        <p className={`text-sm ${mutedText}`}>{t('form.englishHint')}</p>
        <TextFieldControl field="title_en" label={t('form.fields.title')} value={f.title_en} onChange={setText} error={fieldErrors.title_en} maxLength={LIMITS.title} />
        <TextFieldControl
          field="summary_en"
          label={t('form.fields.summary')}
          value={f.summary_en}
          onChange={setText}
          error={fieldErrors.summary_en}
          hint={t('form.hints.summary')}
          maxLength={LIMITS.summary}
          rows={3}
          counter
        />
        <TextFieldControl
          field="description_en"
          label={t('form.fields.description')}
          value={f.description_en}
          onChange={setText}
          error={fieldErrors.description_en}
          hint={t('form.hints.description')}
          maxLength={LIMITS.description}
          rows={8}
          counter
        />
      </fieldset>

      <fieldset className={`${cardClass} min-w-0 space-y-4 p-5`}>
        <legend className="px-1 text-lg font-semibold tracking-tight">{t('form.general')}</legend>
        <TextFieldControl
          field="slug"
          label={t('form.fields.slug')}
          value={f.slug}
          onChange={setText}
          error={fieldErrors.slug}
          hint={slugHint}
          required={!creating}
          maxLength={LIMITS.slug}
        />
        <TextFieldControl
          field="url"
          label={t('form.fields.url')}
          value={f.url}
          onChange={setText}
          error={fieldErrors.url}
          hint={t('form.hints.url')}
          maxLength={LIMITS.url}
          type="url"
        />
        <div>
          <label htmlFor={fieldId('status')} className={labelClass}>
            {t('form.fields.status')}
          </label>
          <select
            id={fieldId('status')}
            value={f.status}
            onChange={(e) => setForm({ ...f, status: e.target.value as ItemStatus })}
            aria-invalid={fieldErrors.status ? true : undefined}
            aria-describedby={fieldErrors.status ? `${fieldId('status')}-error` : undefined}
            className={inputClass}
          >
            {ITEM_STATUSES.map((status) => (
              <option key={status} value={status}>
                {t(`status.${status}`)}
              </option>
            ))}
          </select>
          {fieldErrors.status && (
            <p id={`${fieldId('status')}-error`} className={errorTextClass}>
              {fieldErrors.status}
            </p>
          )}
        </div>
        <TextFieldControl
          field="tags"
          label={t('form.fields.tags')}
          value={f.tags}
          onChange={setText}
          error={fieldErrors.tags}
          hint={t('form.hints.tags', { max: LIMITS.tags })}
          maxLength={LIMITS.tags * (LIMITS.tag + 2)}
        />
        <label className="flex items-start gap-3">
          <input
            type="checkbox"
            checked={f.published}
            onChange={(e) => setForm({ ...f, published: e.target.checked })}
            className="mt-1"
          />
          <span>
            <span className="block text-sm font-medium text-slate-700 dark:text-slate-300">{t('form.fields.published')}</span>
            <span className={hintClass}>{t('form.hints.published')}</span>
          </span>
        </label>
      </fieldset>

      {formError && (
        <p role="alert" className="text-sm font-medium text-red-700 dark:text-red-400">
          {formError}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" disabled={saving} className={primaryButtonClass}>
          {t(saving ? 'form.saving' : 'form.save')}
        </button>
        <Link to={MANAGE_PATH} className={secondaryButtonClass}>
          {t('form.cancel')}
        </Link>
      </div>
    </form>
  )
}

/** /portfolio/manage/new and /portfolio/manage/:id. */
export default function ItemFormPage() {
  const { t } = useTranslation('portfolio')
  const { id } = useParams<{ id: string }>()
  usePageMeta({ title: t(id ? 'form.editTitle' : 'form.newTitle'), noindex: true })
  return (
    <AdminGate>
      <ItemForm key={id ?? 'new'} itemId={id} />
    </AdminGate>
  )
}
