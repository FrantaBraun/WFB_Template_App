/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import {
  API_BASE,
  MAX_INVOICE_BYTES,
  deleteRequest,
  downloadInvoice,
  errorStatus,
  fetchJson,
  formatDate,
  formatFileSize,
  type Invoice,
} from './api'
import { cardClass, dangerButtonClass, inputClass, labelClass, primaryButtonClass, secondaryButtonClass } from './ui'

/** The invoices of one task: download, delete and upload (PDF only). `onChange` asks the page to reload. */
export default function InvoiceList({ taskId, invoices, onChange }: { taskId: string; invoices: Invoice[]; onChange: () => void }) {
  const { t, i18n } = useTranslation('crm')
  const fileRef = useRef<HTMLInputElement>(null)
  const [number, setNumber] = useState('')
  const [chosen, setChosen] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleUpload(e: FormEvent) {
    e.preventDefault()
    if (!chosen) return
    // The backend checks all of this again (it is the authority); this just
    // answers right away instead of after sending a doomed file.
    if (chosen.type !== 'application/pdf') return setError(t('invoices.errors.type'))
    if (chosen.size > MAX_INVOICE_BYTES) return setError(t('invoices.errors.size'))
    setUploading(true)
    setError(null)
    try {
      const form = new FormData()
      form.append('file', chosen)
      if (number.trim()) form.append('number', number.trim())
      await fetchJson<Invoice>(`${API_BASE}/tasks/${taskId}/invoices`, { method: 'POST', body: form })
      setChosen(null)
      setNumber('')
      if (fileRef.current) fileRef.current.value = ''
      onChange()
    } catch (err) {
      const status = errorStatus(err)
      setError(t(status === 415 ? 'invoices.errors.type' : status === 413 ? 'invoices.errors.size' : status === 422 ? 'invoices.errors.invalid' : 'invoices.errors.upload'))
    } finally {
      setUploading(false)
    }
  }

  async function handleDownload(invoice: Invoice) {
    setError(null)
    try {
      await downloadInvoice(invoice)
    } catch {
      setError(t('invoices.errors.download'))
    }
  }

  async function handleDelete(invoice: Invoice) {
    if (!window.confirm(t('invoices.confirmDelete', { name: invoice.original_filename }))) return
    setError(null)
    try {
      await deleteRequest(`${API_BASE}/invoices/${invoice.id}`)
      onChange()
    } catch {
      setError(t('invoices.errors.delete'))
    }
  }

  return (
    <section>
      <h2 className="mb-3 text-xl font-semibold tracking-tight">{t('invoices.title')}</h2>

      {invoices.length === 0 ? (
        <p className="text-slate-500 dark:text-slate-400">{t('invoices.empty')}</p>
      ) : (
        <ul className={`${cardClass} divide-y divide-slate-200 overflow-hidden dark:divide-slate-800`}>
          {invoices.map((invoice) => (
            <li key={invoice.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
              <span className="min-w-0 flex-1">
                <span className="block truncate font-medium">
                  {invoice.number ? `${t('invoices.numberShort', { number: invoice.number })} · ` : ''}
                  {invoice.original_filename}
                </span>
                <span className="block text-sm text-slate-500 dark:text-slate-400">
                  {formatFileSize(invoice.size_bytes, i18n.language)} · {t('invoices.uploadedOn', { date: formatDate(invoice.uploaded_at, i18n.language) })}
                </span>
              </span>
              <span className="flex gap-2">
                <button type="button" onClick={() => handleDownload(invoice)} className={secondaryButtonClass}>{t('invoices.download')}</button>
                <button type="button" onClick={() => handleDelete(invoice)} className={dangerButtonClass}>{t('common.delete')}</button>
              </span>
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={handleUpload} className={`${cardClass} mt-4 space-y-3 p-4`}>
        <h3 className="font-medium">{t('invoices.uploadTitle')}</h3>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label htmlFor="crm-invoice-file" className={labelClass}>{t('invoices.file')}</label>
            <input
              id="crm-invoice-file"
              ref={fileRef}
              type="file"
              accept="application/pdf,.pdf"
              required
              onChange={(e) => {
                setChosen(e.target.files?.[0] ?? null)
                setError(null)
              }}
              className="block w-full text-sm text-slate-600 file:me-3 file:rounded-lg file:border-0 file:bg-slate-200 file:px-3 file:py-2 file:text-slate-800 dark:text-slate-300 dark:file:bg-slate-800 dark:file:text-slate-200"
            />
          </div>
          <div>
            <label htmlFor="crm-invoice-number" className={labelClass}>{t('invoices.number')}</label>
            <input id="crm-invoice-number" maxLength={50} value={number} onChange={(e) => setNumber(e.target.value)} className={inputClass} />
          </div>
        </div>
        <p className="text-xs text-slate-500 dark:text-slate-400">{t('invoices.hint')}</p>
        {error && <p role="alert" className="text-sm text-red-600 dark:text-red-400">{error}</p>}
        <button type="submit" disabled={uploading || !chosen} className={primaryButtonClass}>
          {t(uploading ? 'invoices.uploading' : 'invoices.upload')}
        </button>
      </form>
    </section>
  )
}
