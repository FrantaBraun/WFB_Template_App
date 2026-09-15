/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import DOMPurify from 'dompurify'
import { marked } from 'marked'
import { useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

export interface KnowledgeBasePageData {
  id: string
  title: string
  content: string
  position: number
  created_at: string
  updated_at: string
}

interface KnowledgeBasePageInput {
  title: string
  content: string
}

interface KnowledgeBaseSectionProps {
  /** Caption for this card - a plain string (CollectionDetail.tsx's own KB)
   * or richer content such as a Link (IntegrationDetail.tsx's per-collection
   * groups, captioned "From {collectionName}" and linked back to the
   * collection so a member with permission there can edit it). */
  heading: ReactNode
  pages: KnowledgeBasePageData[]
  canEdit: boolean
  onCreate?: (data: KnowledgeBasePageInput) => Promise<void>
  onUpdate?: (pageId: string, data: KnowledgeBasePageInput) => Promise<void>
  onDelete?: (pageId: string) => Promise<void>
}

const MARKDOWN_CONTENT_CLASS =
  'space-y-2 text-sm text-slate-700 dark:text-slate-300 [&_a]:underline [&_code]:rounded [&_code]:bg-slate-100 [&_code]:px-1 [&_code]:py-0.5 dark:[&_code]:bg-slate-800 [&_h1]:text-lg [&_h1]:font-semibold [&_h2]:text-base [&_h2]:font-semibold [&_h3]:text-sm [&_h3]:font-semibold [&_ol]:list-decimal [&_ol]:pl-5 [&_p]:mb-2 [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-slate-100 [&_pre]:p-3 dark:[&_pre]:bg-slate-800 [&_ul]:list-disc [&_ul]:pl-5'

/**
 * Markdown -> HTML for one page's content, sanitized before render. This is
 * the ONLY place in the codebase that calls dangerouslySetInnerHTML for KB
 * content (CLAUDE.md's "freeform text is never rendered as raw HTML" rule,
 * and the plan's Phase 7 sanitized-Markdown pipeline) - every render path
 * below (a Collection's own KB, an Integration's own pages, an Integration's
 * merged view of each member Collection's pages) goes through this same
 * helper. { async: false } pins marked's overload to a plain string return
 * (no extensions register async behavior here, so this is never actually
 * asynchronous) rather than the string | Promise<string> union its default
 * overload would otherwise produce.
 */
function renderMarkdown(content: string): string {
  const html = marked(content, { async: false })
  return DOMPurify.sanitize(html)
}

/**
 * Reusable, presentational KB page list - mounted by CollectionDetail.tsx
 * (one instance, canEdit tied to the collection's own can_edit) and
 * IntegrationDetail.tsx (one read-only instance per merged collection group,
 * plus one editable instance for the integration's own pages). canEdit=false
 * renders every page read-only with no controls at all, matching a public
 * collection's anonymous-readable KB and an integration's read-only view of
 * a member collection's pages.
 */
export default function KnowledgeBaseSection({ heading, pages, canEdit, onCreate, onUpdate, onDelete }: KnowledgeBaseSectionProps) {
  const { t } = useTranslation()

  const [showAddForm, setShowAddForm] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [newContent, setNewContent] = useState('')
  const [createSaving, setCreateSaving] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  const [editingId, setEditingId] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [editContent, setEditContent] = useState('')
  const [editSaving, setEditSaving] = useState(false)
  const [editError, setEditError] = useState<string | null>(null)

  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  function startEditing(page: KnowledgeBasePageData) {
    setEditingId(page.id)
    setEditTitle(page.title)
    setEditContent(page.content)
    setEditError(null)
  }

  function cancelAdd() {
    setShowAddForm(false)
    setNewTitle('')
    setNewContent('')
    setCreateError(null)
  }

  async function handleCreateSubmit(e: FormEvent) {
    e.preventDefault()
    if (!onCreate) return
    setCreateSaving(true)
    setCreateError(null)
    try {
      await onCreate({ title: newTitle, content: newContent })
      cancelAdd()
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : t('knowledgeBase.addError'))
    } finally {
      setCreateSaving(false)
    }
  }

  async function handleEditSubmit(e: FormEvent, pageId: string) {
    e.preventDefault()
    if (!onUpdate) return
    setEditSaving(true)
    setEditError(null)
    try {
      await onUpdate(pageId, { title: editTitle, content: editContent })
      setEditingId(null)
    } catch (err) {
      setEditError(err instanceof Error ? err.message : t('knowledgeBase.editError'))
    } finally {
      setEditSaving(false)
    }
  }

  async function handleDelete(pageId: string) {
    if (!onDelete) return
    if (!window.confirm(t('knowledgeBase.confirmDelete'))) return
    setDeletingId(pageId)
    setDeleteError(null)
    try {
      await onDelete(pageId)
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : t('knowledgeBase.deleteError'))
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">{heading}</h2>
        {canEdit && !showAddForm && (
          <button
            type="button"
            onClick={() => setShowAddForm(true)}
            className="shrink-0 rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-700 dark:border-slate-700 dark:text-slate-300"
          >
            {t('knowledgeBase.addPage')}
          </button>
        )}
      </div>

      {deleteError && <p className="text-sm text-red-600 dark:text-red-400">{deleteError}</p>}

      {pages.length === 0 && !showAddForm && <p className="text-sm text-slate-600 dark:text-slate-400">{t('knowledgeBase.empty')}</p>}

      {pages.length > 0 && (
        <ul className="divide-y divide-slate-200 dark:divide-slate-800">
          {pages.map((page) => (
            <li key={page.id} className="space-y-2 py-4 first:pt-0 last:pb-0">
              {editingId === page.id ? (
                <form onSubmit={(e) => handleEditSubmit(e, page.id)} className="space-y-3">
                  <div>
                    <label htmlFor={`kb-edit-title-${page.id}`} className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
                      {t('knowledgeBase.titleLabel')}
                    </label>
                    <input
                      id={`kb-edit-title-${page.id}`}
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      required
                      className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
                    />
                  </div>
                  <div>
                    <label htmlFor={`kb-edit-content-${page.id}`} className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
                      {t('knowledgeBase.contentLabel')}
                    </label>
                    <textarea
                      id={`kb-edit-content-${page.id}`}
                      rows={6}
                      value={editContent}
                      onChange={(e) => setEditContent(e.target.value)}
                      className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 font-mono text-sm text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
                    />
                    <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{t('knowledgeBase.contentHint')}</p>
                  </div>
                  {editError && <p className="text-sm text-red-600 dark:text-red-400">{editError}</p>}
                  <div className="flex gap-2">
                    <button
                      type="submit"
                      disabled={editSaving}
                      className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
                    >
                      {editSaving ? t('common.saving') : t('common.save')}
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditingId(null)}
                      className="rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-700 dark:border-slate-700 dark:text-slate-300"
                    >
                      {t('common.cancel')}
                    </button>
                  </div>
                </form>
              ) : (
                <>
                  <div className="flex items-start justify-between gap-4">
                    <h3 className="font-medium text-slate-900 dark:text-slate-100">{page.title}</h3>
                    {canEdit && (
                      <div className="flex shrink-0 gap-3">
                        <button type="button" onClick={() => startEditing(page)} className="text-sm text-slate-600 underline dark:text-slate-400">
                          {t('knowledgeBase.edit')}
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDelete(page.id)}
                          disabled={deletingId === page.id}
                          className="text-sm text-red-600 underline disabled:opacity-50 dark:text-red-400"
                        >
                          {t('knowledgeBase.delete')}
                        </button>
                      </div>
                    )}
                  </div>
                  <div className={MARKDOWN_CONTENT_CLASS} dangerouslySetInnerHTML={{ __html: renderMarkdown(page.content) }} />
                </>
              )}
            </li>
          ))}
        </ul>
      )}

      {canEdit && showAddForm && (
        <form onSubmit={handleCreateSubmit} className="space-y-3 rounded-xl border border-slate-200 p-4 dark:border-slate-700">
          <div>
            <label htmlFor="kb-new-title" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
              {t('knowledgeBase.titleLabel')}
            </label>
            <input
              id="kb-new-title"
              type="text"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              required
              className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
            />
          </div>
          <div>
            <label htmlFor="kb-new-content" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
              {t('knowledgeBase.contentLabel')}
            </label>
            <textarea
              id="kb-new-content"
              rows={6}
              value={newContent}
              onChange={(e) => setNewContent(e.target.value)}
              className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 font-mono text-sm text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
            />
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{t('knowledgeBase.contentHint')}</p>
          </div>
          {createError && <p className="text-sm text-red-600 dark:text-red-400">{createError}</p>}
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={createSaving}
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
            >
              {createSaving ? t('common.saving') : t('knowledgeBase.addPage')}
            </button>
            <button
              type="button"
              onClick={cancelAdd}
              className="rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-700 dark:border-slate-700 dark:text-slate-300"
            >
              {t('common.cancel')}
            </button>
          </div>
        </form>
      )}
    </div>
  )
}
