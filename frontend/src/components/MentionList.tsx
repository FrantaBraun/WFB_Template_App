/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { forwardRef, useEffect, useImperativeHandle, useState } from 'react'
import type { MentionableItem } from './RichTextEditor'

interface MentionListProps {
  items: MentionableItem[]
  command: (item: MentionableItem) => void
}

export interface MentionListHandle {
  onKeyDown: (props: { event: KeyboardEvent }) => boolean
}

/** The @-mention suggestion popup rendered by RichTextEditor's Suggestion
 * extension via tippy.js. Exposes onKeyDown via ref so the extension's
 * render() can forward arrow/enter/escape key handling into this list -
 * Tiptap's own suggestion popups all follow this imperative-handle shape. */
const MentionList = forwardRef<MentionListHandle, MentionListProps>(({ items, command }, ref) => {
  const [selectedIndex, setSelectedIndex] = useState(0)

  useEffect(() => setSelectedIndex(0), [items])

  const selectItem = (index: number) => {
    const item = items[index]
    if (item) command(item)
  }

  useImperativeHandle(ref, () => ({
    onKeyDown: ({ event }) => {
      if (event.key === 'ArrowUp') {
        setSelectedIndex((selectedIndex + items.length - 1) % items.length)
        return true
      }
      if (event.key === 'ArrowDown') {
        setSelectedIndex((selectedIndex + 1) % items.length)
        return true
      }
      if (event.key === 'Enter') {
        selectItem(selectedIndex)
        return true
      }
      return false
    },
  }))

  if (items.length === 0) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-500 shadow-lg dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400">
        Žádné výsledky
      </div>
    )
  }

  return (
    <div className="max-h-64 w-64 overflow-y-auto rounded-lg border border-slate-200 bg-white p-1 shadow-lg dark:border-slate-700 dark:bg-slate-800">
      {items.map((item, index) => (
        <button
          key={`${item.type}-${item.id}`}
          type="button"
          onClick={() => selectItem(index)}
          className={`flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm ${
            index === selectedIndex ? 'bg-slate-100 dark:bg-slate-700' : ''
          }`}
        >
          <span className="w-6 shrink-0 text-xs uppercase text-slate-400">
            {item.type === 'page' ? 'Str' : 'Čl'}
          </span>
          <span className="truncate text-slate-900 dark:text-slate-100">{item.label}</span>
        </button>
      ))}
    </div>
  )
})

MentionList.displayName = 'MentionList'

export default MentionList
