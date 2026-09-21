/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { apiFetch } from '../api/client'
import { useAuth } from '../context/AuthContext'
import usePageMeta from '../hooks/usePageMeta'

interface IntegrationDetailData {
  id: string
  team_id: string
  name: string
  description: string | null
  collection_count: number
  direct_document_count: number
  created_at: string
}

interface CollectionSummaryData {
  id: string
  name: string
  team_id: string
  is_public: boolean
  document_count: number
  created_at: string
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

interface IntegrationDocumentSourceData {
  type: 'direct' | 'collection'
  collection_id: string | null
  collection_name: string | null
}

interface IntegrationDocumentOutData extends ApiDocumentSummaryData {
  sources: IntegrationDocumentSourceData[]
}

interface IntegrationKBCollectionGroupData {
  collection_id: string
  pages: { id: string }[]
}

interface IntegrationKBOutData {
  collection_pages: IntegrationKBCollectionGroupData[]
  own_pages: { id: string }[]
}

type Message = { type: 'success' | 'error'; text: string } | null

/**
 * Signed-in-only, all-or-nothing visibility (unlike ApiDocDetail/CollectionDetail
 * there is no anonymous-friendly path at all - Integration has no public
 * concept, per CLAUDE.md) - the redirect-to-/login guard and the
 * notFound-vs-loadError distinction below both mirror TeamDetail.tsx
 * exactly. No can_edit gating anywhere on this page: every signed-in member
 * who can load it (get_current_user + team membership, enforced
 * server-side) can also edit it - IntegrationDetail's own schema has no
 * can_edit field at all for that reason.
 *
 * The backend has no endpoint listing ONLY the direct-linked documents (see
 * backend/app/api/integrations/router.py) - only the merged
 * GET .../documents view. The "direct documents" card below is therefore
 * derived from that same merged response (entries whose sources include a
 * "direct" entry) rather than a separate fetch, and that same derived set
 * is what the add-document picker excludes.
 */
export default function IntegrationDetail() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const { user, loading: authLoading } = useAuth()
  const navigate = useNavigate()

  const [integration, setIntegration] = useState<IntegrationDetailData | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [collections, setCollections] = useState<CollectionSummaryData[] | null>(null)
  const [collectionsError, setCollectionsError] = useState<string | null>(null)

  const [effectiveDocuments, setEffectiveDocuments] = useState<IntegrationDocumentOutData[] | null>(null)
  const [documentsError, setDocumentsError] = useState<string | null>(null)

  const [kb, setKb] = useState<IntegrationKBOutData | null>(null)
  const [kbError, setKbError] = useState<string | null>(null)

  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [editSaving, setEditSaving] = useState(false)
  const [editMessage, setEditMessage] = useState<Message>(null)

  const [availableCollections, setAvailableCollections] = useState<CollectionSummaryData[] | null>(null)
  const [availableCollectionsError, setAvailableCollectionsError] = useState<string | null>(null)
  const [addingCollectionId, setAddingCollectionId] = useState<string | null>(null)
  const [addCollectionError, setAddCollectionError] = useState<string | null>(null)
  const [removingCollectionId, setRemovingCollectionId] = useState<string | null>(null)
  const [removeCollectionError, setRemoveCollectionError] = useState<string | null>(null)

  const [availableDocuments, setAvailableDocuments] = useState<ApiDocumentSummaryData[] | null>(null)
  const [availableDocumentsError, setAvailableDocumentsError] = useState<string | null>(null)
  const [addingDocumentId, setAddingDocumentId] = useState<string | null>(null)
  const [addDocumentError, setAddDocumentError] = useState<string | null>(null)
  const [removingDocumentId, setRemovingDocumentId] = useState<string | null>(null)
  const [removeDocumentError, setRemoveDocumentError] = useState<string | null>(null)

  usePageMeta({ title: integration?.name ?? t('integrations.detail.pageTitleFallback') })

  useEffect(() => {
    if (!authLoading && !user) {
      navigate('/login', { replace: true })
    }
  }, [authLoading, user, navigate])

