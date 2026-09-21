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
import { KB_CONTENT_CLASS, renderKbContent } from '../utils/renderKbContent'

interface KnowledgeBasePageData {
  id: string
  title: string
  content: string
  content_format: string
}

interface KnowledgeBasePageViewProps {
  ownerType: 'collection' | 'integration'
}

/**
 * Mounted at both /collections/:id/kb/:pageId and /integrations/:id/kb/:pageId
 * (App.tsx) - ownerType picks the owner's own single-page GET/DELETE
 * endpoints and can_edit rule, everything else about the two variants is
 * identical. A collection-owned page reached through an integration's merged
 * KB view is only ever linked to via the collection's own route
 * (IntegrationKnowledgeBase.tsx), so this component never needs to reason
 * about that distinction itself.
 */
export default function KnowledgeBasePageView({ ownerType }: KnowledgeBasePageViewProps) {
  const { t } = useTranslation()
  const { id, pageId } = useParams<{ id: string; pageId: string }>()
  const { user, loading: authLoading } = useAuth()
  const navigate = useNavigate()

  const [page, setPage] = useState<KnowledgeBasePageData | null>(null)
  const [canEdit, setCanEdit] = useState(false)
  const [notFound, setNotFound] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const basePath = ownerType === 'collection' ? `/collections/${id}` : `/integrations/${id}`
  const ownerSegment = ownerType === 'collection' ? 'collections' : 'integrations'

  usePageMeta({ title: page?.title ?? t('knowledgeBase.heading') })

  useEffect(() => {
    if (ownerType === 'integration' && !authLoading && !user) {
      navigate('/login', { replace: true })
    }
  }, [ownerType, authLoading, user, navigate])

  useEffect(() => {
    if (!id || !pageId) return
    if (ownerType === 'integration' && !user) return
    let cancelled = false
    setPage(null)
    setCanEdit(false)
    setNotFound(false)
    setLoadError(null)

    apiFetch(`/api/${ownerSegment}/${id}/kb/pages/${pageId}`)
      .then((r) => {
        if (r.status === 404) {
          if (!cancelled) setNotFound(true)
          return null
        }
        if (!r.ok) return Promise.reject()
        return r.json()
      })
      .then((data: KnowledgeBasePageData | null) => {
        if (cancelled || !data) return
        setPage(data)
      })
      .catch(() => {
        if (!cancelled) setLoadError(t('knowledgeBase.pageLoadError'))
      })

    if (ownerType === 'collection') {
      apiFetch(`/api/collections/${id}`)
        .then((r) => (r.ok ? r.json() : Promise.reject()))
        .then((data: { can_edit: boolean }) => {
          if (!cancelled) setCanEdit(data.can_edit)
        })
        .catch(() => {
          // Best-effort: a failure here just leaves editing controls hidden,
          // it never blocks viewing the page content itself (fetched above).
        })
    } else {
      setCanEdit(true)
    }

    return () => {
      cancelled = true
    }
  }, [ownerType, ownerSegment, id, pageId, user, t])

  async function handleDelete() {
    if (!id || !pageId) return
    if (!window.confirm(t('knowledgeBase.confirmDelete'))) return
    setDeleting(true)
    setDeleteError(null)
    try {
      const resp = await apiFetch(`/api/${ownerSegment}/${id}/kb/pages/${pageId}`, { method: 'DELETE' })
      if (!resp.ok) throw new Error(t('knowledgeBase.deleteError'))
      navigate(`${basePath}/kb`)
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : t('knowledgeBase.deleteError'))
      setDeleting(false)
    }
  }

  if (ownerType === 'integration' && (authLoading || !user)) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-900 dark:text-slate-100">
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('common.loading')}</p>
      </div>
    )
  }

  if (notFound) {
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-4 px-6 py-16 text-center text-slate-900 dark:text-slate-100">
        <h1 className="text-2xl font-semibold tracking-tight">{t('knowledgeBase.notFoundTitle')}</h1>
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('knowledgeBase.notFoundMessage')}</p>
        <Link to={`${basePath}/kb`} className="text-sm text-slate-900 underline dark:text-slate-100">
          {t('knowledgeBase.backToBrowse')}
        </Link>
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-4 px-6 py-16 text-center text-slate-900 dark:text-slate-100">
        <p className="text-sm text-red-600 dark:text-red-400">{loadError}</p>
        <Link to={`${basePath}/kb`} className="text-sm text-slate-900 underline dark:text-slate-100">
          {t('knowledgeBase.backToBrowse')}
        </Link>
      </div>
    )
  }

  if (!page) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-900 dark:text-slate-100">
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('common.loading')}</p>
      </div>
    )
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 px-6 py-16 text-slate-900 dark:text-slate-100">
      <div className="flex items-start justify-between gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">{page.title}</h1>
        <Link to={`${basePath}/kb`} className="shrink-0 text-sm text-slate-600 underline dark:text-slate-400">
          {t('knowledgeBase.backToBrowse')}
        </Link>
      </div>

      {canEdit && (
        <div className="flex gap-3">
          <Link to={`${basePath}/kb/${pageId}/edit`} className="text-sm text-slate-600 underline dark:text-slate-400">
            {t('knowledgeBase.edit')}
          </Link>
          <button
            type="button"
            onClick={handleDelete}
            disabled={deleting}
            className="text-sm text-red-600 underline disabled:opacity-50 dark:text-red-400"
          >
            {t('knowledgeBase.delete')}
          </button>
        </div>
      )}
      {deleteError && <p className="text-sm text-red-600 dark:text-red-400">{deleteError}</p>}

      <div className="rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
        <div className={KB_CONTENT_CLASS} dangerouslySetInnerHTML={{ __html: renderKbContent(page.content, page.content_format) }} />
      </div>
    </div>
  )
}
