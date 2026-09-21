/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { apiFetch } from '../api/client'
import KnowledgeBaseSection, { type KnowledgeBasePageData } from '../components/KnowledgeBaseSection'
import usePageMeta from '../hooks/usePageMeta'

interface CollectionDetailData {
  id: string
  team_id: string
  name: string
  description: string | null
  is_public: boolean
  document_count: number
  created_at: string
  can_edit: boolean
  is_subscribed: boolean | null
}

interface ApiDocumentSummaryData {
  id: string
  title: string
  team_id: string
  is_public: boolean
  recheck_period: string
  last_checked_at: string | null
  last_check_error: string | null
  current_version: string | null
}

type Message = { type: 'success' | 'error'; text: string } | null

/**
 * Same-URL, different-capability page for anonymous vs. signed-in visitors,
 * one level up the domain model from ApiDocDetail.tsx - fetches through
 * get_current_user_optional-backed endpoints and never redirects to /login,
 * since a public collection is fully viewable while signed out. can_edit
 * (server-computed, never re-derived client-side per CLAUDE.md) alone gates
 * the edit form, the add-document picker, and each document row's remove
 * action.
 */
export default function CollectionDetail() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [collection, setCollection] = useState<CollectionDetailData | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [documents, setDocuments] = useState<ApiDocumentSummaryData[] | null>(null)
  const [documentsError, setDocumentsError] = useState<string | null>(null)

  const [kbPages, setKbPages] = useState<KnowledgeBasePageData[] | null>(null)
  const [kbError, setKbError] = useState<string | null>(null)

  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [editIsPublic, setEditIsPublic] = useState(false)
  const [editSaving, setEditSaving] = useState(false)
  const [editMessage, setEditMessage] = useState<Message>(null)

  const [availableDocs, setAvailableDocs] = useState<ApiDocumentSummaryData[] | null>(null)
  const [availableDocsError, setAvailableDocsError] = useState<string | null>(null)
  const [addingDocumentId, setAddingDocumentId] = useState<string | null>(null)
  const [addDocumentError, setAddDocumentError] = useState<string | null>(null)

  const [removingDocumentId, setRemovingDocumentId] = useState<string | null>(null)
  const [removeDocumentError, setRemoveDocumentError] = useState<string | null>(null)

  const [subscribing, setSubscribing] = useState(false)
  const [subscribeError, setSubscribeError] = useState<string | null>(null)

  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  usePageMeta({ title: collection?.name ?? t('collections.detail.pageTitleFallback') })

  useEffect(() => {
    if (!id) return
    // :id can change without unmounting (e.g. navigating straight from one
    // collection's page to another's) - guard against a slow-resolving fetch
    // for the PREVIOUS id overwriting state once a newer id's fetch has
    // landed (same pattern as ApiDocDetail.tsx/TeamDetail.tsx).
    let cancelled = false
    setCollection(null)
    setNotFound(false)
    setLoadError(null)
    setDocuments(null)
    setDocumentsError(null)
    setKbPages(null)
    setKbError(null)
    setAvailableDocs(null)
    setAvailableDocsError(null)

    apiFetch(`/api/collections/${id}`)
      .then((r) => {
        if (r.status === 404) {
          if (!cancelled) setNotFound(true)
          return null
        }
        if (!r.ok) return Promise.reject()
        return r.json()
      })
      .then((data: CollectionDetailData | null) => {
        if (cancelled || !data) return
        setCollection(data)
        setEditName(data.name)
        setEditDescription(data.description ?? '')
        setEditIsPublic(data.is_public)
      })
      .catch(() => {
        if (!cancelled) setLoadError(t('collections.detail.loadError'))
      })

    apiFetch(`/api/collections/${id}/documents`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data: ApiDocumentSummaryData[]) => {
        if (!cancelled) setDocuments(data)
      })
      .catch(() => {
        if (!cancelled) setDocumentsError(t('collections.detail.documentsLoadError'))
      })

    apiFetch(`/api/collections/${id}/kb/pages`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data: KnowledgeBasePageData[]) => {
        if (!cancelled) setKbPages(data)
      })
      .catch(() => {
        if (!cancelled) setKbError(t('collections.detail.kbLoadError'))
      })

    return () => {
      cancelled = true
    }
  }, [id, t])

  useEffect(() => {
    if (!collection?.can_edit || !id) return
    let cancelled = false
    Promise.all([
      apiFetch('/api/api-docs').then((r) => (r.ok ? r.json() : Promise.reject())),
      apiFetch('/api/public/api-docs').then((r) => (r.ok ? r.json() : Promise.reject())),
    ])
      .then(([mine, pub]: [ApiDocumentSummaryData[], ApiDocumentSummaryData[]]) => {
        if (cancelled) return
        const byId = new Map<string, ApiDocumentSummaryData>()
        for (const doc of [...mine, ...pub]) byId.set(doc.id, doc)
        setAvailableDocs(Array.from(byId.values()).sort((a, b) => a.title.localeCompare(b.title)))
      })
      .catch(() => {
        if (!cancelled) setAvailableDocsError(t('collections.detail.addDocumentCard.loadError'))
      })
    return () => {
      cancelled = true
    }
  }, [collection?.can_edit, id, t])

  async function handleEditSubmit(e: FormEvent) {
    e.preventDefault()
    if (!id) return
    setEditSaving(true)
    setEditMessage(null)
    try {
      const resp = await apiFetch(`/api/collections/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ name: editName, description: editDescription || null, is_public: editIsPublic }),
      })
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}))
        throw new Error(typeof body.detail === 'string' ? body.detail : t('collections.detail.editCard.error'))
      }
      const updated: CollectionDetailData = await resp.json()
      setCollection(updated)
      setEditMessage({ type: 'success', text: t('collections.detail.editCard.success') })
    } catch (err) {
      setEditMessage({ type: 'error', text: err instanceof Error ? err.message : t('collections.detail.editCard.error') })
    } finally {
      setEditSaving(false)
    }
  }

  async function handleAddDocument(doc: ApiDocumentSummaryData) {
    if (!id) return
    setAddingDocumentId(doc.id)
    setAddDocumentError(null)
    try {
      const resp = await apiFetch(`/api/collections/${id}/documents/${doc.id}`, { method: 'POST' })
      if (!resp.ok) throw new Error(t('collections.detail.addDocumentCard.addError'))
      setDocuments((prev) => (prev ? [...prev, doc].sort((a, b) => a.title.localeCompare(b.title)) : [doc]))
    } catch (err) {
      setAddDocumentError(err instanceof Error ? err.message : t('collections.detail.addDocumentCard.addError'))
    } finally {
      setAddingDocumentId(null)
    }
  }

  async function handleRemoveDocument(documentationId: string) {
    if (!id) return
    setRemovingDocumentId(documentationId)
    setRemoveDocumentError(null)
    try {
      const resp = await apiFetch(`/api/collections/${id}/documents/${documentationId}`, { method: 'DELETE' })
      if (!resp.ok) throw new Error(t('collections.detail.documentsCard.removeError'))
      setDocuments((prev) => (prev ? prev.filter((d) => d.id !== documentationId) : prev))
    } catch (err) {
      setRemoveDocumentError(err instanceof Error ? err.message : t('collections.detail.documentsCard.removeError'))
    } finally {
      setRemovingDocumentId(null)
    }
  }

  async function handleCreateKbPage(data: { title: string; content: string }) {
    if (!id) return
    const resp = await apiFetch(`/api/collections/${id}/kb/pages`, { method: 'POST', body: JSON.stringify(data) })
    if (!resp.ok) throw new Error(t('knowledgeBase.addError'))
    const created: KnowledgeBasePageData = await resp.json()
    setKbPages((prev) => [...(prev ?? []), created])
  }

  async function handleUpdateKbPage(pageId: string, data: { title: string; content: string }) {
    if (!id) return
    const resp = await apiFetch(`/api/collections/${id}/kb/pages/${pageId}`, { method: 'PATCH', body: JSON.stringify(data) })
    if (!resp.ok) throw new Error(t('knowledgeBase.editError'))
    const updated: KnowledgeBasePageData = await resp.json()
    setKbPages((prev) => (prev ? prev.map((p) => (p.id === pageId ? updated : p)) : prev))
  }

  async function handleDeleteKbPage(pageId: string) {
    if (!id) return
    const resp = await apiFetch(`/api/collections/${id}/kb/pages/${pageId}`, { method: 'DELETE' })
    if (!resp.ok) throw new Error(t('knowledgeBase.deleteError'))
    setKbPages((prev) => (prev ? prev.filter((p) => p.id !== pageId) : prev))
  }

  async function handleToggleSubscribe() {
    if (!collection || collection.is_subscribed === null) return
    setSubscribing(true)
    setSubscribeError(null)
    try {
      const resp = await apiFetch(`/api/collections/${collection.id}/subscribe`, {
        method: collection.is_subscribed ? 'DELETE' : 'POST',
      })
      if (!resp.ok) throw new Error(t('notifications.subscribe.error'))
      setCollection((prev) => (prev ? { ...prev, is_subscribed: !prev.is_subscribed } : prev))
    } catch (err) {
      setSubscribeError(err instanceof Error ? err.message : t('notifications.subscribe.error'))
    } finally {
      setSubscribing(false)
    }
  }

  async function handleDelete() {
    if (!collection) return
    if (!window.confirm(t('collections.detail.confirmDelete'))) return
    setDeleting(true)
    setDeleteError(null)
    try {
      const resp = await apiFetch(`/api/collections/${collection.id}`, { method: 'DELETE' })
      if (!resp.ok) throw new Error(t('collections.detail.deleteError'))
      navigate('/collections')
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : t('collections.detail.deleteError'))
      setDeleting(false)
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

  const existingIds = new Set((documents ?? []).map((d) => d.id))
  const addableDocs = (availableDocs ?? []).filter((d) => !existingIds.has(d.id))

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 px-6 py-16 text-slate-900 dark:text-slate-100">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{collection.name}</h1>
          <span
            className={`mt-1 inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
              collection.is_public
                ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300'
                : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'
            }`}
          >
            {collection.is_public ? t('collections.detail.public') : t('collections.detail.private')}
          </span>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-2">
          {collection.is_subscribed !== null && (
            <button
              type="button"
              onClick={handleToggleSubscribe}
              disabled={subscribing}
              className={`rounded-lg border px-3 py-1.5 text-sm font-medium disabled:opacity-50 ${
                collection.is_subscribed
                  ? 'border-emerald-200 bg-emerald-100 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300'
                  : 'border-slate-200 text-slate-700 dark:border-slate-700 dark:text-slate-300'
              }`}
            >
              {subscribing
                ? t('common.saving')
                : collection.is_subscribed
                  ? t('notifications.subscribe.unsubscribe')
                  : t('notifications.subscribe.subscribe')}
            </button>
          )}
          <Link to="/collections" className="text-sm text-slate-600 underline dark:text-slate-400">
            {t('collections.detail.backToList')}
          </Link>
        </div>
      </div>
      {subscribeError && <p className="text-sm text-red-600 dark:text-red-400">{subscribeError}</p>}

      {collection.description && <p className="text-slate-700 dark:text-slate-300">{collection.description}</p>}

      <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
          {t('collections.detail.documentsCard.title')}
        </h2>
        {documentsError && <p className="text-sm text-red-600 dark:text-red-400">{documentsError}</p>}
        {removeDocumentError && <p className="text-sm text-red-600 dark:text-red-400">{removeDocumentError}</p>}
        {documents && documents.length === 0 && (
          <p className="text-sm text-slate-600 dark:text-slate-400">{t('collections.detail.documentsCard.empty')}</p>
        )}
        {documents && documents.length > 0 && (
          <ul className="divide-y divide-slate-200 dark:divide-slate-800">
            {documents.map((doc) => (
              <li key={doc.id} className="flex items-center justify-between gap-4 py-3 text-sm">
                <Link to={`/api-docs/${doc.id}`} className="hover:underline">
                  <p className="font-medium text-slate-900 dark:text-slate-100">{doc.title}</p>
                  <p className="text-slate-500 dark:text-slate-400">
                    {doc.current_version ? t('apiDocs.list.version', { version: doc.current_version }) : t('apiDocs.list.noVersion')}
                  </p>
                </Link>
                {collection.can_edit && (
                  <button
                    type="button"
                    onClick={() => handleRemoveDocument(doc.id)}
                    disabled={removingDocumentId === doc.id}
                    className="shrink-0 rounded-lg border border-slate-200 px-3 py-1.5 text-slate-700 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300"
                  >
                    {t('collections.detail.documentsCard.removeButton')}
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      {kbError && <p className="text-sm text-red-600 dark:text-red-400">{kbError}</p>}
      <KnowledgeBaseSection
        heading={t('knowledgeBase.heading')}
        pages={kbPages ?? []}
        canEdit={collection.can_edit}
        onCreate={collection.can_edit ? handleCreateKbPage : undefined}
        onUpdate={collection.can_edit ? handleUpdateKbPage : undefined}
        onDelete={collection.can_edit ? handleDeleteKbPage : undefined}
      />

      {collection.can_edit && (
        <>
          <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
              {t('collections.detail.addDocumentCard.title')}
            </h2>
            {availableDocsError && <p className="text-sm text-red-600 dark:text-red-400">{availableDocsError}</p>}
            {addDocumentError && <p className="text-sm text-red-600 dark:text-red-400">{addDocumentError}</p>}
            {availableDocs === null && !availableDocsError && (
              <p className="text-sm text-slate-600 dark:text-slate-400">{t('common.loading')}</p>
            )}
            {availableDocs && addableDocs.length === 0 && (
              <p className="text-sm text-slate-600 dark:text-slate-400">{t('collections.detail.addDocumentCard.empty')}</p>
            )}
            {availableDocs && addableDocs.length > 0 && (
              <ul className="divide-y divide-slate-200 dark:divide-slate-800">
                {addableDocs.map((doc) => (
                  <li key={doc.id} className="flex items-center justify-between gap-4 py-3 text-sm">
                    <p className="font-medium text-slate-900 dark:text-slate-100">{doc.title}</p>
                    <button
                      type="button"
                      onClick={() => handleAddDocument(doc)}
                      disabled={addingDocumentId === doc.id}
                      className="shrink-0 rounded-lg border border-slate-200 px-3 py-1.5 text-slate-700 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300"
                    >
                      {t('collections.detail.addDocumentCard.addButton')}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <form
            onSubmit={handleEditSubmit}
            className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900"
          >
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
              {t('collections.detail.editCard.title')}
            </h2>

            <div>
              <label htmlFor="edit-name" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
                {t('collections.detail.editCard.nameLabel')}
              </label>
              <input
                id="edit-name"
                type="text"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                required
                className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
              />
            </div>

            <div>
              <label htmlFor="edit-description" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
                {t('collections.detail.editCard.descriptionLabel')}
              </label>
              <textarea
                id="edit-description"
                rows={3}
                value={editDescription}
                onChange={(e) => setEditDescription(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
              />
            </div>

            <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
              <input
                type="checkbox"
                checked={editIsPublic}
                onChange={(e) => setEditIsPublic(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300 dark:border-slate-700"
              />
              {t('collections.detail.editCard.isPublicLabel')}
            </label>

            {editMessage && (
              <p
                className={`text-sm ${
                  editMessage.type === 'success' ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'
                }`}
              >
                {editMessage.text}
              </p>
            )}

            <button
              type="submit"
              disabled={editSaving}
              className="rounded-lg bg-slate-900 px-4 py-2 font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
            >
              {editSaving ? t('common.saving') : t('common.save')}
            </button>
          </form>

          <div className="flex flex-col items-start gap-2">
            <button
              type="button"
              onClick={handleDelete}
              disabled={deleting}
              className="rounded-lg border border-red-200 px-3 py-1.5 text-sm font-medium text-red-600 disabled:opacity-50 dark:border-red-900 dark:text-red-400"
            >
              {deleting ? t('common.saving') : t('collections.detail.deleteButton')}
            </button>
            {deleteError && <p className="text-sm text-red-600 dark:text-red-400">{deleteError}</p>}
          </div>
        </>
      )}
    </div>
  )
}
