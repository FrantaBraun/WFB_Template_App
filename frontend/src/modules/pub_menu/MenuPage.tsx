/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'
import usePageMeta from '../../hooks/usePageMeta'
import { AllergenLegend, AllergenList } from './Allergens'
import {
  API_BASE,
  DAILY_KINDS,
  addDays,
  fetchJson,
  formatPrice,
  isoDay,
  mondayOf,
  parseDay,
  query,
  shortDate,
  weekdayName,
  type DailyDay,
  type DailyItem,
  type DailyWeek,
  type Offer,
  type OfferCategory,
  type OfferItem,
} from './api'
import { PageMessage, cardClass, errorClass, mutedClass, secondaryButtonClass } from './ui'

type Tab = 'daily' | 'food' | 'drink'
const TABS: Tab[] = ['daily', 'food', 'drink']

/**
 * /menu - the pub's menus for visitors: the lunch menu by week and the standing
 * menu, food and drinks. The tab is in the address (?tab=) so a link can point at one.
 */
export default function MenuPage() {
  const { t } = useTranslation('pub_menu')
  usePageMeta({ title: t('page.title'), description: t('page.description') })
  const [params, setParams] = useSearchParams()
  const requested = params.get('tab')
  const tab: Tab = TABS.includes(requested as Tab) ? (requested as Tab) : 'daily'

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 text-slate-900 sm:px-6 sm:py-12 dark:text-slate-100">
      <h1 className="mb-2 text-2xl font-semibold tracking-tight sm:text-3xl">{t('page.title')}</h1>
      <p className={`mb-6 max-w-2xl ${mutedClass}`}>{t('page.intro')}</p>
      <div role="tablist" aria-label={t('page.title')} className="mb-6 flex flex-wrap gap-2">
        {TABS.map((value) => (
          <button
            key={value}
            type="button"
            role="tab"
            id={`menu-tab-${value}`}
            aria-selected={tab === value}
            aria-controls="menu-panel"
            onClick={() => setParams(value === 'daily' ? {} : { tab: value }, { replace: true })}
            className={`rounded-lg px-4 py-2 text-sm font-medium ${
              tab === value
                ? 'bg-slate-900 text-slate-100 dark:bg-slate-100 dark:text-slate-900'
                : 'border border-slate-200 hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800'
            }`}
          >
            {t(`page.tab.${value}`)}
          </button>
        ))}
      </div>
      <div role="tabpanel" id="menu-panel" aria-labelledby={`menu-tab-${tab}`}>
        {tab === 'daily' ? <DailyMenu /> : <Standing kind={tab} />}
      </div>
      <div className="mt-8">
        <AllergenLegend />
      </div>
    </div>
  )
}

// --- The lunch menu ------------------------------------------------------------------------------

function DailyMenu() {
  const { t, i18n } = useTranslation('pub_menu')
  const language = i18n.resolvedLanguage ?? i18n.language
  const [week, setWeek] = useState<DailyWeek | null>(null)
  const [on, setOn] = useState<string | null>(null) // null = the week of today
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading')

  useEffect(() => {
    let cancelled = false
    setState('loading')
    fetchJson<DailyWeek>(`${API_BASE}/daily${query({ date: on })}`)
      .then((found) => {
        if (cancelled) return
        setWeek(found)
        setState('ready')
      })
      .catch(() => !cancelled && setState('error'))
    return () => {
      cancelled = true
    }
  }, [on])

  if (state === 'error') return <p role="alert" className={errorClass}>{t('daily.loadError')}</p>
  if (!week) return <PageMessage>{t('common.loading')}</PageMessage>

  const today = isoDay(new Date())
  const previous = addDays(week.week_start, -7)
  const next = addDays(week.week_start, 7)
  const weekdays = week.days.filter((entry, index) => index < 5 || entry.items.length > 0) // Saturday and Sunday only when there is something

  return (
    <div className="space-y-4" aria-busy={state === 'loading'}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-xl font-semibold">{t('daily.title')}</h2>
        <div className="flex items-center gap-2">
          <button type="button" onClick={() => setOn(previous)} disabled={previous < week.min_week_start} aria-label={t('daily.previousWeek')} className={secondaryButtonClass}>
            ‹
          </button>
          <span className="text-sm" aria-live="polite">
            {t('daily.week', { from: shortDate(week.week_start, language), to: shortDate(week.week_end, language) })}
          </span>
          <button type="button" onClick={() => setOn(next)} disabled={next > week.max_week_start} aria-label={t('daily.nextWeek')} className={secondaryButtonClass}>
            ›
          </button>
          {mondayOf(today) !== week.week_start && (
            <button type="button" onClick={() => setOn(null)} className={secondaryButtonClass}>
              {t('daily.thisWeek')}
            </button>
          )}
        </div>
      </div>
      {week.note && <p className={`whitespace-pre-line ${mutedClass}`}>{week.note}</p>}
      <div className="space-y-4">
        {weekdays.map((entry) => (
          <DayCard key={entry.day} entry={entry} currency={week.currency} isToday={entry.day === today} />
        ))}
      </div>
    </div>
  )
}

