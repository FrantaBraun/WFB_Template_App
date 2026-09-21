/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { apiFetch } from '../api/client'
import usePageMeta from '../hooks/usePageMeta'

interface CollectionData {
  id: string
  name: string
  can_edit: boolean
}

interface KnowledgeBasePageSummary {
  id: string
  title: string
  content_format: string
}

/**
 * Same-URL, different-capability page as CollectionDetail.tsx - fetches
 * through get_current_user_optional-backed endpoints, so a public
 * collection's page list is browsable while signed out. can_edit (from the
 * collection's own detail response, never re-derived client-side) alone
 * gates the "Add page" action; editing an individual page happens on its own
 * dedicated route, reached via the links below.
 */
export default function CollectionKnowledgeBase() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [collection, setCollection] = useState<CollectionData | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [pages, setPages] = useState<KnowledgeBasePageSummary[] | null>(null)
  const [pagesError, setPagesError] = useState<string | null>(null)

  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  usePageMeta({ title: t('knowledgeBase.heading') })

  useEffect(() => {
    if (!id) return
    let cancelled = false
    setCollection(null)
    setNotFound(false)
    setLoadError(null)
    setPages(null)
    setPagesError(null)

    apiFetch(`/api/collections/${id}`)
      .then((r) => {
        if (r.status === 404) {
          if (!cancelled) setNotFound(true)
          return null
        }
        if (!r.ok) return Promise.reject()
        return r.json()
      })
      .then((data: CollectionData | null) => {
        if (cancelled || !data) return
        setCollection(data)
      })
      .catch(() => {
        if (!cancelled) setLoadError(t('collections.detail.loadError'))
      })

    apiFetch(`/api/collections/${id}/kb/pages`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data: KnowledgeBasePageSummary[]) => {
        if (!cancelled) setPages(data)
      })
      .catch(() => {
        if (!cancelled) setPagesError(t('collections.detail.kbLoadError'))
      })

    return () => {
      cancelled = true
    }
  }, [id, t])

  async function handleAddPage() {
    if (!id) return
    setCreating(true)
    setCreateError(null)
    try {
      const resp = await apiFetch(`/api/collections/${id}/kb/pages`, {
        method: 'POST',
        body: JSON.stringify({ title: t('knowledgeBase.untitledPlaceholder'), content: '', content_format: 'markdown' }),
      })
      if (!resp.ok) throw new Error(t('knowledgeBase.addError'))
      const created: { id: string } = await resp.json()
      navigate(`/collections/${id}/kb/${created.id}/edit`)
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : t('knowledgeBase.addError'))
      setCreating(false)
    }
  }

  if (notFound) {
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-4 px-6 py-16 text-center text-slate-900 dark:text-slate-100">
        <h1 className="text-2xl font-semibold tracking-tight">{t('collections.detail.notFoundTitle')}</h1>
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('collections.detail.notFoundMessage')}</p>
        <Link to="/collections" className="text-sm text-slate-900 underline dark:text-slate-100">
          {t('collections.detail.backToList')}
        </Link>
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-4 px-6 py-16 text-center text-slate-900 dark:text-slate-100">
        <p className="text-sm text-red-600 dark:text-red-400">{loadError}</p>
        <Link to="/collections" className="text-sm text-slate-900 underline dark:text-slate-100">
          {t('collections.detail.backToList')}
        </Link>
      </div>
    )
  }

  if (!collection) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-900 dark:text-slate-100">
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('common.loading')}</p>
      </div>
    )
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 px-6 py-16 text-slate-900 dark:text-slate-100">
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">{t('knowledgeBase.heading')}</h1>
        <Link to={`/collections/${id}`} className="text-sm text-slate-600 underline dark:text-slate-400">
          {t('knowledgeBase.backToCollection')}
        </Link>
      </div>

      <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
        <div className="flex items-center justify-between gap-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">{collection.name}</h2>
          {collection.can_edit && (
            <button
              type="button"
              onClick={handleAddPage}
              disabled={creating}
              className="shrink-0 rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-700 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300"
            >
              {creating ? t('common.saving') : t('knowledgeBase.addPage')}
            </button>
          )}
        </div>

        {pagesError && <p className="text-sm text-red-600 dark:text-red-400">{pagesError}</p>}
        {createError && <p className="text-sm text-red-600 dark:text-red-400">{createError}</p>}

        {pages && pages.length === 0 && <p className="text-sm text-slate-600 dark:text-slate-400">{t('knowledgeBase.empty')}</p>}

        {pages && pages.length > 0 && (
          <ul className="divide-y divide-slate-200 dark:divide-slate-800">
            {pages.map((page) => (
              <li key={page.id} className="py-3">
                <Link to={`/collections/${id}/kb/${page.id}`} className="flex items-center justify-between gap-4 hover:underline">
                  <span className="font-medium text-slate-900 dark:text-slate-100">{page.title}</span>
                  <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                    {page.content_format === 'html' ? t('knowledgeBase.formatHtml') : t('knowledgeBase.formatMarkdown')}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
