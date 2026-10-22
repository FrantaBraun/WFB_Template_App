/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import type { Aggregation, Attribute, Dimension, StatisticResult } from './api'
import { aggregationText, dimensionKind, dimensionName, formatValue, keyText } from './statFormat'

const cell = 'px-3 py-1.5 text-right tabular-nums'
const head = 'px-3 py-2 text-left font-semibold'

/**
 * The numbers of a statistic written out: a list of groups, or - with two
 * dimensions - a pivot table with the totals of every row and column and of
 * everything. This is the table view every chart has (the chart's tooltips say
 * nothing this does not), so it is complete whatever the chart shows.
 */
export default function PivotTable({
  result,
  dimensions,
  aggregation,
  attributes,
}: {
  result: StatisticResult
  dimensions: Dimension[]
  aggregation: Aggregation
  attributes: Attribute[]
}) {
  const { t, i18n } = useTranslation('repository')
  const language = i18n.resolvedLanguage ?? 'cs'
  const kinds = dimensions.map((dimension) => dimensionKind(dimension, attributes))
  const rowTitle = dimensionName(dimensions[0], attributes, t)
  const what = aggregationText(aggregation, attributes, t)
  const caption =
    result.dimensions === 1
      ? t('statistics.tableCaption1', { what, by: rowTitle })
      : t('statistics.tableCaption2', { what, rows: rowTitle, columns: dimensionName(dimensions[1], attributes, t) })

  return (
    <div className="space-y-1">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <caption className="sr-only">{caption}</caption>
          <thead className="border-b border-slate-200 text-slate-700 dark:border-slate-700 dark:text-slate-300">
            <tr>
              <th scope="col" className={head}>
                {result.dimensions === 2 ? `${rowTitle} / ${dimensionName(dimensions[1], attributes, t)}` : rowTitle}
              </th>
              {result.dimensions === 1 ? (
                <th scope="col" className={`${head} text-right`}>
                  {what}
                </th>
              ) : (
                <>
                  {result.columns.map((column, index) => (
                    <th key={index} scope="col" className={`${head} text-right`}>
                      {keyText(dimensions[1], kinds[1], column, language, t)}
                    </th>
                  ))}
                  <th scope="col" className={`${head} text-right`}>
                    {t('statistics.total')}
                  </th>
                </>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {result.rows.map((row, rowIndex) => (
              <tr key={rowIndex}>
                <th scope="row" className="px-3 py-1.5 text-left font-medium">
                  {keyText(dimensions[0], kinds[0], row, language, t)}
                </th>
                {result.values[rowIndex].map((value, columnIndex) => (
                  <td key={columnIndex} className={cell}>
                    {formatValue(value, language)}
                  </td>
                ))}
                {result.dimensions === 2 && <td className={`${cell} font-semibold`}>{formatValue(result.row_totals[rowIndex], language)}</td>}
              </tr>
            ))}
          </tbody>
          <tfoot className="border-t border-slate-300 font-semibold dark:border-slate-600">
            <tr>
              <th scope="row" className="px-3 py-1.5 text-left">
                {t('statistics.total')}
              </th>
              {result.dimensions === 2 &&
                result.column_totals.map((value, index) => (
                  <td key={index} className={cell}>
                    {formatValue(value, language)}
                  </td>
                ))}
              <td className={cell}>{formatValue(result.total, language)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
      {result.truncated && <p className="text-xs text-slate-500 dark:text-slate-400">{t('statistics.truncated')}</p>}
    </div>
  )
}