  useEffect(() => {
    if (!user || !id) return
    // :id can change without unmounting (e.g. navigating straight from one
    // integration's page to another's) - guard against a slow-resolving
    // fetch for the PREVIOUS id overwriting state once a newer id's fetch
    // has already landed (same pattern as CollectionDetail.tsx/TeamDetail.tsx).
    let cancelled = false
    setIntegration(null)
    setNotFound(false)
    setLoadError(null)
    setCollections(null)
    setCollectionsError(null)
    setEffectiveDocuments(null)
    setDocumentsError(null)
    setKb(null)
    setKbError(null)
    setAvailableCollections(null)
    setAvailableCollectionsError(null)
    setAvailableDocuments(null)
    setAvailableDocumentsError(null)

    apiFetch(`/api/integrations/${id}`)
      .then((r) => {
        if (r.status === 404) {
          if (!cancelled) setNotFound(true)
          return null
        }
        if (!r.ok) return Promise.reject()
        return r.json()
      })
      .then((data: IntegrationDetailData | null) => {
        if (cancelled || !data) return
        setIntegration(data)
        setEditName(data.name)
        setEditDescription(data.description ?? '')
      })
      .catch(() => {
        if (!cancelled) setLoadError(t('integrations.detail.loadError'))
      })

    apiFetch(`/api/integrations/${id}/collections`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data: CollectionSummaryData[]) => {
        if (!cancelled) setCollections(data)
      })
      .catch(() => {
        if (!cancelled) setCollectionsError(t('integrations.detail.collectionsLoadError'))
      })

    apiFetch(`/api/integrations/${id}/documents`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data: IntegrationDocumentOutData[]) => {
        if (!cancelled) setEffectiveDocuments(data)
      })
      .catch(() => {
        if (!cancelled) setDocumentsError(t('integrations.detail.documentsLoadError'))
      })

