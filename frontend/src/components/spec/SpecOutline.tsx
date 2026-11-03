/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import ListSearch from '../ListSearch'
import MethodBadge from '../MethodBadge'
import type { OutlineEndpoint, VersionOutline } from '../../utils/versionSpec'

/** Lower case without diacritics, so typing "zakaznik" finds "zákazník" - the same folding the backend search does. */
function fold(text: string): string {
  return text.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase()
}

function searchable(endpoint: OutlineEndpoint): string {
  return fold([endpoint.method, endpoint.path, endpoint.name, endpoint.description, endpoint.operation_id, ...endpoint.tags].filter(Boolean).join(' '))
}

/**
 * What a version contains, as a list of its endpoints with a filter - how a
 * document of a kind that has no rendered documentation here (AsyncAPI, a
 * Postman collection, a GraphQL schema) is read. `outline` is the backend's
 * GET .../versions/{id}/outline; the filter works on what is already loaded.
 */
export default function SpecOutline({ outline }: { outline: VersionOutline }) {
  const { t } = useTranslation()
  const [filter, setFilter] = useState('')

  const rows = useMemo(() => outline.endpoints.map((endpoint) => ({ endpoint, text: searchable(endpoint) })), [outline])
  const terms = fold(filter).split(/\s+/).filter(Boolean)
  const shown = terms.length === 0 ? rows : rows.filter((row) => terms.every((term) => row.text.includes(term)))

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm text-slate-600 dark:text-slate-400">
          {t(`specTypes.${outline.spec_type}`, { defaultValue: outline.spec_type })}
          {' · '}
          {t('outline.summary', { count: outline.endpoints.length })}
        </p>
      </div>
      <p className="text-sm text-slate-600 dark:text-slate-400">{t('outline.notRendered')}</p>

      {outline.endpoints.length === 0 ? (
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('outline.empty')}</p>
      ) : (
        <>
          <ListSearch value={filter} onChange={setFilter} label={t('outline.filterLabel')} placeholder={t('outline.filterPlaceholder')} />
          {shown.length === 0 ? (
            <p className="text-sm text-slate-600 dark:text-slate-400">{t('outline.noMatch', { query: filter.trim() })}</p>
          ) : (
            <ul className="divide-y divide-slate-200 dark:divide-slate-800">
              {shown.map(({ endpoint }) => (
                <li key={`${endpoint.method} ${endpoint.path}`} className="flex flex-wrap items-start gap-3 py-3 text-sm">
                  <MethodBadge method={endpoint.method} />
                  <div className="min-w-0 flex-1 space-y-1">
                    <p className="break-all font-mono text-slate-900 dark:text-slate-100">
                      {endpoint.path}
                      {endpoint.deprecated && (
                        <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 font-sans text-xs font-medium text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
                          {t('outline.deprecated')}
                        </span>
                      )}
                    </p>
                    {endpoint.name && <p className="break-words text-slate-700 dark:text-slate-300">{endpoint.name}</p>}
                    {endpoint.description && (
                      <p className="line-clamp-3 break-words text-xs text-slate-500 dark:text-slate-400">{endpoint.description}</p>
                    )}
                    {endpoint.tags.length > 0 && (
                      <p className="flex flex-wrap gap-1">
                        {endpoint.tags.map((tag) => (
                          <span key={tag} className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                            {tag}
                          </span>
                        ))}
                      </p>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  )
}
