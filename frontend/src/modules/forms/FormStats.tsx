/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import type { FormStatsData, QuestionStats } from './api'

function formatNumber(value: number, language: string): string {
  return value.toLocaleString(language, { maximumFractionDigits: 2 })
}

function formatBound(type: QuestionStats['type'], value: string, language: string): string {
  if (type === 'date') return new Date(`${value}T00:00`).toLocaleDateString(language)
  if (type === 'datetime') return new Date(value).toLocaleString(language, { dateStyle: 'medium', timeStyle: 'short' })
  return value
}

function QuestionBlock({ stats }: { stats: QuestionStats }) {
  const { t, i18n } = useTranslation('forms')
  const language = i18n.language

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
      <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-semibold">{stats.label}</h3>
        <span className="text-xs text-slate-500 dark:text-slate-400">{t(`types.${stats.type}`)}</span>
      </div>
      <p className="mb-3 text-sm text-slate-600 dark:text-slate-300">
        {t('stats.shownAnswered', { shown: stats.shown_count, answered: stats.answered_count })}
      </p>

      {stats.options && (
        <ul className="space-y-2">
          {stats.options.map((option) => (
            <li key={option.id}>
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span>{option.label}</span>
                <span className="tabular-nums text-slate-600 dark:text-slate-300">
                  {option.count} ({formatNumber(option.percent, language)} %)
                </span>
              </div>
              {/* The bar is decoration: the count and share above are the data. */}
              <div aria-hidden="true" className="mt-1 h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                <div className="h-full rounded-full bg-sky-500 dark:bg-sky-400" style={{ width: `${Math.min(option.percent, 100)}%` }} />
              </div>
            </li>
          ))}
          {stats.average_selected !== undefined && (
            <li className="pt-1 text-sm text-slate-600 dark:text-slate-300">
              {t('stats.averageSelected', { value: formatNumber(stats.average_selected, language) })}
            </li>
          )}
        </ul>
      )}

      {stats.numeric && (
        <table className="text-sm">
          <tbody>
            {(['min', 'max', 'average', 'median'] as const).map((key) => (
              <tr key={key}>
                <th scope="row" className="pr-6 text-left font-normal text-slate-500 dark:text-slate-400">{t(`stats.${key}`)}</th>
                <td className="tabular-nums">{formatNumber(stats.numeric![key], language)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {stats.range && (
        <table className="text-sm">
          <tbody>
            <tr>
              <th scope="row" className="pr-6 text-left font-normal text-slate-500 dark:text-slate-400">{t('stats.earliest')}</th>
              <td>{formatBound(stats.type, stats.range.earliest, language)}</td>
            </tr>
            <tr>
              <th scope="row" className="pr-6 text-left font-normal text-slate-500 dark:text-slate-400">{t('stats.latest')}</th>
              <td>{formatBound(stats.type, stats.range.latest, language)}</td>
            </tr>
          </tbody>
        </table>
      )}

      {stats.type === 'text' && <p className="text-sm text-slate-500 dark:text-slate-400">{t('stats.textHint')}</p>}
    </section>
  )
}

/**
 * The summary of a form's answers, question by question: to how many it was
 * shown and how many answered (which is what shows how a conditional question
 * fared), bars with counts and shares for the options of a choice (the
 * numbers are always written out too), minimum / maximum / average / median
 * for numbers, earliest and latest for dates and times, and just the counts
 * for texts. Takes the data from wherever you fetched it, so you can summarise
 * only the answers that still count.
 */
export default function FormStats({ stats }: { stats: FormStatsData }) {
  const { t } = useTranslation('forms')

  if (stats.submission_count === 0) {
    return <p className="text-slate-500 dark:text-slate-400">{t('answers.empty')}</p>
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600 dark:text-slate-300">{t('stats.total', { count: stats.submission_count })}</p>
      {stats.questions.map((question) => (
        <QuestionBlock key={`${question.question_id}-${question.type}`} stats={question} />
      ))}
    </div>
  )
}
