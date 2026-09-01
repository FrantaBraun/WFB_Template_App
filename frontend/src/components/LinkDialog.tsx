/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useState } from 'react'
import { useTranslation } from 'react-i18next'

interface LinkDialogProps {
  initialText: string
  initialUrl: string
  isEditing: boolean
  onSave: (text: string, url: string) => void
  onRemove: () => void
  onCancel: () => void
}

/** Shared by the toolbar's manual "Link" button and by clicking into any
 * existing link (including one inserted via @-mention) - both let the admin
 * change the displayed text and the URL in one dialog, replacing the old
 * window.prompt(url-only) flow. */
export default function LinkDialog({ initialText, initialUrl, isEditing, onSave, onRemove, onCancel }: LinkDialogProps) {
  const { t } = useTranslation()
  const [text, setText] = useState(initialText)
  const [url, setUrl] = useState(initialUrl)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" onClick={onCancel}>
      <div
        className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-4 shadow-xl dark:border-slate-800 dark:bg-slate-900"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="mb-3 text-sm font-semibold text-slate-900 dark:text-slate-100">{t('editor.linkDialogTitle')}</h3>

        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs text-slate-600 dark:text-slate-400">{t('editor.linkTextLabel')}</label>
            <input
              type="text"
              autoFocus
              value={text}
              onChange={(e) => setText(e.target.value)}
              className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-600 dark:text-slate-400">{t('editor.linkUrlLabel')}</label>
            <input
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
            />
          </div>
        </div>

        <div className="mt-4 flex items-center justify-between">
          <div>
            {isEditing && (
              <button type="button" onClick={onRemove} className="text-sm text-red-600 dark:text-red-400">
                {t('editor.linkRemove')}
              </button>
            )}
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onCancel}
              className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm dark:border-slate-800"
            >
              {t('common.cancel')}
            </button>
            <button
              type="button"
              onClick={() => onSave(text, url)}
              disabled={!url.trim()}
              className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
            >
              {t('common.save')}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
