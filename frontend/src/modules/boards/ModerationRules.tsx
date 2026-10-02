/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { API_BASE, ApiError, fetchJson, sendJson, type RuleKeyword, type RulesResponse } from './api'

const field =
  'rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100'

/**
 * A category's machine rules, as an administrator reads and edits them: the
 * keywords posts are compared against, each with a weight, and free notes.
 * An empty list switches the topic check off for the category; "rebuild"
 * throws the rules away and builds them again from the title and description.
 */
export default function ModerationRules({ slug, onSlugChange }: { slug: string; onSlugChange: (slug: string) => void }) {
  const { t } = useTranslation('boards')
  const [input, setInput] = useState(slug)
  const [loaded, setLoaded] = useState<RulesResponse | null>(null)
  const [keywords, setKeywords] = useState<RuleKeyword[]>([])
  const [notes, setNotes] = useState('')
  const [state, setState] = useState<'idle' | 'loading' | 'notFound' | 'error'>('idle')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<{ ok: boolean; key: string } | null>(null)

  function show(response: RulesResponse) {
    setLoaded(response)
    setKeywords(response.rules.keywords)
    setNotes(response.rules.notes)
  }

  useEffect(() => {
    setInput(slug)
    setMessage(null)
    if (!slug) {
      setLoaded(null)
      setState('idle')
      return
    }
    let cancelled = false
    setState('loading')
    fetchJson<RulesResponse>(`${API_BASE}/manage/categories/${encodeURIComponent(slug)}/rules`)
      .then((response) => {
        if (cancelled) return
        show(response)
        setState('idle')
      })
      .catch((err) => {
        if (cancelled) return
        setLoaded(null)
        setState(err instanceof ApiError && err.status === 404 ? 'notFound' : 'error')
      })
    return () => {
      cancelled = true
    }
  }, [slug])

  async function act(action: () => Promise<RulesResponse>, doneKey: string) {
    setBusy(true)
    setMessage(null)
    try {
      show(await action())
      setMessage({ ok: true, key: doneKey })
    } catch (err) {
      setMessage({ ok: false, key: err instanceof ApiError && err.status === 422 ? 'admin.rules.invalid' : 'admin.error' })
    } finally {
      setBusy(false)
    }
  }

  const base = `${API_BASE}/manage/categories/${encodeURIComponent(slug)}/rules`

  function save(event: FormEvent) {
    event.preventDefault()
    const cleaned = keywords.filter((keyword) => keyword.term.trim() !== '')
    act(() => sendJson<RulesResponse>('PUT', base, { keywords: cleaned, notes }), 'admin.rules.saved')
  }

  function rebuild() {
    if (!window.confirm(t('admin.rules.confirmRebuild'))) return
    act(() => sendJson<RulesResponse>('POST', `${base}/rebuild`), 'admin.rules.rebuilt')
  }

  function updateKeyword(index: number, change: Partial<RuleKeyword>) {
    setKeywords((current) => current.map((keyword, i) => (i === index ? { ...keyword, ...change } : keyword)))
  }

  return (
    <div>
      <form
        onSubmit={(event) => {
          event.preventDefault()
          onSlugChange(input.trim())
        }}
        className="mb-6 flex flex-wrap items-end gap-3 text-sm"
      >
        <label className="flex flex-col gap-1">
          {t('admin.rules.category')}
          <input value={input} onChange={(e) => setInput(e.target.value)} className={`${field} w-64`} />
        </label>
        <button type="submit" className="rounded-lg bg-slate-900 px-4 py-1.5 font-medium text-slate-100 dark:bg-slate-100 dark:text-slate-900">
          {t('admin.rules.load')}
        </button>
      </form>

      {state === 'loading' && <p className="text-slate-500 dark:text-slate-400">{t('common.loading')}</p>}
      {state === 'notFound' && <p>{t('category.notFound')}</p>}
      {state === 'error' && <p className="text-red-600 dark:text-red-400">{t('admin.error')}</p>}
      {state === 'idle' && !slug && <p className="text-slate-500 dark:text-slate-400">{t('admin.rules.pick')}</p>}

      {loaded && (
        <form onSubmit={save} className="space-y-4 text-sm">
          <p className="text-slate-600 dark:text-slate-400">
            {t('admin.rules.source', { source: loaded.source ? t(`admin.rules.sources.${loaded.source}`, { defaultValue: loaded.source }) : t('admin.rules.none') })}
            {loaded.updated_at && <> · {new Date(loaded.updated_at).toLocaleString()}</>}
          </p>
          <p className="text-slate-600 dark:text-slate-400">{t('admin.rules.explain')}</p>

          {keywords.length === 0 ? (
            <p className="rounded-lg border border-dashed border-slate-300 p-4 text-slate-500 dark:border-slate-700 dark:text-slate-400">
              {t('admin.rules.empty')}
            </p>
          ) : (
            <ul className="space-y-2">
              {keywords.map((keyword, index) => (
                <li key={index} className="flex flex-wrap items-center gap-2">
                  <input
                    aria-label={t('admin.rules.term')}
                    value={keyword.term}
                    maxLength={60}
                    onChange={(e) => updateKeyword(index, { term: e.target.value })}
                    className={`${field} w-56`}
                  />
                  <input
                    aria-label={t('admin.rules.weight')}
                    type="number"
                    min={0.1}
                    max={10}
                    step={0.1}
                    value={keyword.weight}
                    onChange={(e) => updateKeyword(index, { weight: Number(e.target.value) })}
                    className={`${field} w-24`}
                  />
                  <button
                    type="button"
                    onClick={() => setKeywords((current) => current.filter((_, i) => i !== index))}
                    className="rounded border border-slate-300 px-2 py-1 hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
                  >
                    {t('admin.rules.remove')}
                  </button>
                </li>
              ))}
            </ul>
          )}

          <button
            type="button"
            onClick={() => setKeywords((current) => [...current, { term: '', weight: 1 }])}
            className="underline underline-offset-4 hover:no-underline"
          >
            {t('admin.rules.add')}
          </button>

          <div>
            <label htmlFor="rules-notes" className="mb-1 block font-medium">
              {t('admin.rules.notes')}
            </label>
            <textarea id="rules-notes" rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} className={`${field} w-full`} />
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="submit"
              disabled={busy}
              className="rounded-lg bg-slate-900 px-4 py-1.5 font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
            >
              {t('admin.rules.save')}
            </button>
            <button
              type="button"
              onClick={rebuild}
              disabled={busy}
              className="rounded-lg border border-slate-300 px-4 py-1.5 hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:hover:bg-slate-800"
            >
              {t('admin.rules.rebuild')}
            </button>
            {message && (
              <span role={message.ok ? 'status' : 'alert'} className={message.ok ? '' : 'text-red-600 dark:text-red-400'}>
                {t(message.key)}
              </span>
            )}
          </div>
        </form>
      )}
    </div>
  )
}
