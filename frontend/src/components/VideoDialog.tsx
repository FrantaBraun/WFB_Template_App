/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { parseVideoUrl } from './videoEmbed'

interface VideoDialogProps {
  /** Called with the canonical embed URL once the pasted link is a supported one. */
  onInsert: (src: string) => void
  onCancel: () => void
}

/** Asks for a YouTube or Vimeo link for the editor's Video button; anything else is refused with a hint. */
export default function VideoDialog({ onInsert, onCancel }: VideoDialogProps) {
  const { t } = useTranslation()
  const [url, setUrl] = useState('')
  const [invalid, setInvalid] = useState(false)

  function submit() {
    const src = parseVideoUrl(url)
    if (!src) {
      setInvalid(true)
      return
    }
    onInsert(src)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4" onClick={onCancel}>
      <div
        className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-4 shadow-xl dark:border-slate-800 dark:bg-slate-900"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="mb-3 text-sm font-semibold text-slate-900 dark:text-slate-100">{t('editor.videoDialogTitle')}</h3>
        <label htmlFor="video-url" className="mb-1 block text-xs text-slate-600 dark:text-slate-400">
          {t('editor.videoUrlLabel')}
        </label>
        <input
          id="video-url"
          type="url"
          autoFocus
          value={url}
          onChange={(e) => {
            setUrl(e.target.value)
            setInvalid(false)
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              submit()
            }
          }}
          className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
        />
        <p className={`mt-2 text-xs ${invalid ? 'text-red-600 dark:text-red-400' : 'text-slate-500 dark:text-slate-400'}`} role={invalid ? 'alert' : undefined}>
          {invalid ? t('editor.videoInvalid') : t('editor.videoHint')}
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <button type="button" onClick={onCancel} className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm dark:border-slate-800">
            {t('common.cancel')}
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={!url.trim()}
            className="rounded-lg bg-slate-900 px-3 py-1.5 text-sm font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
          >
            {t('editor.videoInsert')}
          </button>
        </div>
      </div>
    </div>
  )
}
