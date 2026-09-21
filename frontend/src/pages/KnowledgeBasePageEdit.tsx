/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { EditorContent, useEditor } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'
import TurndownService from 'turndown'
import { apiFetch } from '../api/client'
import { useAuth } from '../context/AuthContext'
import usePageMeta from '../hooks/usePageMeta'
import { KB_CONTENT_CLASS } from '../utils/renderKbContent'

interface KnowledgeBasePageData {
  id: string
  title: string
  content: string
  content_format: string
}

interface KnowledgeBasePageEditProps {
  ownerType: 'collection' | 'integration'
}

type Mode = 'rich' | 'markdown'

const turndownService = new TurndownService()

function ToolbarButton({
  active,
  onClick,
  label,
  children,
}: {
  active: boolean
  onClick: () => void
  label: string
  children: ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      aria-pressed={active}
      className={`min-w-[2rem] rounded-md px-2 py-1 text-sm font-medium ${
        active
          ? 'bg-slate-900 text-slate-100 dark:bg-slate-100 dark:text-slate-900'
          : 'text-slate-700 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
      }`}
    >
      {children}
    </button>
  )
}

/**
 * Mounted at both /collections/:id/kb/:pageId/edit and
 * /integrations/:id/kb/:pageId/edit (App.tsx). The TipTap editor
 * (useEditor) is created once, unconditionally, and stays mounted for this
 * component's whole lifetime regardless of which mode is displayed -
 * EditorContent below is only the VIEW for it, so hiding it while in
 * Markdown mode never destroys the underlying editor, and
 * getHTML()/setContent() stay callable across mode switches.
 */