/** One day of the lunch menu: its dishes grouped by kind - soups, main courses, desserts, the rest. */
export function DayCard({ entry, currency, isToday = false }: { entry: DailyDay; currency: string; isToday?: boolean }) {
  const { t, i18n } = useTranslation('pub_menu')
  const language = i18n.resolvedLanguage ?? i18n.language
  const groups = DAILY_KINDS.map((kind) => ({ kind, items: entry.items.filter((item) => item.kind === kind) })).filter((group) => group.items.length > 0)

  return (
    <section className={`${cardClass} ${isToday ? 'ring-2 ring-slate-900 dark:ring-slate-100' : ''}`} aria-label={weekdayName(entry.day, language)}>
      <h3 className="mb-3 flex flex-wrap items-baseline gap-x-2 text-lg font-semibold">
        <span className="capitalize">{weekdayName(entry.day, language)}</span>
        <span className={`font-normal ${mutedClass}`}>{parseDay(entry.day).toLocaleDateString(language, { day: 'numeric', month: 'numeric' })}</span>
        {isToday && <span className="rounded-full bg-slate-900 px-2 py-0.5 text-xs font-medium text-slate-100 dark:bg-slate-100 dark:text-slate-900">{t('daily.today')}</span>}
      </h3>
      {groups.length === 0 ? (
        <p className={mutedClass}>{t('daily.none')}</p>
      ) : (
        <div className="space-y-4">
          {groups.map((group) => (
            <div key={group.kind}>
              {groups.length > 1 && <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">{t(`daily.kinds.${group.kind}`)}</h4>}
              <ul className="divide-y divide-slate-100 dark:divide-slate-800">
                {group.items.map((item) => (
                  <DailyRow key={item.id} item={item} currency={currency} />
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

function DailyRow({ item, currency }: { item: DailyItem; currency: string }) {
  const { i18n } = useTranslation('pub_menu')
  const language = i18n.resolvedLanguage ?? i18n.language
  return (
    <li className="flex items-baseline justify-between gap-4 py-2">
      <div className="min-w-0">
        <p>
          <span className="font-medium">{item.name}</span>
          {item.amount && <span className={`ml-2 ${mutedClass}`}>{item.amount}</span>}
        </p>
        {item.description && <p className={mutedClass}>{item.description}</p>}
        <AllergenList numbers={item.allergens} />
      </div>
      {item.price !== null && <p className="shrink-0 font-medium tabular-nums">{formatPrice(item.price, currency, language)}</p>}
    </li>
  )
}

// --- The standing menu ----------------------------------------------------------------------------

function Standing({ kind }: { kind: 'food' | 'drink' }) {
  const { t } = useTranslation('pub_menu')
  const [offer, setOffer] = useState<Offer | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    fetchJson<Offer>(`${API_BASE}/offer`)
      .then((found) => {
        if (cancelled) return
        setOffer(found)
        setFailed(false)
      })
      .catch(() => !cancelled && setFailed(true))
    return () => {
      cancelled = true
    }
  }, [])

  if (failed) return <p role="alert" className={errorClass}>{t('offer.loadError')}</p>
  if (!offer) return <PageMessage>{t('common.loading')}</PageMessage>

  const categories = offer.categories.filter((category) => category.kind === kind)
  return (
    <div className="space-y-6">
      {offer.note && <p className={`whitespace-pre-line ${mutedClass}`}>{offer.note}</p>}
      {categories.length === 0 ? (
        <p className={cardClass}>{t('offer.none')}</p>
      ) : (
        categories.map((category) => <CategoryCard key={category.id} category={category} currency={offer.currency} />)
      )}
    </div>
  )
}

function CategoryCard({ category, currency }: { category: OfferCategory; currency: string }) {
  const { t } = useTranslation('pub_menu')
  return (
    <section className={cardClass} aria-labelledby={`category-${category.id}`}>
      <h2 id={`category-${category.id}`} className="text-xl font-semibold">
        {category.name}
      </h2>
      {category.description && <p className={`mt-1 ${mutedClass}`}>{category.description}</p>}
      {category.items.length === 0 ? (
        <p className={`mt-3 ${mutedClass}`}>{t('offer.emptyCategory')}</p>
      ) : (
        <ul className="mt-3 divide-y divide-slate-100 dark:divide-slate-800">
          {category.items.map((item) => (
            <OfferRow key={item.id} item={item} currency={currency} />
          ))}
        </ul>
      )}
    </section>
  )
}

function OfferRow({ item, currency }: { item: OfferItem; currency: string }) {
  const { t, i18n } = useTranslation('pub_menu')
  const language = i18n.resolvedLanguage ?? i18n.language
  return (
    <li className={`flex items-baseline justify-between gap-4 py-2 ${item.is_available ? '' : 'opacity-60'}`}>
      <div className="min-w-0">
        <p>
          <span className={`font-medium ${item.is_available ? '' : 'line-through'}`}>{item.name}</span>
          {!item.is_available && <span className="ml-2 rounded-full border border-slate-300 px-2 py-0.5 text-xs dark:border-slate-600">{t('offer.soldOut')}</span>}
        </p>
        {item.description && <p className={mutedClass}>{item.description}</p>}
        <AllergenList numbers={item.allergens} />
      </div>
      <ul className="shrink-0 text-right tabular-nums">
        {item.prices.map((price, index) => (
          <li key={index}>
            {price.label && <span className={`mr-2 ${mutedClass}`}>{price.label}</span>}
            <span className="font-medium">{formatPrice(price.price, currency, language)}</span>
          </li>
        ))}
      </ul>
    </li>
  )
}
