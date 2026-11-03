/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../api/client'
import ListSearch from '../components/ListSearch'
import MethodBadge from '../components/MethodBadge'
import usePageMeta from '../hooks/usePageMeta'
import useDebouncedValue from '../hooks/useDebouncedValue'

const PAGE_SIZE = 20
const SEARCH_DEBOUNCE_MS = 300
const METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'QUERY', 'MUTATION', 'SUBSCRIPTION', 'PUBLISH', 'SUBSCRIBE', 'SEND', 'RECEIVE']
const KINDS = ['openapi', 'asyncapi', 'postman', 'graphql']

/** One hit of GET /api/endpoint-search (backend EndpointHitOut). */
interface EndpointHit {
  document_id: string
  document_title: string
  is_public: boolean
  version: string
  spec_type: string
  method: string
  path: string
  name: string | null
  description: string | null
  tags: string[]
  deprecated: boolean
}

interface EndpointSearchData {
  total: number
  page: number
  page_size: number
  items: EndpointHit[]
}

const SELECT_CLASS =
  'rounded-lg border border-slate-200 bg-white px-3 py-2 text-base text-slate-900 sm:text-sm dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100'

/**
 * Finds an endpoint across the current version of every documentation the
 * visitor can see - the public ones, and a signed-in user's team's (GET
 * /api/endpoint-search; what an endpoint is, per kind of document, is the
 * backend's spec_outline). The text, method, kind and page live in the address
 * (`?q=&method=&kind=&page=`), so a search can be shared and the back button
 * returns to it; the text waits until typing pauses before it is sent. The
 * previous page of results stays up, dimmed, while the next one loads.
 */
export default function EndpointSearch() {
  const { t } = useTranslation()
  usePageMeta({ title: t('endpointSearch.pageTitle'), description: t('endpointSearch.pageDescription'), noindex: true })

  const [params, setParams] = useSearchParams()
  const method = params.get('method') ?? ''
  const kind = params.get('kind') ?? ''
  const page = Math.max(1, Number(params.get('page')) || 1)

  const [input, setInput] = useState(params.get('q') ?? '')
  const query = useDebouncedValue(input.trim(), SEARCH_DEBOUNCE_MS)
  const urlQuery = params.get('q') ?? ''

  const [data, setData] = useState<EndpointSearchData | null>(null)
  const [failed, setFailed] = useState(false)
  const [pending, setPending] = useState(true)

  function update(changes: Record<string, string | null>) {
    const next = new URLSearchParams(params)
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value)
      else next.delete(key)
    }
    setParams(next, { replace: true })
  }

  // The typed text, once it has settled, goes into the address - from the first page again.
  useEffect(() => {
    if (query !== urlQuery) update({ q: query || null, page: null })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query])

  useEffect(() => {
    // Responses can arrive out of order; one for a search the user has moved on from must not replace a newer one.
    let cancelled = false
    setPending(true)
    const search = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) })
    if (urlQuery) search.set('q', urlQuery)
    if (method) search.set('method', method)
    if (kind) search.set('spec_type', kind)
    apiFetch(`/api/endpoint-search?${search.toString()}`)
      .then((resp) => (resp.ok ? resp.json() : Promise.reject(new Error(`HTTP ${resp.status}`))))
      .then((result: EndpointSearchData) => {
        if (cancelled) return
        setData(result)
        setFailed(false)
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })
      .finally(() => {
        if (!cancelled) setPending(false)
      })
    return () => {
      cancelled = true
    }
  }, [urlQuery, method, kind, page])

  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 px-6 py-16 text-slate-900 dark:text-slate-100">
      <h1 className="text-2xl font-semibold tracking-tight">{t('endpointSearch.pageTitle')}</h1>

      <div className="flex flex-col gap-3">
        <ListSearch value={input} onChange={setInput} label={t('endpointSearch.label')} placeholder={t('endpointSearch.placeholder')} />
        <div className="flex flex-wrap gap-3">
          <select
            aria-label={t('endpointSearch.methodLabel')}
            value={method}
            onChange={(e) => update({ method: e.target.value || null, page: null })}
            className={SELECT_CLASS}
          >
            <option value="">{t('endpointSearch.anyMethod')}</option>
            {METHODS.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
          <select
            aria-label={t('endpointSearch.kindLabel')}
            value={kind}
            onChange={(e) => update({ kind: e.target.value || null, page: null })}
            className={SELECT_CLASS}
          >
            <option value="">{t('endpointSearch.anyKind')}</option>
            {KINDS.map((k) => (
              <option key={k} value={k}>
                {t(`specTypes.${k}`)}
              </option>
            ))}
          </select>
        </div>
      </div>

      {failed && <p className="text-sm text-red-600 dark:text-red-400">{t('endpointSearch.loadError')}</p>}
      {data === null && !failed && <p className="text-sm text-slate-600 dark:text-slate-400">{t('common.loading')}</p>}

      {data && (
        <>
          <p aria-live="polite" className="text-sm text-slate-600 dark:text-slate-400">
            {data.total === 0 ? t('endpointSearch.noResults') : t('endpointSearch.results', { count: data.total })}
          </p>

          {data.items.length > 0 && (
            <ul
              aria-busy={pending}
              className={`divide-y divide-slate-200 overflow-hidden rounded-2xl border border-slate-200 bg-white transition-opacity dark:divide-slate-800 dark:border-slate-800 dark:bg-slate-900 ${
                pending ? 'opacity-60' : ''
              }`}
            >
              {data.items.map((hit) => (
                <li key={`${hit.document_id}:${hit.method}:${hit.path}`}>
                  <Link to={`/api-docs/${hit.document_id}`} className="flex items-start gap-3 px-6 py-4 hover:bg-slate-50 dark:hover:bg-slate-800/50">
                    <MethodBadge method={hit.method} />
                    <div className="min-w-0 flex-1 space-y-1 text-sm">
                      <p className="break-all font-mono text-slate-900 dark:text-slate-100">
                        {hit.path}
                        {hit.deprecated && (
                          <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 font-sans text-xs font-medium text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
                            {t('endpointSearch.deprecated')}
                          </span>
                        )}
                      </p>
                      {hit.name && <p className="break-words text-slate-700 dark:text-slate-300">{hit.name}</p>}
                      {hit.description && <p className="line-clamp-2 break-words text-xs text-slate-500 dark:text-slate-400">{hit.description}</p>}
                      <p className="text-xs text-slate-500 dark:text-slate-400">
                        {hit.document_title}
                        {' · '}
                        {t(`specTypes.${hit.spec_type}`, { defaultValue: hit.spec_type })}
                        {' · '}
                        {t('endpointSearch.version', { version: hit.version })}
                        {!hit.is_public && ` · ${t('endpointSearch.team')}`}
                      </p>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}

          {pages > 1 && (
            <nav className="flex items-center justify-between gap-3 text-sm" aria-label={t('endpointSearch.page', { page: data.page, pages })}>
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => update({ page: page > 2 ? String(page - 1) : null })}
                className="rounded-lg border border-slate-200 px-3 py-1.5 text-slate-700 hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                {t('endpointSearch.previous')}
              </button>
              <span className="text-slate-600 dark:text-slate-400">{t('endpointSearch.page', { page: data.page, pages })}</span>
              <button
                type="button"
                disabled={page >= pages}
                onClick={() => update({ page: String(page + 1) })}
                className="rounded-lg border border-slate-200 px-3 py-1.5 text-slate-700 hover:bg-slate-100 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                {t('endpointSearch.next')}
              </button>
            </nav>
          )}
        </>
      )}
    </div>
  )
}
