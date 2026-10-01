/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { Extension } from '@tiptap/core'
import ColorExtension from '@tiptap/extension-color'
import FontFamilyExtension from '@tiptap/extension-font-family'
import ImageExtension from '@tiptap/extension-image'
import { FontSize, TextStyle as TextStyleExtension } from '@tiptap/extension-text-style'
import { EditorContent, ReactRenderer, useEditor, type Editor } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Suggestion, { type SuggestionOptions } from '@tiptap/suggestion'
import { useEffect, useRef, useState, type ChangeEvent } from 'react'
import { useTranslation } from 'react-i18next'
import tippy, { type Instance as TippyInstance } from 'tippy.js'
import LinkDialog from './LinkDialog'
import MentionList from './MentionList'

/** One @-mention target: inserted as a plain link to `url` labelled `label`. */
export interface MentionableItem {
  id: string
  label: string
  url: string
  /** Short type tag shown in the suggestion list (e.g. "Pg", "Ev"). */
  typeLabel?: string
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
          { type: 'text', text: item.label, marks: [{ type: 'link', attrs: { href: item.url } }] },
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

const FONT_SIZES = ['12px', '14px', '18px', '24px', '32px']
const FONT_FAMILIES = [
  { label: 'Arial', value: 'Arial, sans-serif' },
  { label: 'Georgia', value: 'Georgia, serif' },
  { label: 'Courier New', value: "'Courier New', monospace" },
  { label: 'Times New Roman', value: "'Times New Roman', serif" },
]
const HEADING_LEVELS = [1, 2, 3, 4, 5] as const

function ToolbarButton({
  active,
  onClick,
  title,
  children,
}: {
  active?: boolean
  onClick: () => void
  title?: string
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
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

function Toolbar({ editor, onInsertImage, onOpenLinkDialog }: { editor: Editor; onInsertImage?: () => void; onOpenLinkDialog: () => void }) {
  const { t } = useTranslation()
  const activeHeadingLevel = HEADING_LEVELS.find((level) => editor.isActive('heading', { level })) ?? 'p'

  return (
    <div className="flex flex-wrap items-center gap-1 border-b border-slate-200 p-2 dark:border-slate-800">
      <select
        value={activeHeadingLevel}
        onChange={(e) => {
          const value = e.target.value
          if (value === 'p') editor.chain().focus().setParagraph().run()
          else editor.chain().focus().setHeading({ level: Number(value) as (typeof HEADING_LEVELS)[number] }).run()
        }}
        className="rounded border border-slate-200 bg-white px-1 py-1 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300"
      >
        <option value="p">{t('editor.paragraph')}</option>
        {HEADING_LEVELS.map((level) => (
          <option key={level} value={level}>
            {t('editor.heading', { level })}
          </option>
        ))}
      </select>

      <ToolbarButton active={editor.isActive('bold')} onClick={() => editor.chain().focus().toggleBold().run()} title={t('editor.bold')}>
        <span className="font-bold">B</span>
      </ToolbarButton>
      <ToolbarButton active={editor.isActive('italic')} onClick={() => editor.chain().focus().toggleItalic().run()} title={t('editor.italic')}>
        <span className="italic">I</span>
      </ToolbarButton>
      <ToolbarButton active={editor.isActive('underline')} onClick={() => editor.chain().focus().toggleUnderline().run()} title={t('editor.underline')}>
        <span className="underline">U</span>
      </ToolbarButton>
      <ToolbarButton active={editor.isActive('strike')} onClick={() => editor.chain().focus().toggleStrike().run()} title={t('editor.strike')}>
        <span className="line-through">S</span>
      </ToolbarButton>
      <ToolbarButton active={editor.isActive('bulletList')} onClick={() => editor.chain().focus().toggleBulletList().run()}>
        {t('editor.list')}
      </ToolbarButton>
      <ToolbarButton active={editor.isActive('orderedList')} onClick={() => editor.chain().focus().toggleOrderedList().run()}>
        1. 2. 3.
      </ToolbarButton>
      <ToolbarButton active={editor.isActive('blockquote')} onClick={() => editor.chain().focus().toggleBlockquote().run()}>
        {t('editor.quote')}
      </ToolbarButton>

      <select
        value={editor.getAttributes('textStyle').fontFamily ?? ''}
        onChange={(e) => {
          const value = e.target.value
          if (value) editor.chain().focus().setFontFamily(value).run()
          else editor.chain().focus().unsetFontFamily().run()
        }}
        className="rounded border border-slate-200 bg-white px-1 py-1 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300"
      >
        <option value="">{t('editor.fontFamilyDefault')}</option>
        {FONT_FAMILIES.map((font) => (
          <option key={font.value} value={font.value}>
            {font.label}
          </option>
        ))}
      </select>

      <select
        value={editor.getAttributes('textStyle').fontSize ?? ''}
        onChange={(e) => {
          const value = e.target.value
          if (value) editor.chain().focus().setFontSize(value).run()
          else editor.chain().focus().unsetFontSize().run()
        }}
        className="rounded border border-slate-200 bg-white px-1 py-1 text-sm text-slate-700 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300"
      >
        <option value="">{t('editor.fontSizeDefault')}</option>
        {FONT_SIZES.map((size) => (
          <option key={size} value={size}>
            {size}
          </option>
        ))}
      </select>

      <input
        type="color"
        title={t('editor.textColor')}
        value={editor.getAttributes('textStyle').color ?? '#000000'}
        onChange={(e) => editor.chain().focus().setColor(e.target.value).run()}
        className="h-7 w-7 cursor-pointer rounded border border-slate-200 dark:border-slate-800"
      />

      <ToolbarButton onClick={onOpenLinkDialog}>{t('editor.link')}</ToolbarButton>
      {onInsertImage && <ToolbarButton onClick={onInsertImage}>{t('editor.image')}</ToolbarButton>}
    </div>
  )
}

interface RichTextEditorProps {
  value: string
  onChange: (html: string) => void
  /** Loads the @-mention targets once on mount; without it, typing @ does nothing special. */
  loadMentionables?: () => Promise<MentionableItem[]>
  /** Uploads an image and resolves to its public URL; without it, the toolbar has no Image button. */
  uploadImage?: (file: File) => Promise<string>
}

interface LinkDialogState {
  isEditing: boolean
  initialText: string
  initialUrl: string
}

/** Shared WYSIWYG HTML editor: headings 1-5, bold/italic/underline/strike,
 * font size/family/color, lists/quote, a link dialog (text + URL, for both
 * inserting and editing - including a link inserted via @-mention), image
 * upload (when `uploadImage` is given) and @-triggered suggestions (when
 * `loadMentionables` is given) that insert a plain link. Its output must
 * stay within what the backend's app/services/sanitize.py allows - keep
 * the two in sync when adding an extension. */
export default function RichTextEditor({ value, onChange, loadMentionables, uploadImage }: RichTextEditorProps) {
  const mentionableRef = useRef<MentionableItem[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [linkDialog, setLinkDialog] = useState<LinkDialogState | null>(null)

  useEffect(() => {
    if (!loadMentionables) return
    loadMentionables()
      .then((items) => {
        mentionableRef.current = items
      })
      .catch(() => {})
    // Mount-only on purpose: callers usually pass an inline function.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        link: { openOnClick: false, autolink: false },
        heading: { levels: [...HEADING_LEVELS] },
      }),
      ImageExtension,
      TextStyleExtension,
      ColorExtension,
      FontFamilyExtension,
      FontSize,
      MentionSuggestion.configure({ suggestion: createMentionSuggestion(() => mentionableRef.current) }),
    ],
    content: value,
    onUpdate: ({ editor }) => onChange(editor.getHTML()),
  })

  async function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file || !editor || !uploadImage) return
    try {
      const url = await uploadImage(file)
      editor.chain().focus().setImage({ src: url }).run()
    } catch {
      // The upload helper owns error reporting; the editor just doesn't insert.
    }
  }

  function openLinkDialog() {
    if (!editor) return
    if (editor.isActive('link')) {
      // Selects the full extent of the link mark at the cursor so both the
      // text-replace-on-save below and the initial text read here cover the
      // whole link, not just the character the cursor happens to sit on.
      editor.chain().extendMarkRange('link').run()
      const { from, to } = editor.state.selection
      setLinkDialog({
        isEditing: true,
        initialText: editor.state.doc.textBetween(from, to, ' '),
        initialUrl: (editor.getAttributes('link').href as string) || '',
      })
    } else {
      const { from, to } = editor.state.selection
      setLinkDialog({ isEditing: false, initialText: editor.state.doc.textBetween(from, to, ' '), initialUrl: '' })
    }
  }

  function handleLinkSave(text: string, url: string) {
    if (!editor) return
    const displayText = text.trim() || url
    if (linkDialog?.isEditing) {
      // Selection is still the extended link range from openLinkDialog().
      editor.chain().focus().insertContent([{ type: 'text', text: displayText, marks: [{ type: 'link', attrs: { href: url } }] }]).run()
    } else {
      const { from, to } = editor.state.selection
      const content = [
        { type: 'text', text: displayText, marks: [{ type: 'link', attrs: { href: url } }] },
        { type: 'text', text: ' ' },
      ]
      if (from === to) editor.chain().focus().insertContent(content).run()
      else editor.chain().focus().deleteSelection().insertContent(content).run()
    }
    setLinkDialog(null)
  }

  function handleLinkRemove() {
    editor?.chain().focus().extendMarkRange('link').unsetLink().run()
    setLinkDialog(null)
  }

  if (!editor) return null

  return (
    <div className="overflow-hidden rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950">
      <Toolbar editor={editor} onInsertImage={uploadImage ? () => fileInputRef.current?.click() : undefined} onOpenLinkDialog={openLinkDialog} />
      <input ref={fileInputRef} type="file" accept="image/png,image/jpeg,image/webp,image/gif" className="hidden" onChange={handleFileChange} />
      <div className="rich-text-content px-3 py-2 text-slate-900 dark:text-slate-100">
        <EditorContent editor={editor} />
      </div>
      {linkDialog && (
        <LinkDialog
          isEditing={linkDialog.isEditing}
          initialText={linkDialog.initialText}
          initialUrl={linkDialog.initialUrl}
          onSave={handleLinkSave}
          onRemove={handleLinkRemove}
          onCancel={() => setLinkDialog(null)}
        />
      )}
    </div>
  )
}
