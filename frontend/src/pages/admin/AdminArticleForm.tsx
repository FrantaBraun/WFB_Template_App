/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { apiFetch } from '../../api/client'
import RichTextEditor from '../../components/RichTextEditor'
import { loadAdminMentionables, uploadAdminImage } from './editorSources'
import usePageMeta from '../../hooks/usePageMeta'
import useRequireAdmin from '../../hooks/useRequireAdmin'

interface ArticleData {
  id: string
  title: string
  slug: string
  short_description: string
  full_text: string
  event_date: string
  display_from: string | null
  display_to: string | null
  pinned: boolean
  status: 'draft' | 'published' | 'deleted'
}

type Message = { type: 'success' | 'error'; text: string } | null

/** Same shared create/edit pattern as AdminPageForm - useParams().id present
 * or not decides POST vs. PATCH. */
export default function AdminArticleForm() {
  const { t } = useTranslation()
  usePageMeta({ title: t('admin.articles.title'), description: t('admin.pageDescription') })
  const { user, loading: authLoading } = useRequireAdmin()
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const isEditing = Boolean(id)

  const [title, setTitle] = useState('')
  const [slug, setSlug] = useState('')
  const [shortDescription, setShortDescription] = useState('')
  const [fullText, setFullText] = useState('')
  const [eventDate, setEventDate] = useState('')
  const [displayFrom, setDisplayFrom] = useState('')
  const [displayTo, setDisplayTo] = useState('')
  const [pinned, setPinned] = useState(false)
  const [status, setStatus] = useState<'draft' | 'published' | 'deleted'>('draft')
  const [loaded, setLoaded] = useState(!isEditing)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<Message>(null)

  useEffect(() => {
    if (!user?.is_admin || !id) return
    apiFetch(`/api/admin/articles/${id}`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data: ArticleData) => {
        setTitle(data.title)
        setSlug(data.slug)
        setShortDescription(data.short_description)
        setFullText(data.full_text)
        setEventDate(data.event_date)
        setDisplayFrom(data.display_from ?? '')
        setDisplayTo(data.display_to ?? '')
        setPinned(data.pinned)
        setStatus(data.status)
        setLoaded(true)
      })
      .catch(() => setMessage({ type: 'error', text: t('admin.articles.loadError') }))
  }, [user, id, t])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setSaving(true)
    setMessage(null)
    const body = {
      title,
      slug,
      short_description: shortDescription,
      full_text: fullText,
      event_date: eventDate,
      // Controlled date inputs can't hold null, so an untouched/cleared
      // bound is '' here - convert back to null (open-ended) before sending,
      // same convention as Account.tsx's blankToNull for birth_date.
      display_from: displayFrom || null,
      display_to: displayTo || null,
      pinned,
      status,
    }
    try {
      const resp = await apiFetch(isEditing ? `/api/admin/articles/${id}` : '/api/admin/articles/', {
        method: isEditing ? 'PATCH' : 'POST',
        body: JSON.stringify(body),
      })
      if (!resp.ok) throw new Error()
      const saved: ArticleData = await resp.json()
      setMessage({ type: 'success', text: t('admin.articles.saveSuccess') })
      if (!isEditing) navigate(`/admin/articles/${saved.id}/edit`, { replace: true })
    } catch {
      setMessage({ type: 'error', text: t('admin.articles.saveError') })
    } finally {
      setSaving(false)
    }
  }

  if (authLoading || !user?.is_admin || !loaded) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-900 dark:text-slate-100">
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('common.loading')}</p>
      </div>
    )
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 px-6 py-16 text-slate-900 dark:text-slate-100">
      <h1 className="text-2xl font-semibold tracking-tight">{isEditing ? title : t('admin.articles.new')}</h1>

      <form
        onSubmit={handleSubmit}
        className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900"
      >
        <div>
          <label htmlFor="title" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
            {t('admin.articles.titleLabel')}
          </label>
          <input
            id="title"
            type="text"
            required
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
          />
        </div>

        <div>
          <label htmlFor="slug" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
            {t('admin.articles.slugLabel')}
          </label>
          <input
            id="slug"
            type="text"
            required
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
          />
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{t('admin.articles.slugHint')}</p>
        </div>

        <div>
          <label htmlFor="short_description" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
            {t('admin.articles.shortDescriptionLabel')}
          </label>
          <textarea
            id="short_description"
            rows={2}
            value={shortDescription}
            onChange={(e) => setShortDescription(e.target.value)}
            className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
            {t('admin.articles.fullTextLabel')}
          </label>
          <RichTextEditor value={fullText} onChange={setFullText} loadMentionables={loadAdminMentionables} uploadImage={uploadAdminImage} />
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <label htmlFor="event_date" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
              {t('admin.articles.eventDateLabel')}
            </label>
            <input
              id="event_date"
              type="date"
              required
              value={eventDate}
              onChange={(e) => setEventDate(e.target.value)}
              className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
            />
          </div>
          <div>
            <label htmlFor="display_from" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
              {t('admin.articles.displayFromLabel')}
            </label>
            <input
              id="display_from"
              type="date"
              value={displayFrom}
              onChange={(e) => setDisplayFrom(e.target.value)}
              className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
            />
          </div>
          <div>
            <label htmlFor="display_to" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
              {t('admin.articles.displayToLabel')}
            </label>
            <input
              id="display_to"
              type="date"
              value={displayTo}
              onChange={(e) => setDisplayTo(e.target.value)}
              className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
            />
          </div>
        </div>

        <div className="flex items-center gap-6">
          <div>
            <label htmlFor="status" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
              {t('admin.articles.statusLabel')}
            </label>
            <select
              id="status"
              value={status}
              onChange={(e) => setStatus(e.target.value as 'draft' | 'published' | 'deleted')}
              className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
            >
              <option value="draft">{t('admin.status.draft')}</option>
              <option value="published">{t('admin.status.published')}</option>
              <option value="deleted">{t('admin.status.deleted')}</option>
            </select>
          </div>

          <label className="mt-5 flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
            <input
              type="checkbox"
              checked={pinned}
              onChange={(e) => setPinned(e.target.checked)}
              className="h-4 w-4 rounded border-slate-300"
            />
            {t('admin.articles.pinnedLabel')}
          </label>
        </div>

        {message && (
          <p
            className={`text-sm ${
              message.type === 'success' ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'
            }`}
          >
            {message.text}
          </p>
        )}

        <button
          type="submit"
          disabled={saving}
          className="rounded-lg bg-slate-900 px-4 py-2 font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
        >
          {saving ? t('common.saving') : t('common.save')}
        </button>
      </form>

      <Link to="/admin/articles" className="text-sm text-slate-500 underline dark:text-slate-400">
        {t('admin.backToList')}
      </Link>
    </div>
  )
}
