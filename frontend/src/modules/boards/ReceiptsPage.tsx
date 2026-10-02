/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../api/client'
import { useAuth } from '../../context/AuthContext'
import usePageMeta from '../../hooks/usePageMeta'
import { API_BASE, MY_POSTS_PATH, fetchJson, formatMoney, type Receipt } from './api'

/**
 * /receipts - the documents issued for the signed-in user's payments, each
 * with the confirmation it was emailed with. The document is the server's own
 * HTML (the very one in the email), shown in a sandboxed frame: it is data
 * built from outside input, and a frame with no permissions cannot run or
 * navigate anything. The newest is open by default.
 */
export default function ReceiptsPage() {
  const { t, i18n } = useTranslation('boards')
  const { user, loading } = useAuth()
  const [items, setItems] = useState<Receipt[] | null>(null)
  const [error, setError] = useState(false)
  const [selected, setSelected] = useState<string | null>(null)
  const [html, setHtml] = useState<string | null>(null)
  const [documentError, setDocumentError] = useState(false)
  const language = i18n.resolvedLanguage ?? i18n.language

  usePageMeta({ title: t('receipts.title') })

  useEffect(() => {
    if (loading || !user) return
    let cancelled = false
    fetchJson<Receipt[]>(`${API_BASE}/me/receipts`)
      .then((found) => {
        if (cancelled) return
        setItems(found)
        setSelected((current) => current ?? found[0]?.id ?? null)
      })
      .catch(() => !cancelled && setError(true))
    return () => {
      cancelled = true
    }
  }, [user, loading])

  useEffect(() => {
    if (!selected) {
      setHtml(null)
      return
    }
    let cancelled = false
    setDocumentError(false)
    apiFetch(`${API_BASE}/me/receipts/${selected}/document?language=${encodeURIComponent(language)}`)
      .then(async (resp) => {
        if (!resp.ok) throw new Error()
        const text = await resp.text()
        if (!cancelled) setHtml(text)
      })
      .catch(() => !cancelled && setDocumentError(true))
    return () => {
      cancelled = true
    }
  }, [selected, language])

  const current = items?.find((receipt) => receipt.id === selected)

  return (
    <div className="mx-auto max-w-3xl px-6 py-12 text-slate-900 dark:text-slate-100">
      <p className="mb-6 text-sm">
        <Link to={MY_POSTS_PATH} className="underline underline-offset-4 hover:no-underline">
          ← {t('myPosts.title')}
        </Link>
      </p>
      <h1 className="mb-6 text-3xl font-bold tracking-tight">{t('receipts.title')}</h1>

      {loading ? (
        <p className="text-slate-500 dark:text-slate-400">{t('common.loading')}</p>
      ) : !user ? (
        <p>
          <Link to="/login" className="font-medium underline underline-offset-4 hover:no-underline">
            {t('receipts.loginRequired')}
          </Link>
        </p>
      ) : (
        <>
          <p className="mb-6 text-sm text-slate-600 dark:text-slate-400">{t('receipts.explain')}</p>
          {error && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{t('receipts.error')}</p>}
          {items === null ? (
            !error && <p className="text-slate-500 dark:text-slate-400">{t('common.loading')}</p>
          ) : items.length === 0 ? (
            <p className="rounded-lg border border-dashed border-slate-300 p-8 text-center text-slate-500 dark:border-slate-700 dark:text-slate-400">
              {t('receipts.empty')}
            </p>
          ) : (
            <>
              <ul className="mb-6 divide-y divide-slate-200 border-y border-slate-200 dark:divide-slate-800 dark:border-slate-800">
                {items.map((receipt) => (
                  <li key={receipt.id} className="flex flex-wrap items-center justify-between gap-3 py-3 text-sm">
                    <div className="min-w-0">
                      <p className="font-bold">{receipt.number}</p>
                      <p className="break-words text-slate-600 dark:text-slate-400">
                        {new Date(receipt.issued_at).toLocaleDateString(language)} · {receipt.post_title} ·{' '}
                        {formatMoney(receipt.amount, receipt.currency, language)}
                      </p>
                      <p className="text-xs text-slate-500 dark:text-slate-400">
                        {receipt.emailed ? t('receipts.emailed') : t('receipts.notEmailed')}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setSelected(receipt.id)}
                      aria-pressed={receipt.id === selected}
                      className="rounded border border-slate-300 px-3 py-1 hover:bg-slate-100 aria-pressed:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800 dark:aria-pressed:bg-slate-800"
                    >
                      {t('receipts.show')}
                    </button>
                  </li>
                ))}
              </ul>

              {documentError && <p className="mb-4 text-sm text-red-600 dark:text-red-400">{t('receipts.documentError')}</p>}
              {html && current && (
                <iframe
                  title={t('receipts.frameTitle', { number: current.number })}
                  srcDoc={html}
                  sandbox=""
                  className="h-[34rem] w-full rounded-lg border border-slate-300 bg-white dark:border-slate-700"
                />
              )}
            </>
          )}
        </>
      )}
    </div>
  )
}
