/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import usePageMeta from '../../hooks/usePageMeta'
import { API_BASE, MANAGE_PATH, fetchJson, itemPath, usePublicLanguage, type PublicItem } from './api'
import { StatusBadge, TagList, cardClass, container, mutedText, secondaryButtonClass } from './ui'

type State = { status: 'loading' } | { status: 'error' } | { status: 'ready'; items: PublicItem[] }

function ItemCard({ item }: { item: PublicItem }) {
  const { t } = useTranslation('portfolio')
  return (
    <li
      className={`${cardClass} relative flex min-w-0 flex-col gap-3 p-5 transition-colors hover:border-violet-300 has-[a:focus-visible]:outline-2 has-[a:focus-visible]:outline-offset-2 has-[a:focus-visible]:outline-violet-600 dark:hover:border-violet-700 dark:has-[a:focus-visible]:outline-violet-400`}
    >
      <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-2">
        <h2 className="min-w-0 break-words text-lg font-semibold tracking-tight">
          {/* A stretched link: the whole card is clickable, but the link text is just the title. */}
          <Link to={itemPath(item.slug)} className="outline-none after:absolute after:inset-0 after:content-['']">
            {item.title}
          </Link>
        </h2>
        {item.status === 'in_preparation' && <StatusBadge status={item.status} />}
      </div>
      <p className={`break-words ${mutedText}`}>{item.summary}</p>
      <div className="mt-auto pt-1">
        <TagList tags={item.tags} label={t('list.tagsLabel')} />
      </div>
    </li>
  )
}

/** /portfolio - the published projects as a grid of cards, in the administrator's order. */
export default function PortfolioPage() {
  const { t } = useTranslation('portfolio')
  const { user } = useAuth()
  const language = usePublicLanguage()
  const [state, setState] = useState<State>({ status: 'loading' })
  const [reload, setReload] = useState(0)

  usePageMeta({ title: t('list.title'), description: t('list.metaDescription') })

  useEffect(() => {
    let cancelled = false
    // Keep what is shown while the same list is fetched again in another language.
    setState((current) => (current.status === 'ready' ? current : { status: 'loading' }))
    fetchJson<PublicItem[]>(`${API_BASE}/items?language=${encodeURIComponent(language)}`)
      .then((items) => !cancelled && setState({ status: 'ready', items }))
      .catch(() => !cancelled && setState({ status: 'error' }))
    return () => {
      cancelled = true
    }
  }, [language, reload])

  return (
    <div className={`${container} py-12 text-slate-900 dark:text-slate-100 sm:py-16`}>
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="min-w-0">
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">{t('list.title')}</h1>
          <p className={`mt-4 max-w-2xl text-lg ${mutedText}`}>{t('list.intro')}</p>
        </div>
        {user?.is_admin === true && (
          <Link to={MANAGE_PATH} className={secondaryButtonClass}>
            {t('list.manage')}
          </Link>
        )}
      </div>

      <div className="mt-10">
        {state.status === 'loading' && <p role="status" className={mutedText}>{t('common.loading')}</p>}

        {state.status === 'error' && (
          <div role="alert" className="space-y-3">
            <p className="text-red-700 dark:text-red-400">{t('list.loadError')}</p>
            <button type="button" onClick={() => setReload((n) => n + 1)} className={secondaryButtonClass}>
              {t('common.retry')}
            </button>
          </div>
        )}

        {state.status === 'ready' && state.items.length === 0 && <p className={mutedText}>{t('list.empty')}</p>}

        {state.status === 'ready' && state.items.length > 0 && (
          <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {state.items.map((item) => (
              <ItemCard key={item.slug} item={item} />
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

