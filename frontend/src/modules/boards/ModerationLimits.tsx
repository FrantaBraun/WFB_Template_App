/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  API_BASE,
  fetchJson,
  formatMoney,
  type CountryTotal,
  type LimitLevel,
  type OssYear,
  type PaymentsOverview,
} from './api'
import { card } from './styles'

// A level is never told by colour alone: every chip carries its text.
const LEVEL_CHIP: Record<LimitLevel, string> = {
  ok: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-500/20 dark:text-emerald-300',
  warn: 'bg-amber-100 text-amber-800 dark:bg-amber-500/20 dark:text-amber-200',
  exceeded: 'bg-rose-100 text-rose-800 dark:bg-rose-500/20 dark:text-rose-300',
}
const LEVEL_BAR: Record<LimitLevel, string> = {
  ok: 'bg-emerald-500',
  warn: 'bg-amber-500',
  exceeded: 'bg-rose-600',
}

function regionName(code: string, language: string): string {
  try {
    return new Intl.DisplayNames([language], { type: 'region' }).of(code) ?? code
  } catch {
    return code
  }
}

/** "2030-04-01" as a local date - `new Date(iso)` would read it as UTC midnight and may show the day before. */
function formatDay(iso: string, language: string): string {
  const [year, month, day] = iso.split('-').map(Number)
  return new Date(year, month - 1, day).toLocaleDateString(language)
}

function LimitBar({ percent, level, label }: { percent: number; level: LimitLevel; label: string }) {
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.min(Math.round(percent), 100)}
      className="h-2.5 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800"
    >
      <div className={`h-full rounded-full ${LEVEL_BAR[level]}`} style={{ width: `${Math.min(percent, 100)}%` }} />
    </div>
  )
}

