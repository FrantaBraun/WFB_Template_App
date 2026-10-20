/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'
import RichTextEditor from '../../components/RichTextEditor'
import usePageMeta from '../../hooks/usePageMeta'
import ModuleSlot from '../ModuleSlot'
import {
  API_BASE,
  ARTICLES_PATH,
  articlePath,
  fetchJson,
  loadArticleMentionables,
  slugify,
  uploadArticleImage,
  type ArticleAdmin,
  type ArticleStatus,
  type ArticleType,
} from './api'
import { ArticlesGate, inputClass, labelClass, primaryButtonClass, secondaryButtonClass } from './ui'

interface FormState {
  title: string
  slug: string
  perex: string
  content: string
  image_url: string
  type_id: string
  status: ArticleStatus
  display_from: string
  display_to: string
  pinned: boolean
}

const EMPTY: FormState = {
  title: '',
  slug: '',
  perex: '',
  content: '',
  image_url: '',
  type_id: '',
  status: 'draft',
  display_from: '',
  display_to: '',
  pinned: false,
}

function ArticleForm({ articleId }: { articleId: string | undefined }) {
  const { t } = useTranslation('articles')
  const navigate = useNavigate()
  const fileRef = useRef<HTMLInputElement>(null)
  const [form, setForm] = useState<FormState | null>(articleId ? null : EMPTY)
  const [saved, setSaved] = useState<ArticleAdmin | null>(null)
  const [types, setTypes] = useState<ArticleType[]>([])
  // A new article's slug follows its title until the editor types a slug of their own.
  const [slugTouched, setSlugTouched] = useState(Boolean(articleId))
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [message, setMessage] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null)

  useEffect(() => {
    fetchJson<ArticleType[]>(`${API_BASE}/types`)
      .then(setTypes)
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!articleId) return
    fetchJson<ArticleAdmin>(`${API_BASE}/manage/${articleId}`)
      .then((a) => {
        setSaved(a)
        setForm({
          title: a.title,
          slug: a.slug,
          perex: a.perex,
          content: a.content,
          image_url: a.image_url ?? '',
          type_id: a.type_id ?? '',
          status: a.status,
          display_from: a.display_from ?? '',
          display_to: a.display_to ?? '',
          pinned: a.pinned,
        })
      })
      .catch(() => setMessage({ kind: 'error', text: t('form.loadError') }))
  }, [articleId, t])

  if (!form) {
    return <p className="mx-auto max-w-4xl px-6 py-16 text-slate-500 dark:text-slate-400">{message?.text ?? t('common.loading')}</p>
  }

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => {
      if (!current) return current
      const next = { ...current, [key]: value }
      if (key === 'title' && !slugTouched) next.slug = slugify(String(value))
      return next
    })
  }

  async function handleImage(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setUploading(true)
    try {
      update('image_url', await uploadArticleImage(file))
    } catch {
      setMessage({ kind: 'error', text: t('form.uploadError') })
    } finally {
      setUploading(false)
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!form) return
    setSaving(true)
    setMessage(null)
    const payload = {
      ...form,
      image_url: form.image_url || null,
      type_id: form.type_id || null,
      display_from: form.display_from || null,
      display_to: form.display_to || null,
    }
    try {
      const result = await fetchJson<ArticleAdmin>(articleId ? `${API_BASE}/manage/${articleId}` : `${API_BASE}/manage`, {
        method: articleId ? 'PATCH' : 'POST',
        body: JSON.stringify(payload),
      })
      if (!articleId) {
        // Straight to the edit page, where the slots other modules add (e.g. dates) can attach to the saved article.
        navigate(`${ARTICLES_PATH}/manage/${result.id}`, { replace: true })
        return
      }
      setSaved(result)
      setForm((current) => (current ? { ...current, content: result.content } : current))
      setMessage({ kind: 'ok', text: t('form.saved') })
    } catch (err) {
      const status = (err as { status?: number }).status
      setMessage({ kind: 'error', text: status === 409 ? t('form.slugTaken') : status === 422 ? t('form.invalid') : t('form.saveError') })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mx-auto max-w-4xl px-6 py-12 text-slate-900 dark:text-slate-100">
      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-3xl font-semibold tracking-tight">{articleId ? t('form.editTitle') : t('form.newTitle')}</h1>
          <div className="flex gap-2">
            <Link to={`${ARTICLES_PATH}/manage`} className={secondaryButtonClass}>
              {t('form.backToList')}
            </Link>
            {articleId && form.status !== 'draft' && (
              <Link to={articlePath(form.slug)} className={secondaryButtonClass}>
                {t('form.view')}
              </Link>
            )}
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label htmlFor="art-title" className={labelClass}>{t('form.title')}</label>
            <input id="art-title" required maxLength={200} value={form.title} onChange={(e) => update('title', e.target.value)} className={inputClass} />
          </div>
          <div className="sm:col-span-2">
            <label htmlFor="art-slug" className={labelClass}>{t('form.slug')}</label>
            <input
              id="art-slug"
              required
              maxLength={200}
              pattern="[a-z0-9]+(-[a-z0-9]+)*"
              value={form.slug}
              onChange={(e) => {
                setSlugTouched(true)
                update('slug', e.target.value)
              }}
              className={`${inputClass} font-mono text-sm`}
            />
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{t('form.slugHint', { path: articlePath(form.slug || '…') })}</p>
          </div>
          <div className="sm:col-span-2">
            <label htmlFor="art-perex" className={labelClass}>{t('form.perex')}</label>
            <textarea id="art-perex" rows={3} maxLength={500} value={form.perex} onChange={(e) => update('perex', e.target.value)} className={inputClass} />
            <p className="mt-1 text-right text-xs text-slate-500 dark:text-slate-400">{form.perex.length} / 500</p>
          </div>

          <div>
            <label htmlFor="art-type" className={labelClass}>{t('form.type')}</label>
            <select id="art-type" value={form.type_id} onChange={(e) => update('type_id', e.target.value)} className={inputClass}>
              <option value="">{t('form.noType')}</option>
              {types.map((type) => (
                <option key={type.id} value={type.id}>{type.name}</option>
              ))}
            </select>
            <p className="mt-1 text-xs"><Link to={`${ARTICLES_PATH}/manage/types`} className="underline text-slate-500 dark:text-slate-400">{t('form.manageTypes')}</Link></p>
          </div>
          <div>
            <label htmlFor="art-status" className={labelClass}>{t('form.status')}</label>
            <select id="art-status" value={form.status} onChange={(e) => update('status', e.target.value as ArticleStatus)} className={inputClass}>
              {(['draft', 'published', 'archived'] as const).map((status) => (
                <option key={status} value={status}>{t(`status.${status}`)}</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="art-from" className={labelClass}>{t('form.displayFrom')}</label>
            <input id="art-from" type="date" value={form.display_from} onChange={(e) => update('display_from', e.target.value)} className={inputClass} />
          </div>
          <div>
            <label htmlFor="art-to" className={labelClass}>{t('form.displayTo')}</label>
            <input id="art-to" type="date" value={form.display_to} min={form.display_from || undefined} onChange={(e) => update('display_to', e.target.value)} className={inputClass} />
          </div>
          <p className="-mt-2 text-xs text-slate-500 sm:col-span-2 dark:text-slate-400">{t('form.displayHint')}</p>
          <label className="flex items-center gap-2 text-sm sm:col-span-2">
            <input type="checkbox" checked={form.pinned} onChange={(e) => update('pinned', e.target.checked)} />
            {t('form.pinned')}
          </label>
        </div>

        <div>
          <span className={labelClass}>{t('form.image')}</span>
          <div className="flex flex-wrap items-center gap-4">
            <div className="h-28 w-40 overflow-hidden rounded-xl bg-slate-100 dark:bg-slate-800">
              {form.image_url && <img src={form.image_url} alt="" className="h-full w-full object-cover" />}
            </div>
            <div className="flex gap-2 text-sm">
              <button type="button" onClick={() => fileRef.current?.click()} disabled={uploading} className={secondaryButtonClass}>
                {uploading ? t('common.loading') : form.image_url ? t('form.imageReplace') : t('form.imageUpload')}
              </button>
              {form.image_url && (
                <button type="button" onClick={() => update('image_url', '')} className="rounded-lg px-3 py-1.5 text-red-600 dark:text-red-400">
                  {t('form.imageRemove')}
                </button>
              )}
            </div>
            <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp,image/gif" className="hidden" onChange={handleImage} />
          </div>
        </div>

        <div>
          <span className={labelClass}>{t('form.content')}</span>
          <RichTextEditor value={form.content} onChange={(html) => update('content', html)} uploadImage={uploadArticleImage} loadMentionables={loadArticleMentionables} />
        </div>

        {message && (
          <p role="status" className={`text-sm ${message.kind === 'ok' ? 'text-emerald-700 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'}`}>
            {message.text}
          </p>
        )}
        <button type="submit" disabled={saving} className={`${primaryButtonClass} px-5 py-2`}>
          {saving ? t('form.saving') : t('form.save')}
        </button>
      </form>

      {/* Other modules add their panels here (the dates of this article, ...). Only once it is saved: they need its id. */}
      {saved && <ModuleSlot name="article.editor" context={{ article: saved }} />}
    </div>
  )
}

/** /articles/manage/new and /articles/manage/:id. */
export default function ArticleFormPage() {
  const { t } = useTranslation('articles')
  const { id } = useParams<{ id: string }>()
  usePageMeta({ title: id ? t('form.editTitle') : t('form.newTitle') })
  return (
    <ArticlesGate>
      <ArticleForm key={id ?? 'new'} articleId={id} />
    </ArticlesGate>
  )
}
