/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import usePageMeta from '../../hooks/usePageMeta'
import { API_BASE, CRM_PATH, fetchJson, partnerPath, type PartnerListItem } from './api'
import { CrmGate, cardClass, inputClass, primaryButtonClass } from './ui'

const SEARCH_DEBOUNCE_MS = 250

function PartnersList() {
  const { t } = useTranslation('crm')
  const [partners, setPartners] = useState<PartnerListItem[] | null>(null)
  const [error, setError] = useState(false)
  const [search, setSearch] = useState('')
  const [includeArchived, setIncludeArchived] = useState(false)

  useEffect(() => {
    let cancelled = false
    const timer = setTimeout(() => {
      const params = new URLSearchParams()
      if (search.trim()) params.set('q', search.trim())
      if (includeArchived) params.set('include_archived', 'true')
      fetchJson<PartnerListItem[]>(`${API_BASE}/partners?${params}`)
        .then((found) => {
          if (cancelled) return
          setPartners(found)
          setError(false)
        })
        .catch(() => !cancelled && setError(true))
    }, SEARCH_DEBOUNCE_MS)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [search, includeArchived])

  const filtering = search.trim() !== ''

  return (
    <div className="mx-auto max-w-4xl px-6 py-12 text-slate-900 dark:text-slate-100">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-3xl font-semibold tracking-tight">{t('partners.title')}</h1>
        <Link to={`${CRM_PATH}/partners/new`} className={primaryButtonClass}>
          {t('partners.new')}
        </Link>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-4">
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t('partners.search')}
          aria-label={t('partners.search')}
          maxLength={100}
          className={`${inputClass} sm:max-w-sm`}
        />
        <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
          <input type="checkbox" checked={includeArchived} onChange={(e) => setIncludeArchived(e.target.checked)} />
          {t('partners.showArchived')}
        </label>
      </div>

      {error && <p className="text-sm text-red-600 dark:text-red-400">{t('partners.loadError')}</p>}
      {partners === null && !error && <p className="text-slate-500 dark:text-slate-400">{t('common.loading')}</p>}
      {partners && partners.length === 0 && (
        <p className="text-slate-500 dark:text-slate-400">{filtering ? t('partners.emptyFiltered') : t('partners.empty')}</p>
      )}

      {partners && partners.length > 0 && (
        <ul className={`${cardClass} divide-y divide-slate-200 overflow-hidden dark:divide-slate-800`}>
          {partners.map((partner) => (
            <li key={partner.id}>
              <Link to={partnerPath(partner.id)} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-800/60">
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">{partner.name}</span>
                  {(partner.company || partner.email) && (
                    <span className="block truncate text-sm text-slate-500 dark:text-slate-400">
                      {[partner.company, partner.email].filter(Boolean).join(' · ')}
                    </span>
                  )}
                </span>
                {partner.archived && (
                  <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                    {t('partners.archived')}
                  </span>
                )}
                <span className="text-sm text-slate-500 dark:text-slate-400">{t('partners.taskCount', { count: partner.task_count })}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/** /crm - the partner list, with search. */
export default function PartnersPage() {
  const { t } = useTranslation('crm')
  usePageMeta({ title: t('partners.title') })
  return (
    <CrmGate>
      <PartnersList />
    </CrmGate>
  )
}
