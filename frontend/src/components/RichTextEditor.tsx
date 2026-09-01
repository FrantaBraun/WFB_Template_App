/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { Extension } from '@tiptap/core'
import ImageExtension from '@tiptap/extension-image'
import LinkExtension from '@tiptap/extension-link'
import { EditorContent, ReactRenderer, useEditor, type Editor } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Suggestion, { type SuggestionOptions } from '@tiptap/suggestion'
import { useEffect, useRef, type ChangeEvent } from 'react'
import tippy, { type Instance as TippyInstance } from 'tippy.js'
import { apiFetch } from '../api/client'
import MentionList from './MentionList'

export interface MentionableItem {
  type: 'page' | 'article'
  id: string
  label: string
  slug: string
}

function mentionUrl(item: MentionableItem): string {
  return item.type === 'page' ? `/${item.slug}` : `/clanek/${item.slug}`
}

/**
 * Builds the @-mention Suggestion config. `getItems` reads from a ref rather
 * than a closed-over array so the suggestion list stays live as the
 * mentionable list loads/changes, without needing to recreate the editor.
 */
function createMentionSuggestion(getItems: () => MentionableItem[]): Partial<SuggestionOptions> {
  return {
    char: '@',
    items: ({ query }) =>
      getItems()
        .filter((item) => item.label.toLowerCase().includes(query.toLowerCase()))
        .slice(0, 10),
    render: () => {
      let component: ReactRenderer
      let popup: TippyInstance[]

      return {
        onStart: (props) => {
          component = new ReactRenderer(MentionList, { props, editor: props.editor })
          if (!props.clientRect) return
          popup = tippy('body', {
            getReferenceClientRect: props.clientRect as () => DOMRect,
            appendTo: () => document.body,
            content: component.element,
            showOnCreate: true,
            interactive: true,
            trigger: 'manual',
            placement: 'bottom-start',
          })
        },
        onUpdate(props) {
          component.updateProps(props)
          if (!props.clientRect) return
          popup[0].setProps({ getReferenceClientRect: props.clientRect as () => DOMRect })
        },
        onKeyDown(props) {
          if (props.event.key === 'Escape') {
            popup[0].hide()
            return true
          }
          return (component.ref as { onKeyDown: (p: typeof props) => boolean } | null)?.onKeyDown(props) ?? false
        },
        onExit() {
          popup[0].destroy()
          component.destroy()
        },
      }
    },
    command: ({ editor, range, props }) => {
      const item = props as MentionableItem
      editor
        .chain()
        .focus()
        .insertContentAt(range, [
          { type: 'text', text: item.label, marks: [{ type: 'link', attrs: { href: mentionUrl(item) } }] },
          { type: 'text', text: ' ' },
        ])
        .run()
    },
  }
}

const MentionSuggestion = Extension.create<{ suggestion: Partial<SuggestionOptions> }>({
  name: 'mentionSuggestion',
  addOptions() {
    return { suggestion: {} }
  },
  addProseMirrorPlugins() {
    return [Suggestion({ editor: this.editor, ...this.options.suggestion })]
  },
})

function ToolbarButton({
  active,
  onClick,
  children,
}: {
  active?: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded px-2 py-1 text-sm ${
        active
          ? 'bg-slate-900 text-slate-100 dark:bg-slate-100 dark:text-slate-900'
          : 'text-slate-700 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
      }`}
    >
      {children}
    </button>
  )
}

function Toolbar({ editor, onInsertImage }: { editor: Editor; onInsertImage: () => void }) {
  return (
    <div className="flex flex-wrap items-center gap-1 border-b border-slate-200 p-2 dark:border-slate-800">
      <ToolbarButton active={editor.isActive('bold')} onClick={() => editor.chain().focus().toggleBold().run()}>
        <span className="font-bold">B</span>
      </ToolbarButton>
      <ToolbarButton active={editor.isActive('italic')} onClick={() => editor.chain().focus().toggleItalic().run()}>
        <span className="italic">I</span>
      </ToolbarButton>
      <ToolbarButton
        active={editor.isActive('bulletList')}
        onClick={() => editor.chain().focus().toggleBulletList().run()}
      >
        Seznam
      </ToolbarButton>
      <ToolbarButton
        active={editor.isActive('orderedList')}
        onClick={() => editor.chain().focus().toggleOrderedList().run()}
      >
        1. 2. 3.
      </ToolbarButton>
      <ToolbarButton
        active={editor.isActive('blockquote')}
        onClick={() => editor.chain().focus().toggleBlockquote().run()}
      >
        Citace
      </ToolbarButton>
      <ToolbarButton
        onClick={() => {
          const url = window.prompt('URL odkazu:')
          if (url) editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run()
        }}
      >
        Odkaz
      </ToolbarButton>
      <ToolbarButton onClick={onInsertImage}>Obrázek</ToolbarButton>
    </div>
  )
}

interface RichTextEditorProps {
  value: string
  onChange: (html: string) => void
}

/** WYSIWYG editor for Page.content / Article.full_text: bold/italic/lists/
 * quote, manual link insertion, image upload, and @-triggered mention
 * suggestions (from /api/admin/mentionable) that insert a plain link -
 * matching the spec's literal "typing @ triggers a menu to insert a link",
 * not a separate re-resolving mention-chip concept. */
export default function RichTextEditor({ value, onChange }: RichTextEditorProps) {
  const mentionableRef = useRef<MentionableItem[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    apiFetch('/api/admin/mentionable')
      .then((r) => (r.ok ? r.json() : []))
      .then((items: MentionableItem[]) => {
        mentionableRef.current = items
      })
      .catch(() => {})
  }, [])

  const editor = useEditor({
    extensions: [
      StarterKit,
      ImageExtension,
      LinkExtension.configure({ openOnClick: false, autolink: false }),
      MentionSuggestion.configure({ suggestion: createMentionSuggestion(() => mentionableRef.current) }),
    ],
    content: value,
    onUpdate: ({ editor }) => onChange(editor.getHTML()),
  })

  async function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file || !editor) return

    const formData = new FormData()
    formData.append('file', file)
    const resp = await apiFetch('/api/admin/uploads/image', { method: 'POST', body: formData })
    if (!resp.ok) return
    const { url } = await resp.json()
    editor.chain().focus().setImage({ src: url }).run()
  }

  if (!editor) return null

  return (
    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950">
      <Toolbar editor={editor} onInsertImage={() => fileInputRef.current?.click()} />
      <input ref={fileInputRef} type="file" accept="image/png,image/jpeg,image/webp,image/gif" className="hidden" onChange={handleFileChange} />
      <div className="rich-text-content px-3 py-2 text-slate-900 dark:text-slate-100">
        <EditorContent editor={editor} />
      </div>
    </div>
  )
}
