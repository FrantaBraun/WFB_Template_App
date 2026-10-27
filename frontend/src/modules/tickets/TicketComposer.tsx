/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useMemo, useRef, useState, type ChangeEvent, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import RichTextEditor from '../../components/RichTextEditor'
import {
  API_BASE,
  MAX_ATTACHMENTS_PER_ENTRY,
  MAX_ATTACHMENT_BYTES,
  deleteRequest,
  formatFileSize,
  parseMinutes,
  sendJson,
  uploadAttachment,
  uploadTicketImage,
  type Attachment,
  type Entry,
  type TicketDetail,
} from './api'
import { cardClass, inputClass, labelClass, primaryButtonClass, secondaryButtonClass, useErrorText } from './ui'

type Mode = 'note' | 'outgoing'

/**
 * The form under a ticket's thread: an internal note or a mail to the
 * requester, written in the shared rich-text editor (with pictures), with
 * files attached and the time spent on it. Files are uploaded as they are
 * chosen (and can be taken back until the entry is sent), because an entry
 * names them by id.
 */
export default function TicketComposer({ ticket, onAdded }: { ticket: TicketDetail; onAdded: () => void }) {
  const { t, i18n } = useTranslation('tickets')
  const errorText = useErrorText()
  const fileInput = useRef<HTMLInputElement>(null)
  const [mode, setMode] = useState<Mode>('note')
  const [html, setHtml] = useState('')
  // TipTap takes its content only when it is created: a new key makes a blank editor.
  const [editorKey, setEditorKey] = useState(0)
  const [attachments, setAttachments] = useState<Attachment[]>([])
  const [uploading, setUploading] = useState(false)
  const [minutesText, setMinutesText] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const uploadImage = useMemo(() => uploadTicketImage(ticket.number), [ticket.number])
  const canEmail = Boolean(ticket.requester_email)

  async function handleFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? [])
    event.target.value = ''
    setError(null)
    setUploading(true)
    try {
      let count = attachments.length
      for (const file of files) {
        if (count >= MAX_ATTACHMENTS_PER_ENTRY) {
          setError(t('composer.tooManyFiles', { count: MAX_ATTACHMENTS_PER_ENTRY }))
          break
        }
        if (file.size > MAX_ATTACHMENT_BYTES) {
          setError(t('errors.tooLarge'))
          continue
        }
        const uploaded = await uploadAttachment(ticket.number, file)
        setAttachments((current) => [...current, uploaded])
        count += 1
      }
    } catch (e) {
      setError(errorText(e, 'composer.uploadError'))
    } finally {
      setUploading(false)
    }
  }

  async function removeAttachment(attachment: Attachment) {
    setError(null)
    try {
      await deleteRequest(`${API_BASE}/${ticket.number}/attachments/${attachment.id}`)
      setAttachments((current) => current.filter((item) => item.id !== attachment.id))
    } catch (e) {
      setError(errorText(e, 'composer.removeError'))
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const minutes = parseMinutes(minutesText)
    if (minutes === null) {
      setError(t('composer.invalidTime'))
      return
    }
    setSending(true)
    setError(null)
    try {
      await sendJson<Entry>(`${API_BASE}/${ticket.number}/entries`, 'POST', {
        kind: mode,
        content_html: html,
        minutes,
        attachment_ids: attachments.map((item) => item.id),
      })
      setHtml('')
      setEditorKey((key) => key + 1)
      setAttachments([])
      setMinutesText('')
      onAdded()
    } catch (e) {
      // Everything typed stays, so a failed mail can simply be sent again.
      setError(errorText(e, 'composer.sendError'))
    } finally {
      setSending(false)
    }
  }

  const tabClass = (active: boolean) =>
    `rounded-t-lg px-4 py-2 text-sm font-medium ${
      active
        ? 'bg-white text-slate-900 dark:bg-slate-900 dark:text-slate-100'
        : 'text-slate-500 hover:text-slate-900 disabled:opacity-50 dark:text-slate-400 dark:hover:text-slate-100'
    }`

  return (
    <section aria-label={t('composer.title')}>
      <div role="tablist" className="flex gap-1 border-b border-slate-200 dark:border-slate-800">
        <button type="button" role="tab" aria-selected={mode === 'note'} onClick={() => setMode('note')} className={tabClass(mode === 'note')}>
          {t('composer.note')}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mode === 'outgoing'}
          disabled={!canEmail}
          title={canEmail ? undefined : t('composer.noRequesterEmail')}
          onClick={() => setMode('outgoing')}
          className={tabClass(mode === 'outgoing')}
        >
          {t('composer.reply')}
        </button>
      </div>

      <form onSubmit={handleSubmit} className={`${cardClass} space-y-4 rounded-t-none p-5`}>
        {mode === 'outgoing' ? (
          <p className="text-sm text-slate-600 dark:text-slate-400">{t('composer.replyHint', { address: ticket.requester_email ?? '' })}</p>
        ) : (
          <p className="text-sm text-slate-600 dark:text-slate-400">{t('composer.noteHint')}</p>
        )}

        <RichTextEditor key={editorKey} value={html} onChange={setHtml} uploadImage={uploadImage} />

        <div>
          <div className="flex flex-wrap items-center gap-3">
            <input ref={fileInput} type="file" multiple className="hidden" onChange={handleFiles} aria-label={t('composer.attach')} />
            <button type="button" onClick={() => fileInput.current?.click()} disabled={uploading} className={secondaryButtonClass}>
              {uploading ? t('composer.uploading') : t('composer.attach')}
            </button>
            <span className="text-sm text-slate-500 dark:text-slate-400">{t('composer.attachHint')}</span>
          </div>
          {attachments.length > 0 && (
            <ul className="mt-3 flex flex-wrap gap-2">
              {attachments.map((item) => (
                <li key={item.id} className="flex items-center gap-2 rounded-full border border-slate-200 px-3 py-1 text-sm dark:border-slate-700">
                  <span className="max-w-[16rem] truncate">{item.original_filename}</span>
                  <span className="text-slate-500 dark:text-slate-400">{formatFileSize(item.size_bytes, i18n.language)}</span>
                  <button
                    type="button"
                    onClick={() => removeAttachment(item)}
                    aria-label={t('composer.removeFile', { name: item.original_filename })}
                    className="text-slate-500 hover:text-red-600 dark:text-slate-400 dark:hover:text-red-400"
                  >
                    ✕
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="flex flex-wrap items-end gap-4">
          <div className="w-40">
            <label htmlFor="entry-time" className={labelClass}>{t('composer.time')}</label>
            <input
              id="entry-time"
              value={minutesText}
              onChange={(e) => setMinutesText(e.target.value)}
              placeholder={t('composer.timePlaceholder')}
              inputMode="text"
              className={inputClass}
            />
          </div>
          <button type="submit" disabled={sending || uploading} className={primaryButtonClass}>
            {sending ? t('composer.sending') : t(mode === 'outgoing' ? 'composer.send' : 'composer.add')}
          </button>
        </div>
        <p className="text-sm text-slate-500 dark:text-slate-400">{t('composer.timeHint')}</p>

        {error && <p role="alert" className="text-sm text-red-600 dark:text-red-400">{error}</p>}
      </form>
    </section>
  )
}