export default function KnowledgeBasePageEdit({ ownerType }: KnowledgeBasePageEditProps) {
  const { t } = useTranslation()
  const { id, pageId } = useParams<{ id: string; pageId: string }>()
  const { user, loading: authLoading } = useAuth()
  const navigate = useNavigate()

  const [page, setPage] = useState<KnowledgeBasePageData | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [title, setTitle] = useState('')
  const [mode, setMode] = useState<Mode>('markdown')
  const [markdownText, setMarkdownText] = useState('')

  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const hydratedPageIdRef = useRef<string | null>(null)
  const basePath = ownerType === 'collection' ? `/collections/${id}` : `/integrations/${id}`
  const ownerSegment = ownerType === 'collection' ? 'collections' : 'integrations'

  const editor = useEditor({
    extensions: [StarterKit.configure({ link: { openOnClick: false } })],
    content: '',
  })

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

    return () => {
      cancelled = true
    }
  }, [ownerType, ownerSegment, id, pageId, user, t])

  useEffect(() => {
    if (ownerType !== 'collection' || !id || !pageId) return
    let cancelled = false
    apiFetch(`/api/collections/${id}`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data: { can_edit: boolean }) => {
        if (!cancelled && !data.can_edit) navigate(`/collections/${id}/kb/${pageId}`, { replace: true })
      })
      .catch(() => {
        // Best-effort permission check only - the PATCH below is the real
        // enforcement (404 for a non-member) regardless of this outcome.
      })
    return () => {
      cancelled = true
    }
  }, [ownerType, id, pageId, navigate])

  useEffect(() => {
    if (!page || !editor) return
    if (hydratedPageIdRef.current === page.id) return
    hydratedPageIdRef.current = page.id
    setTitle(page.title)
    if (page.content_format === 'html') {
      setMode('rich')
      // A member could still have stored something dangerous, intentionally
      // or via a compromised session - sanitize before it ever reaches the
      // editor's own initial state, even in this member-only editing context.
      editor.commands.setContent(DOMPurify.sanitize(page.content))
      setMarkdownText('')
    } else {
      setMode('markdown')
      setMarkdownText(page.content)
      editor.commands.setContent('')
    }
  }, [page, editor])

  function switchToRichText() {
    if (!editor || mode === 'rich') return
    // marked() passes raw HTML embedded in the source Markdown straight
    // through - sanitize before it reaches the editor's state, same
    // discipline as hydrating an existing page above, even though this
    // particular path only ever affects the current user's own session.
    editor.commands.setContent(DOMPurify.sanitize(marked(markdownText, { async: false })))
    setMode('rich')
  }

  function switchToMarkdown() {
    if (!editor || mode === 'markdown') return
    setMarkdownText(turndownService.turndown(editor.getHTML()))
    setMode('markdown')
  }

  async function handleSave(e: FormEvent) {
    e.preventDefault()
    if (!id || !pageId) return
    setSaving(true)
    setSaveError(null)
    const content = mode === 'rich' ? (editor?.getHTML() ?? '') : markdownText
    const contentFormat = mode === 'rich' ? 'html' : 'markdown'
    try {
      const resp = await apiFetch(`/api/${ownerSegment}/${id}/kb/pages/${pageId}`, {
        method: 'PATCH',
        body: JSON.stringify({ title, content, content_format: contentFormat }),
      })
      if (!resp.ok) throw new Error(t('knowledgeBase.editError'))
      navigate(`${basePath}/kb/${pageId}`)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : t('knowledgeBase.editError'))
    } finally {
      setSaving(false)
    }
  }

  function handleCancel() {
    navigate(`${basePath}/kb/${pageId}`)
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
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="mx-auto flex max-w-2xl flex-col gap-4 px-6 py-16 text-center text-slate-900 dark:text-slate-100">
        <p className="text-sm text-red-600 dark:text-red-400">{loadError}</p>
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
      <h1 className="text-2xl font-semibold tracking-tight">{page.title}</h1>

      <form onSubmit={handleSave} className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
        <div>
          <label htmlFor="kb-edit-title" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
            {t('knowledgeBase.titleLabel')}
          </label>
          <input
            id="kb-edit-title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
          />
        </div>

        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex gap-1 rounded-lg border border-slate-200 p-1 dark:border-slate-700">
              <button
                type="button"
                onClick={switchToRichText}
                className={`rounded-md px-3 py-1 text-sm font-medium ${
                  mode === 'rich' ? 'bg-slate-900 text-slate-100 dark:bg-slate-100 dark:text-slate-900' : 'text-slate-700 dark:text-slate-300'
                }`}
              >
                {t('knowledgeBase.richTextMode')}
              </button>
              <button
                type="button"
                onClick={switchToMarkdown}
                className={`rounded-md px-3 py-1 text-sm font-medium ${
                  mode === 'markdown' ? 'bg-slate-900 text-slate-100 dark:bg-slate-100 dark:text-slate-900' : 'text-slate-700 dark:text-slate-300'
                }`}
              >
                {t('knowledgeBase.markdownMode')}
              </button>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400">{t('knowledgeBase.conversionNote')}</p>
          </div>

          {mode === 'rich' ? (
            <div className="space-y-1">
              {editor && (
                <div className="flex flex-wrap gap-1 rounded-lg border border-slate-200 p-1 dark:border-slate-700">
                  <ToolbarButton active={editor.isActive('bold')} onClick={() => editor.chain().focus().toggleBold().run()} label={t('knowledgeBase.toolbar.bold')}>
                    <strong>B</strong>
                  </ToolbarButton>
                  <ToolbarButton active={editor.isActive('italic')} onClick={() => editor.chain().focus().toggleItalic().run()} label={t('knowledgeBase.toolbar.italic')}>
                    <em>I</em>
                  </ToolbarButton>
                  <ToolbarButton
                    active={editor.isActive('heading', { level: 1 })}
                    onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
                    label={t('knowledgeBase.toolbar.heading1')}
                  >
                    H1
                  </ToolbarButton>
                  <ToolbarButton
                    active={editor.isActive('heading', { level: 2 })}
                    onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
                    label={t('knowledgeBase.toolbar.heading2')}
                  >
                    H2
                  </ToolbarButton>
                  <ToolbarButton
                    active={editor.isActive('heading', { level: 3 })}
                    onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
                    label={t('knowledgeBase.toolbar.heading3')}
                  >
                    H3
                  </ToolbarButton>
                  <ToolbarButton
                    active={editor.isActive('bulletList')}
                    onClick={() => editor.chain().focus().toggleBulletList().run()}
                    label={t('knowledgeBase.toolbar.bulletList')}
                  >
                    •
                  </ToolbarButton>
                  <ToolbarButton
                    active={editor.isActive('orderedList')}
                    onClick={() => editor.chain().focus().toggleOrderedList().run()}
                    label={t('knowledgeBase.toolbar.orderedList')}
                  >
                    1.
                  </ToolbarButton>
                  <ToolbarButton
                    active={editor.isActive('blockquote')}
                    onClick={() => editor.chain().focus().toggleBlockquote().run()}
                    label={t('knowledgeBase.toolbar.blockquote')}
                  >
                    "
                  </ToolbarButton>
                  <ToolbarButton
                    active={editor.isActive('codeBlock')}
                    onClick={() => editor.chain().focus().toggleCodeBlock().run()}
                    label={t('knowledgeBase.toolbar.codeBlock')}
                  >
                    {'</>'}
                  </ToolbarButton>
                </div>
              )}
              <EditorContent
                editor={editor}
                className={`${KB_CONTENT_CLASS} rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-800 dark:bg-slate-950 [&_.ProseMirror]:min-h-48 [&_.ProseMirror]:outline-none`}
              />
            </div>
          ) : (
            <div>
              <textarea
                id="kb-edit-content"
                rows={12}
                value={markdownText}
                onChange={(e) => setMarkdownText(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 font-mono text-sm text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
              />
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{t('knowledgeBase.contentHint')}</p>
            </div>
          )}
        </div>

        {saveError && <p className="text-sm text-red-600 dark:text-red-400">{saveError}</p>}

        <div className="flex gap-2">
          <button
            type="submit"
            disabled={saving}
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
          >
            {saving ? t('common.saving') : t('common.save')}
          </button>
          <button
            type="button"
            onClick={handleCancel}
            className="rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-700 dark:border-slate-700 dark:text-slate-300"
          >
            {t('common.cancel')}
          </button>
        </div>
      </form>
    </div>
  )
}
