/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import RichTextEditor from '../../components/RichTextEditor'
import {
  API_BASE,
  deleteRequest,
  downloadAttachment,
  formatDateTime,
  formatFileSize,
  parseMinutes,
  sendJson,
  uploadTicketImage,
  type Attachment,
  type Entry,
  type EntryKind,
} from './api'
import { dangerButtonClass, inputClass, labelClass, primaryButtonClass, secondaryButtonClass, useErrorText, useMinutesLabel } from './ui'

const KIND_STYLES: Record<EntryKind, string> = {
  note: 'border-amber-200 bg-amber-50 dark:border-amber-900/60 dark:bg-amber-950/30',
  incoming: 'border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900',
  outgoing: 'border-sky-200 bg-sky-50 dark:border-sky-900/60 dark:bg-sky-950/30',
}

function AttachmentList({ attachments }: { attachments: Attachment[] }) {
  const { t, i18n } = useTranslation('tickets')
  const errorText = useErrorText()
  const [error, setError] = useState<string | null>(null)

  async function open(attachment: Attachment) {
    setError(null)
    try {
      await downloadAttachment(attachment)
    } catch (e) {
      setError(errorText(e, 'entry.downloadError'))
    }
  }

  if (attachments.length === 0) return null
  return (
    <div className="mt-3">
      <ul className="flex flex-wrap gap-2">
        {attachments.map((item) => (
          <li key={item.id}>
            <button
              type="button"
              onClick={() => open(item)}
              title={t('entry.download')}
              className="flex items-center gap-2 rounded-full border border-slate-200 px-3 py-1 text-sm hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
            >
              <span aria-hidden="true">📎</span>
              <span className="max-w-[16rem] truncate">{item.original_filename}</span>
              <span className="text-slate-500 dark:text-slate-400">{formatFileSize(item.size_bytes, i18n.language)}</span>
            </button>
          </li>
        ))}
      </ul>
      {error && <p role="alert" className="mt-1 text-sm text-red-600 dark:text-red-400">{error}</p>}
    </div>
  )
}

/**
 * One item of the thread. A note can be corrected and deleted; a mail we sent
 * or received stays as it was (it is a record of what was said) and only its
 * time can be changed. The HTML is sanitized by the backend on every write.
 */
export default function EntryView({ ticketNumber, entry, onChanged }: { ticketNumber: number; entry: Entry; onChanged: () => void }) {
  const { t, i18n } = useTranslation('tickets')
  const errorText = useErrorText()
  const minutesLabel = useMinutesLabel()
  const [editing, setEditing] = useState(false)
  const [html, setHtml] = useState(entry.content_html)
  const [minutesText, setMinutesText] = useState(String(entry.minutes))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const isNote = entry.kind === 'note'

  const who =
    entry.kind === 'incoming'
      ? [entry.from_name, entry.from_address ? `<${entry.from_address}>` : null].filter(Boolean).join(' ')
      : entry.kind === 'outgoing'
        ? t('entry.sentTo', { address: entry.to_address ?? '', author: entry.author_label ?? '' })
        : (entry.author_label ?? '')

  async function save(event: FormEvent) {
    event.preventDefault()
    const minutes = parseMinutes(minutesText)
    if (minutes === null) {
      setError(t('composer.invalidTime'))
      return
    }
    setSaving(true)
    setError(null)
    try {
      await sendJson<Entry>(`${API_BASE}/${ticketNumber}/entries/${entry.id}`, 'PATCH', isNote ? { content_html: html, minutes } : { minutes })
      setEditing(false)
      onChanged()
    } catch (e) {
      setError(errorText(e, 'entry.saveError'))
    } finally {
      setSaving(false)
    }
  }

  async function remove() {
    if (!window.confirm(t('entry.confirmDelete'))) return
    setError(null)
    try {
      await deleteRequest(`${API_BASE}/${ticketNumber}/entries/${entry.id}`)
      onChanged()
    } catch (e) {
      setError(errorText(e, 'entry.deleteError'))
    }
  }

  function startEditing() {
    setHtml(entry.content_html)
    setMinutesText(String(entry.minutes))
    setError(null)
    setEditing(true)
  }

  return (
    <article className={`rounded-2xl border p-5 ${KIND_STYLES[entry.kind]}`}>
      <header className="mb-3 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <div className="min-w-0">
          <span className="text-sm font-semibold">{t(`entry.kind.${entry.kind}`)}</span>
          {who && <span className="ms-2 break-all text-sm text-slate-600 dark:text-slate-400">{who}</span>}
        </div>
        <div className="flex flex-wrap items-center gap-x-3 text-sm text-slate-500 dark:text-slate-400">
          {entry.minutes > 0 && (
            <span className="rounded-full bg-white/70 px-2 py-0.5 font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-200" title={t('entry.timeSpent')}>
              ⏱ {minutesLabel(entry.minutes)}
            </span>
          )}
          <time dateTime={entry.created_at}>{formatDateTime(entry.created_at, i18n.language)}</time>
        </div>
      </header>

      {entry.email_subject && entry.kind !== 'note' && (
        <p className="mb-2 break-words text-sm text-slate-500 dark:text-slate-400">{entry.email_subject}</p>
      )}

      {editing ? (
        <form onSubmit={save} className="space-y-4">
          {isNote && <RichTextEditor value={html} onChange={setHtml} uploadImage={uploadTicketImage(ticketNumber)} />}
          <div className="w-40">
            <label htmlFor={`time-${entry.id}`} className={labelClass}>{t('composer.time')}</label>
            <input id={`time-${entry.id}`} value={minutesText} onChange={(e) => setMinutesText(e.target.value)} className={inputClass} />
          </div>
          <div className="flex gap-2">
            <button type="submit" disabled={saving} className={primaryButtonClass}>{saving ? t('common.saving') : t('common.save')}</button>
            <button type="button" onClick={() => setEditing(false)} className={secondaryButtonClass}>{t('common.cancel')}</button>
          </div>
        </form>
      ) : (
        <>
          {/* Sanitized by the backend (app.services.sanitize) before it was ever stored. */}
          <div className="rich-text-content break-words" dangerouslySetInnerHTML={{ __html: entry.content_html }} />
          <AttachmentList attachments={entry.attachments} />
          <div className="mt-3 flex gap-2">
            <button type="button" onClick={startEditing} className={secondaryButtonClass}>{isNote ? t('common.edit') : t('entry.editTime')}</button>
            {isNote && <button type="button" onClick={remove} className={dangerButtonClass}>{t('common.delete')}</button>}
          </div>
        </>
      )}

      {error && <p role="alert" className="mt-2 text-sm text-red-600 dark:text-red-400">{error}</p>}
    </article>
  )
}
