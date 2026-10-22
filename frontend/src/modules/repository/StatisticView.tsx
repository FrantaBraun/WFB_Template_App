/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { Aggregation, Attribute, ChartType, Dimension, StatisticDisplay, StatisticResult } from './api'
import StatChart from './charts'
import PivotTable from './PivotTable'
import { toChartData } from './statFormat'
import { secondaryButtonClass } from './ui'

/**
 * A statistic's result as its `display` asks: the table, the chart, or both. A
 * chart on its own has a button that shows the numbers as a table too, so the
 * values are never only in the picture.
 */
export default function StatisticView({
  result,
  dimensions,
  aggregation,
  attributes,
  display,
  chartType,
}: {
  result: StatisticResult
  dimensions: Dimension[]
  aggregation: Aggregation
  attributes: Attribute[]
  display: StatisticDisplay
  chartType: ChartType
}) {
  const { t, i18n } = useTranslation('repository')
  const language = i18n.resolvedLanguage ?? 'cs'
  const [tableToo, setTableToo] = useState(false)
  const showChart = display === 'chart' || display === 'both'
  const showTable = display === 'table' || display === 'both' || tableToo

  return (
    <div className="space-y-3 text-slate-900 dark:text-slate-100">
      {showChart && <StatChart kind={chartType} data={toChartData(result, dimensions, attributes, aggregation, language, t)} language={language} />}
      {display === 'chart' && (
        <button type="button" onClick={() => setTableToo((value) => !value)} aria-expanded={tableToo} className={secondaryButtonClass}>
          {t(tableToo ? 'statistics.hideTable' : 'statistics.showTable')}
        </button>
      )}
      {showTable && <PivotTable result={result} dimensions={dimensions} aggregation={aggregation} attributes={attributes} />}
    </div>
  )
}
