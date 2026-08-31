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
import usePageMeta from '../../hooks/usePageMeta'
import useRequireAdmin from '../../hooks/useRequireAdmin'

interface PageData {
  id: string
  heading: string
  slug: string
  content: string
  status: 'draft' | 'published'
  show_in_nav: boolean
}

type Message = { type: 'success' | 'error'; text: string } | null

/** One shared form for both creating and editing a Page - useParams().id
 * present or not decides POST vs. PATCH, mirroring the pattern this repo
 * uses elsewhere of not duplicating near-identical forms. */
export default function AdminPageForm() {
  const { t } = useTranslation()
  usePageMeta({ title: t('admin.pages.title'), description: t('admin.pageDescription') })
  const { user, loading: authLoading } = useRequireAdmin()
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const isEditing = Boolean(id)

  const [heading, setHeading] = useState('')
  const [slug, setSlug] = useState('')
  const [content, setContent] = useState('')
  const [status, setStatus] = useState<'draft' | 'published'>('draft')
  const [showInNav, setShowInNav] = useState(false)
  const [loaded, setLoaded] = useState(!isEditing)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<Message>(null)

  useEffect(() => {
    if (!user?.is_admin || !id) return
    apiFetch(`/api/admin/pages/${id}`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data: PageData) => {
        setHeading(data.heading)
        setSlug(data.slug)
        setContent(data.content)
        setStatus(data.status)
        setShowInNav(data.show_in_nav)
        setLoaded(true)
      })
      .catch(() => setMessage({ type: 'error', text: t('admin.pages.loadError') }))
  }, [user, id, t])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setSaving(true)
    setMessage(null)
    const body = { heading, slug, content, status, show_in_nav: showInNav }
    try {
      const resp = await apiFetch(isEditing ? `/api/admin/pages/${id}` : '/api/admin/pages/', {
        method: isEditing ? 'PATCH' : 'POST',
        body: JSON.stringify(body),
      })
      if (!resp.ok) throw new Error()
      const saved: PageData = await resp.json()
      setMessage({ type: 'success', text: t('admin.pages.saveSuccess') })
      // Transition create -> edit in place so a second save PATCHes the same
      // row instead of risking a duplicate create on re-submit.
      if (!isEditing) navigate(`/admin/pages/${saved.id}/edit`, { replace: true })
    } catch {
      setMessage({ type: 'error', text: t('admin.pages.saveError') })
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
      <h1 className="text-2xl font-semibold tracking-tight">{isEditing ? heading : t('admin.pages.new')}</h1>

      <form
        onSubmit={handleSubmit}
        className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900"
      >
        <div>
          <label htmlFor="heading" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
            {t('admin.pages.headingLabel')}
          </label>
          <input
            id="heading"
            type="text"
            required
            value={heading}
            onChange={(e) => setHeading(e.target.value)}
            className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
          />
        </div>

        <div>
          <label htmlFor="slug" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
            {t('admin.pages.slugLabel')}
          </label>
          <input
            id="slug"
            type="text"
            required
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
          />
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{t('admin.pages.slugHint')}</p>
        </div>

        <div>
          <label className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
            {t('admin.pages.contentLabel')}
          </label>
          <RichTextEditor value={content} onChange={setContent} />
        </div>

        <div className="flex items-center gap-6">
          <div>
            <label htmlFor="status" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
              {t('admin.pages.statusLabel')}
            </label>
            <select
              id="status"
              value={status}
              onChange={(e) => setStatus(e.target.value as 'draft' | 'published')}
              className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
            >
              <option value="draft">{t('admin.status.draft')}</option>
              <option value="published">{t('admin.status.published')}</option>
            </select>
          </div>

          <label className="mt-5 flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
            <input
              type="checkbox"
              checked={showInNav}
              onChange={(e) => setShowInNav(e.target.checked)}
              className="h-4 w-4 rounded border-slate-300"
            />
            {t('admin.pages.showInNavLabel')}
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

      <Link to="/admin/pages" className="text-sm text-slate-500 underline dark:text-slate-400">
        {t('admin.backToList')}
      </Link>
    </div>
  )
}