function Figure({
  title,
  value,
  limit,
  percent,
  level,
}: {
  title: string
  value: string
  limit: string
  percent: number
  level: LimitLevel
}) {
  const { t, i18n } = useTranslation('boards')
  const language = i18n.resolvedLanguage ?? 'cs'
  const shown = percent.toLocaleString(language, { maximumFractionDigits: 1 })
  return (
    <div>
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-2xl font-extrabold tabular-nums">{t('admin.limits.figure', { value, limit })}</p>
        <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${LEVEL_CHIP[level]}`}>
          {t(`admin.limits.level.${level}`)} · {t('admin.limits.ofLimit', { percent: shown })}
        </span>
      </div>
      <LimitBar percent={percent} level={level} label={`${title}: ${t('admin.limits.ofLimit', { percent: shown })}`} />
    </div>
  )
}

function Countries({ countries, language }: { countries: CountryTotal[]; language: string }) {
  const { t } = useTranslation('boards')
  return (
    <table className="mt-4 w-full text-left text-sm">
      <caption className="sr-only">{t('admin.limits.oss.countries')}</caption>
      <thead className="text-xs text-slate-500 dark:text-slate-400">
        <tr>
          <th scope="col" className="py-1 pr-3 font-medium">{t('admin.limits.oss.columns.country')}</th>
          <th scope="col" className="py-1 pr-3 text-right font-medium">{t('admin.limits.oss.columns.payments')}</th>
          <th scope="col" className="py-1 text-right font-medium">{t('admin.limits.oss.columns.amount')}</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
        {countries.map((entry) => (
          <tr key={entry.country ?? 'unknown'}>
            <td className="py-1.5 pr-3">
              {entry.country ? `${regionName(entry.country, language)} (${entry.country})` : t('admin.limits.oss.unknownCountry')}
              {entry.eu && (
                <span className="ml-2 rounded-full bg-violet-100 px-2 py-0.5 text-xs font-medium text-violet-800 dark:bg-violet-500/20 dark:text-violet-200">
                  {t('admin.limits.oss.euChip')}
                </span>
              )}
            </td>
            <td className="py-1.5 pr-3 text-right tabular-nums">{entry.payments}</td>
            <td className="py-1.5 text-right tabular-nums">{formatMoney(entry.paid_usd_cents, 'usd', language)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function YearCard({ year, language }: { year: OssYear; language: string }) {
  const { t } = useTranslation('boards')
  const eur = new Intl.NumberFormat(language, { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 })
  const title = t('admin.limits.oss.year', { year: year.year })
  return (
    <section aria-label={title} className={`${card} p-5`}>
      <h4 className="mb-3 font-semibold">{title}</h4>
      <Figure
        title={title}
        value={eur.format(year.estimated_eur)}
        limit={eur.format(year.limit_eur)}
        percent={year.percent}
        level={year.level}
      />
      {year.countries.length === 0 ? (
        <p className="mt-3 text-slate-500 dark:text-slate-400">{t('admin.limits.oss.empty')}</p>
      ) : (
        <>
          <p className="mt-3 text-slate-600 dark:text-slate-400">
            {t('admin.limits.oss.sold', {
              amount: formatMoney(year.eu_paid_usd_cents, 'usd', language),
              count: year.eu_payments,
              estimate: eur.format(year.estimated_eur),
            })}
          </p>
          {year.unknown_country_payments > 0 && (
            <p className="mt-2 rounded-lg bg-amber-50 p-2 text-amber-900 dark:bg-amber-400/10 dark:text-amber-100">
              {t('admin.limits.oss.unknown', { count: year.unknown_country_payments })}
            </p>
          )}
          <Countries countries={year.countries} language={language} />
        </>
      )}
    </section>
  )
}

/**
 * The "Sales and limits" tab of /moderation: how close the confirmed payments
 * are to the two limits that change a provider's tax position (Czech VAT
 * registration, EU sales to consumers - see the backend's limits.py). Every
 * figure is an early warning with cautious assumptions, said so on the page.
 */
export default function ModerationLimits() {
  const { t, i18n } = useTranslation('boards')
  const language = i18n.resolvedLanguage ?? 'cs'
  const [overview, setOverview] = useState<PaymentsOverview | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let cancelled = false
    fetchJson<PaymentsOverview>(`${API_BASE}/manage/payments-overview`)
      .then((found) => !cancelled && setOverview(found))
      .catch(() => !cancelled && setError(true))
    return () => {
      cancelled = true
    }
  }, [])

  if (error) return <p className="text-sm text-red-600 dark:text-red-400">{t('admin.limits.error')}</p>
  if (overview === null) return <p className="text-sm text-slate-500 dark:text-slate-400">{t('common.loading')}</p>

  const czk = new Intl.NumberFormat(language, { style: 'currency', currency: 'CZK', maximumFractionDigits: 0 })
  const vat = overview.vat_registration
  const vatTitle = t('admin.limits.vat.title')
  const eurLimit = new Intl.NumberFormat(language, { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(
    overview.oss_years[0]?.limit_eur ?? 0,
  )

  return (
    <div className="space-y-8 text-sm">
      <p className="text-slate-600 dark:text-slate-400">{t('admin.limits.explain')}</p>

      <section aria-label={vatTitle}>
        <h3 className="mb-2 text-lg font-semibold">{vatTitle}</h3>
        {overview.vat_payer ? (
          <p className={`${card} p-5`}>{t('admin.limits.vat.payer')}</p>
        ) : (
          <div className={`${card} p-5`}>
            <p className="mb-3 text-slate-600 dark:text-slate-400">
              {t('admin.limits.vat.explain', {
                from: formatDay(vat.window_from, language),
                to: formatDay(vat.window_to, language),
                limit: czk.format(vat.limit_czk),
              })}
            </p>
            <Figure
              title={vatTitle}
              value={czk.format(vat.estimated_czk)}
              limit={czk.format(vat.limit_czk)}
              percent={vat.percent}
              level={vat.level}
            />
            <p className="mt-3 text-slate-600 dark:text-slate-400">
              {t('admin.limits.vat.paid', {
                amount: formatMoney(vat.paid_usd_cents, 'usd', language),
                count: vat.payments,
              })}
            </p>
            <p className="mt-2 text-slate-500 dark:text-slate-400">{t('admin.limits.vat.note')}</p>
          </div>
        )}
      </section>

      <section aria-label={t('admin.limits.oss.title')}>
        <h3 className="mb-2 text-lg font-semibold">{t('admin.limits.oss.title')}</h3>
        <p className="mb-3 text-slate-600 dark:text-slate-400">{t('admin.limits.oss.explain', { limit: eurLimit })}</p>
        <div className="grid gap-4 md:grid-cols-2">
          {[...overview.oss_years].reverse().map((year) => (
            <YearCard key={year.year} year={year} language={language} />
          ))}
        </div>
        <p className="mt-3 text-slate-500 dark:text-slate-400">{t('admin.limits.oss.note')}</p>
      </section>

      <p className="text-xs text-slate-500 dark:text-slate-400">
        {t('admin.limits.rates', { czk: overview.czk_per_usd.toLocaleString(language), eur: overview.eur_per_usd.toLocaleString(language) })}{' '}
        {t('admin.limits.generated', { time: new Date(overview.generated_at).toLocaleString(language) })}
      </p>
    </div>
  )
}
