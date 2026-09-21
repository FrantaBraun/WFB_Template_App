/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { apiFetch } from '../api/client'
import { useAuth } from '../context/AuthContext'
import usePageMeta from '../hooks/usePageMeta'

interface KnowledgeBasePageSummary {
  id: string
  title: string
  content_format: string
}

interface IntegrationKBCollectionGroupData {
  collection_id: string
  collection_name: string
  pages: KnowledgeBasePageSummary[]
}

interface IntegrationKBOutData {
  collection_pages: IntegrationKBCollectionGroupData[]
  own_pages: KnowledgeBasePageSummary[]
}

/**
 * Signed-in-only, all-or-nothing visibility, matching IntegrationDetail.tsx's
 * own redirect-to-/login guard - Integration has no public concept. Every
 * member collection's own pages link OUT to that collection's own
 * /collections/:collectionId/kb/:pageId route (never an integration-scoped
 * one) since editing a collection's page always happens at the source
 * collection; this integration's own pages link to its own route instead.
 * No can_edit gating for the "own pages" section - every member who can load
 * this page can edit its own pages too, mirroring IntegrationDetail's own
 * reasoning (that schema has no can_edit field at all).
 */
export default function IntegrationKnowledgeBase() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const { user, loading: authLoading } = useAuth()
  const navigate = useNavigate()

  const [kb, setKb] = useState<IntegrationKBOutData | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  usePageMeta({ title: t('knowledgeBase.heading') })

  useEffect(() => {
    if (!authLoading && !user) {
      navigate('/login', { replace: true })
    }
  }, [authLoading, user, navigate])

  useEffect(() => {
    if (!user || !id) return
    let cancelled = false
    setKb(null)
    setNotFound(false)
    setLoadError(null)

    apiFetch(`/api/integrations/${id}/kb`)
      .then((r) => {
        if (r.status === 404) {
          if (!cancelled) setNotFound(true)
          return null
        }
        if (!r.ok) return Promise.reject()
        return r.json()
      })
      .then((data: IntegrationKBOutData | null) => {
        if (cancelled || !data) return
        setKb(data)
      })
      .catch(() => {
        if (!cancelled) setLoadError(t('integrations.detail.kbLoadError'))
      })

    return () => {
      cancelled = true
    }
  }, [user, id, t])

  async function handleAddPage() {
    if (!id) return
    setCreating(true)
    setCreateError(null)
    try {
      const resp = await apiFetch(`/api/integrations/${id}/kb/pages`, {
        method: 'POST',
        body: JSON.stringify({ title: t('knowledgeBase.untitledPlaceholder'), content: '', content_format: 'markdown' }),
      })
      if (!resp.ok) throw new Error(t('knowledgeBase.addError'))
      const created: { id: string } = await resp.json()
      navigate(`/integrations/${id}/kb/${created.id}/edit`)
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : t('knowledgeBase.addError'))
      setCreating(false)
    }
  }

  if (authLoading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-900 dark:text-slate-100">
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('common.loading')}</p>
      </div>
    )
  }

  if (notFound) {
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-4 px-6 py-16 text-center text-slate-900 dark:text-slate-100">
        <h1 className="text-2xl font-semibold tracking-tight">{t('integrations.detail.notFoundTitle')}</h1>
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('integrations.detail.notFoundMessage')}</p>
        <Link to="/integrations" className="text-sm text-slate-900 underline dark:text-slate-100">
          {t('integrations.detail.backToList')}
        </Link>
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-4 px-6 py-16 text-center text-slate-900 dark:text-slate-100">
        <p className="text-sm text-red-600 dark:text-red-400">{loadError}</p>
        <Link to="/integrations" className="text-sm text-slate-900 underline dark:text-slate-100">
          {t('integrations.detail.backToList')}
        </Link>
      </div>
    )
  }

  if (!kb) {
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
        <Link to={`/integrations/${id}`} className="text-sm text-slate-600 underline dark:text-slate-400">
          {t('knowledgeBase.backToIntegration')}
        </Link>
      </div>

      {kb.collection_pages.map((group) => (
        <div
          key={group.collection_id}
          className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900"
        >
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
            <Link to={`/collections/${group.collection_id}`} className="hover:underline">
              {t('knowledgeBase.fromCollection', { collectionName: group.collection_name })}
            </Link>
          </h2>
          {group.pages.length === 0 && <p className="text-sm text-slate-600 dark:text-slate-400">{t('knowledgeBase.empty')}</p>}
          {group.pages.length > 0 && (
            <ul className="divide-y divide-slate-200 dark:divide-slate-800">
              {group.pages.map((page) => (
                <li key={page.id} className="py-3">
                  <Link to={`/collections/${group.collection_id}/kb/${page.id}`} className="flex items-center justify-between gap-4 hover:underline">
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
      ))}

      <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
        <div className="flex items-center justify-between gap-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
            {t('knowledgeBase.ownPagesHeading')}
          </h2>
          <button
            type="button"
            onClick={handleAddPage}
            disabled={creating}
            className="shrink-0 rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-700 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300"
          >
            {creating ? t('common.saving') : t('knowledgeBase.addPage')}
          </button>
        </div>
        {createError && <p className="text-sm text-red-600 dark:text-red-400">{createError}</p>}
        {kb.own_pages.length === 0 && <p className="text-sm text-slate-600 dark:text-slate-400">{t('knowledgeBase.empty')}</p>}
        {kb.own_pages.length > 0 && (
          <ul className="divide-y divide-slate-200 dark:divide-slate-800">
            {kb.own_pages.map((page) => (
              <li key={page.id} className="py-3">
                <Link to={`/integrations/${id}/kb/${page.id}`} className="flex items-center justify-between gap-4 hover:underline">
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