    apiFetch(`/api/integrations/${id}/kb`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data: IntegrationKBOutData) => {
        if (!cancelled) setKb(data)
      })
      .catch(() => {
        if (!cancelled) setKbError(t('integrations.detail.kbLoadError'))
      })

    return () => {
      cancelled = true
    }
  }, [user, id, t])

  useEffect(() => {
    if (!integration || !id) return
    let cancelled = false
    Promise.all([
      apiFetch('/api/collections').then((r) => (r.ok ? r.json() : Promise.reject())),
      apiFetch('/api/public/collections').then((r) => (r.ok ? r.json() : Promise.reject())),
    ])
      .then(([mine, pub]: [CollectionSummaryData[], CollectionSummaryData[]]) => {
        if (cancelled) return
        const byId = new Map<string, CollectionSummaryData>()
        for (const collection of [...mine, ...pub]) byId.set(collection.id, collection)
        setAvailableCollections(Array.from(byId.values()).sort((a, b) => a.name.localeCompare(b.name)))
      })
      .catch(() => {
        if (!cancelled) setAvailableCollectionsError(t('integrations.detail.addCollectionCard.loadError'))
      })

    Promise.all([
      apiFetch('/api/api-docs').then((r) => (r.ok ? r.json() : Promise.reject())),
      apiFetch('/api/public/api-docs').then((r) => (r.ok ? r.json() : Promise.reject())),
    ])
      .then(([mine, pub]: [ApiDocumentSummaryData[], ApiDocumentSummaryData[]]) => {
        if (cancelled) return
        const byId = new Map<string, ApiDocumentSummaryData>()
        for (const doc of [...mine, ...pub]) byId.set(doc.id, doc)
        setAvailableDocuments(Array.from(byId.values()).sort((a, b) => a.title.localeCompare(b.title)))
      })
      .catch(() => {
        if (!cancelled) setAvailableDocumentsError(t('integrations.detail.addDocumentCard.loadError'))
      })

    return () => {
      cancelled = true
    }
  }, [integration, id, t])

  if (authLoading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-900 dark:text-slate-100">
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('common.loading')}</p>
      </div>
    )
  }

  // Adding/removing a Collection changes which documents this integration
  // reaches (via that collection's own members), and a direct document
  // add/remove obviously does too - so every mutation below refreshes the
  // merged view from the server rather than trying to replicate its
  // dedup/source-tagging logic client-side. Collections themselves don't
  // need a refetch: the full CollectionSummary being added/removed is
  // already known locally (from availableCollections, or the row itself).
  async function reloadEffectiveDocuments() {
    if (!id) return
    try {
      const resp = await apiFetch(`/api/integrations/${id}/documents`)
      if (resp.ok) setEffectiveDocuments(await resp.json())
    } catch {
      // Best-effort refresh after an already-successful mutation - a
      // transient failure here just leaves the previous list displayed
      // instead of piling a second error on top of a successful action.
    }
  }

  async function handleEditSubmit(e: FormEvent) {
    e.preventDefault()
    if (!id) return
    setEditSaving(true)
    setEditMessage(null)
    try {
      const resp = await apiFetch(`/api/integrations/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ name: editName, description: editDescription || null }),
      })
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}))
        throw new Error(typeof body.detail === 'string' ? body.detail : t('integrations.detail.editCard.error'))
      }
      const updated: IntegrationDetailData = await resp.json()
      setIntegration(updated)
      setEditMessage({ type: 'success', text: t('integrations.detail.editCard.success') })
    } catch (err) {
      setEditMessage({ type: 'error', text: err instanceof Error ? err.message : t('integrations.detail.editCard.error') })
    } finally {
      setEditSaving(false)
    }
  }

  async function handleAddCollection(collection: CollectionSummaryData) {
    if (!id) return
    setAddingCollectionId(collection.id)
    setAddCollectionError(null)
    try {
      const resp = await apiFetch(`/api/integrations/${id}/collections/${collection.id}`, { method: 'POST' })
      if (!resp.ok) throw new Error(t('integrations.detail.addCollectionCard.addError'))
      setCollections((prev) => (prev ? [...prev, collection].sort((a, b) => a.name.localeCompare(b.name)) : [collection]))
      await reloadEffectiveDocuments()
    } catch (err) {
      setAddCollectionError(err instanceof Error ? err.message : t('integrations.detail.addCollectionCard.addError'))
    } finally {
      setAddingCollectionId(null)
    }
  }

  async function handleRemoveCollection(collectionId: string) {
    if (!id) return
    setRemovingCollectionId(collectionId)
    setRemoveCollectionError(null)
    try {
      const resp = await apiFetch(`/api/integrations/${id}/collections/${collectionId}`, { method: 'DELETE' })
      if (!resp.ok) throw new Error(t('integrations.detail.collectionsCard.removeError'))
      setCollections((prev) => (prev ? prev.filter((c) => c.id !== collectionId) : prev))
      await reloadEffectiveDocuments()
    } catch (err) {
      setRemoveCollectionError(err instanceof Error ? err.message : t('integrations.detail.collectionsCard.removeError'))
    } finally {
      setRemovingCollectionId(null)
    }
  }

  async function handleAddDocument(doc: ApiDocumentSummaryData) {
    if (!id) return
    setAddingDocumentId(doc.id)
    setAddDocumentError(null)
    try {
      const resp = await apiFetch(`/api/integrations/${id}/documents/${doc.id}`, { method: 'POST' })
      if (!resp.ok) throw new Error(t('integrations.detail.addDocumentCard.addError'))
      await reloadEffectiveDocuments()
    } catch (err) {
      setAddDocumentError(err instanceof Error ? err.message : t('integrations.detail.addDocumentCard.addError'))
    } finally {
      setAddingDocumentId(null)
    }
  }

  async function handleRemoveDocument(documentationId: string) {
    if (!id) return
    setRemovingDocumentId(documentationId)
    setRemoveDocumentError(null)
    try {
      const resp = await apiFetch(`/api/integrations/${id}/documents/${documentationId}`, { method: 'DELETE' })
      if (!resp.ok) throw new Error(t('integrations.detail.directDocumentsCard.removeError'))
      await reloadEffectiveDocuments()
    } catch (err) {
      setRemoveDocumentError(err instanceof Error ? err.message : t('integrations.detail.directDocumentsCard.removeError'))
    } finally {
      setRemovingDocumentId(null)
    }
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

  if (!integration) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-900 dark:text-slate-100">
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('common.loading')}</p>
      </div>
    )
  }

  const existingCollectionIds = new Set((collections ?? []).map((c) => c.id))
  const addableCollections = (availableCollections ?? []).filter((c) => !existingCollectionIds.has(c.id))

  const directDocuments = (effectiveDocuments ?? []).filter((d) => d.sources.some((s) => s.type === 'direct'))
  const directDocumentIds = new Set(directDocuments.map((d) => d.id))
  const addableDocuments = (availableDocuments ?? []).filter((d) => !directDocumentIds.has(d.id))

  const kbPageTotal = kb ? kb.own_pages.length + kb.collection_pages.reduce((sum, group) => sum + group.pages.length, 0) : null

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 px-6 py-16 text-slate-900 dark:text-slate-100">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">{integration.name}</h1>
        <Link to="/integrations" className="text-sm text-slate-600 underline dark:text-slate-400">
          {t('integrations.detail.backToList')}
        </Link>
      </div>

      {integration.description && <p className="text-slate-700 dark:text-slate-300">{integration.description}</p>}

      <form
        onSubmit={handleEditSubmit}
        className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900"
      >
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
          {t('integrations.detail.editCard.title')}
        </h2>

        <div>
          <label htmlFor="edit-name" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
            {t('integrations.detail.editCard.nameLabel')}
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
            {t('integrations.detail.editCard.descriptionLabel')}
          </label>
          <textarea
            id="edit-description"
            rows={3}
            value={editDescription}
            onChange={(e) => setEditDescription(e.target.value)}
            className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
          />
        </div>

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

      <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
          {t('integrations.detail.collectionsCard.title')}
        </h2>
        {collectionsError && <p className="text-sm text-red-600 dark:text-red-400">{collectionsError}</p>}
        {removeCollectionError && <p className="text-sm text-red-600 dark:text-red-400">{removeCollectionError}</p>}
        {collections && collections.length === 0 && (
          <p className="text-sm text-slate-600 dark:text-slate-400">{t('integrations.detail.collectionsCard.empty')}</p>
        )}
        {collections && collections.length > 0 && (
          <ul className="divide-y divide-slate-200 dark:divide-slate-800">
            {collections.map((collection) => (
              <li key={collection.id} className="flex items-center justify-between gap-4 py-3 text-sm">
                <Link to={`/collections/${collection.id}`} className="hover:underline">
                  <p className="font-medium text-slate-900 dark:text-slate-100">{collection.name}</p>
                  <p className="text-slate-500 dark:text-slate-400">
                    {collection.document_count}{' '}
                    {t(
                      collection.document_count === 1
                        ? 'collections.list.documentSingular'
                        : 'collections.list.documentPlural',
                    )}
                  </p>
                </Link>
                <button
                  type="button"
                  onClick={() => handleRemoveCollection(collection.id)}
                  disabled={removingCollectionId === collection.id}
                  className="shrink-0 rounded-lg border border-slate-200 px-3 py-1.5 text-slate-700 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300"
                >
                  {t('integrations.detail.collectionsCard.removeButton')}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
          {t('integrations.detail.addCollectionCard.title')}
        </h2>
        {availableCollectionsError && <p className="text-sm text-red-600 dark:text-red-400">{availableCollectionsError}</p>}
        {addCollectionError && <p className="text-sm text-red-600 dark:text-red-400">{addCollectionError}</p>}
        {availableCollections === null && !availableCollectionsError && (
          <p className="text-sm text-slate-600 dark:text-slate-400">{t('common.loading')}</p>
        )}
        {availableCollections && addableCollections.length === 0 && (
          <p className="text-sm text-slate-600 dark:text-slate-400">{t('integrations.detail.addCollectionCard.empty')}</p>
        )}
        {availableCollections && addableCollections.length > 0 && (
          <ul className="divide-y divide-slate-200 dark:divide-slate-800">
            {addableCollections.map((collection) => (
              <li key={collection.id} className="flex items-center justify-between gap-4 py-3 text-sm">
                <p className="font-medium text-slate-900 dark:text-slate-100">{collection.name}</p>
                <button
                  type="button"
                  onClick={() => handleAddCollection(collection)}
                  disabled={addingCollectionId === collection.id}
                  className="shrink-0 rounded-lg border border-slate-200 px-3 py-1.5 text-slate-700 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300"
                >
                  {t('integrations.detail.addCollectionCard.addButton')}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
          {t('integrations.detail.directDocumentsCard.title')}
        </h2>
        {removeDocumentError && <p className="text-sm text-red-600 dark:text-red-400">{removeDocumentError}</p>}
        {effectiveDocuments && directDocuments.length === 0 && (
          <p className="text-sm text-slate-600 dark:text-slate-400">{t('integrations.detail.directDocumentsCard.empty')}</p>
        )}
        {directDocuments.length > 0 && (
          <ul className="divide-y divide-slate-200 dark:divide-slate-800">
            {directDocuments.map((doc) => (
              <li key={doc.id} className="flex items-center justify-between gap-4 py-3 text-sm">
                <Link to={`/api-docs/${doc.id}`} className="hover:underline">
                  <p className="font-medium text-slate-900 dark:text-slate-100">{doc.title}</p>
                  <p className="text-slate-500 dark:text-slate-400">
                    {doc.current_version ? t('apiDocs.list.version', { version: doc.current_version }) : t('apiDocs.list.noVersion')}
                  </p>
                </Link>
                <button
                  type="button"
                  onClick={() => handleRemoveDocument(doc.id)}
                  disabled={removingDocumentId === doc.id}
                  className="shrink-0 rounded-lg border border-slate-200 px-3 py-1.5 text-slate-700 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300"
                >
                  {t('integrations.detail.directDocumentsCard.removeButton')}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
          {t('integrations.detail.addDocumentCard.title')}
        </h2>
        {availableDocumentsError && <p className="text-sm text-red-600 dark:text-red-400">{availableDocumentsError}</p>}
        {addDocumentError && <p className="text-sm text-red-600 dark:text-red-400">{addDocumentError}</p>}
        {availableDocuments === null && !availableDocumentsError && (
          <p className="text-sm text-slate-600 dark:text-slate-400">{t('common.loading')}</p>
        )}
        {availableDocuments && addableDocuments.length === 0 && (
          <p className="text-sm text-slate-600 dark:text-slate-400">{t('integrations.detail.addDocumentCard.empty')}</p>
        )}
        {availableDocuments && addableDocuments.length > 0 && (
          <ul className="divide-y divide-slate-200 dark:divide-slate-800">
            {addableDocuments.map((doc) => (
              <li key={doc.id} className="flex items-center justify-between gap-4 py-3 text-sm">
                <p className="font-medium text-slate-900 dark:text-slate-100">{doc.title}</p>
                <button
                  type="button"
                  onClick={() => handleAddDocument(doc)}
                  disabled={addingDocumentId === doc.id}
                  className="shrink-0 rounded-lg border border-slate-200 px-3 py-1.5 text-slate-700 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300"
                >
                  {t('integrations.detail.addDocumentCard.addButton')}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
          {t('integrations.detail.effectiveDocumentsCard.title')}
        </h2>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {t('integrations.detail.effectiveDocumentsCard.description')}
        </p>
        {documentsError && <p className="text-sm text-red-600 dark:text-red-400">{documentsError}</p>}
        {effectiveDocuments && effectiveDocuments.length === 0 && (
          <p className="text-sm text-slate-600 dark:text-slate-400">{t('integrations.detail.effectiveDocumentsCard.empty')}</p>
        )}
        {effectiveDocuments && effectiveDocuments.length > 0 && (
          <ul className="divide-y divide-slate-200 dark:divide-slate-800">
            {effectiveDocuments.map((doc) => (
              <li key={doc.id} className="py-3 text-sm">
                <Link to={`/api-docs/${doc.id}`} className="hover:underline">
                  <p className="font-medium text-slate-900 dark:text-slate-100">{doc.title}</p>
                  <p className="text-slate-500 dark:text-slate-400">
                    {doc.current_version ? t('apiDocs.list.version', { version: doc.current_version }) : t('apiDocs.list.noVersion')}
                  </p>
                </Link>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {doc.sources.map((source, index) =>
                    source.type === 'direct' ? (
                      <span
                        key={`direct-${index}`}
                        className="inline-block rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300"
                      >
                        {t('integrations.detail.effectiveDocumentsCard.sourceDirect')}
                      </span>
                    ) : (
                      <span
                        key={`collection-${source.collection_id}`}
                        className="inline-block rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300"
                      >
                        {t('integrations.detail.effectiveDocumentsCard.sourceCollection', {
                          collectionName: source.collection_name,
                        })}
                      </span>
                    ),
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="space-y-2 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">{t('knowledgeBase.heading')}</h2>
        {kbError && <p className="text-sm text-red-600 dark:text-red-400">{kbError}</p>}
        <p className="text-sm text-slate-600 dark:text-slate-400">
          {kbPageTotal === null
            ? t('common.loading')
            : `${kbPageTotal} ${t(kbPageTotal === 1 ? 'knowledgeBase.pageCountSingular' : 'knowledgeBase.pageCountPlural')}`}
        </p>
        <Link to={`/integrations/${id}/kb`} className="text-sm text-slate-900 underline dark:text-slate-100">
          {t('knowledgeBase.browseLink')}
        </Link>
      </div>
    </div>
  )
}
