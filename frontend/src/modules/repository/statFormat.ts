/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

// How the keys and values of a statistic's result are written. Pure and
// free of React, so the chart components and the table share one wording.

import { formatDate, formatNumber, type Aggregation, type Attribute, type Dimension, type ResultKey, type StatisticResult } from './api'

/** What useTranslation('repository') gives; typed loosely so these helpers do not depend on i18next's types. */
export type Translate = (key: string, options?: Record<string, unknown>) => string

/** The kind of a dimension's field: `timestamp` for created_on, the attribute's type otherwise. */
export function dimensionKind(dimension: Dimension, attributes: Attribute[]): string {
  if (dimension.field === 'created_on') return 'timestamp'
  return attributes.find((attribute) => attribute.id === dimension.field)?.type ?? 'text'
}

/** The name of a dimension's field (a translated `Created` for created_on). */
export function dimensionName(dimension: Dimension, attributes: Attribute[], t: Translate): string {
  if (dimension.field === 'created_on') return t('filters.system.createdOn')
  return attributes.find((attribute) => attribute.id === dimension.field)?.name ?? '?'
}

/** A group's key as the reader sees it: an empty value as "(empty)", a month as "Jan 2026", a record by its name. */
export function keyText(dimension: Dimension, kind: string, item: ResultKey, language: string, t: Translate): string {
  if (item.key === null) return t('statistics.empty')
  if (kind === 'reference') return item.label ?? String(item.key)
  if (kind === 'boolean') return item.key === 'true' ? t('record.boolean.yes') : t('record.boolean.no')
  if (kind === 'number') return formatNumber(Number(item.key), language)
  if (dimension.bucket && (kind === 'date' || kind === 'datetime' || kind === 'timestamp')) {
    const key = String(item.key)
    if (dimension.bucket === 'day') return formatDate(key, language)
    if (dimension.bucket === 'month') {
      const [year, month] = key.split('-').map(Number)
      return new Date(year, month - 1, 1).toLocaleDateString(language, { month: 'short', year: 'numeric' })
    }
    return key
  }
  return String(item.key)
}

/** What a statistic computes, in words: "Count", "Sum of Amount". */
export function aggregationText(aggregation: Aggregation, attributes: Attribute[], t: Translate): string {
  if (aggregation.fn === 'count') return t('statistics.fn.count')
  const name = attributes.find((attribute) => attribute.id === aggregation.attribute_id)?.name ?? '?'
  return t(`statistics.fn.${aggregation.fn}`, { name })
}

export function formatValue(value: number | null, language: string): string {
  return value === null ? '—' : value.toLocaleString(language, { maximumFractionDigits: 2 })
}

/** Axis tick text: whole thousands and up are shortened (1K, 2.5M). */
export function compactNumber(value: number, language: string): string {
  return value.toLocaleString(language, { notation: 'compact', maximumFractionDigits: 1 })
}

/** A "nice" top for an axis and the ticks up to it (0, step, 2 step, ...), including negative values. */
export function niceScale(min: number, max: number, targetTicks = 5): { min: number; max: number; ticks: number[] } {
  const low = Math.min(0, min)
  const high = Math.max(0, max)
  const span = high - low || 1
  const rough = span / targetTicks
  const magnitude = 10 ** Math.floor(Math.log10(rough))
  const step = [1, 2, 2.5, 5, 10].map((factor) => factor * magnitude).find((candidate) => candidate >= rough) ?? 10 * magnitude
  const niceMin = Math.floor(low / step) * step
  const niceMax = Math.ceil(high / step) * step
  const ticks: number[] = []
  for (let tick = niceMin; tick <= niceMax + step / 2; tick += step) ticks.push(Math.round(tick * 1e9) / 1e9)
  return { min: niceMin, max: niceMax, ticks }
}

export interface ChartSeries {
  name: string
  values: (number | null)[]
}

export interface ChartData {
  categories: string[]
  /** For a date axis: where each category is in time (days, months or years as one number), so a gap in the data is a gap on the axis. Null otherwise. */
  positions: number[] | null
  /** Which categories are the "(empty)" group - drawn in the neutral colour, not in a palette slot. */
  neutral: boolean[]
  series: ChartSeries[]
  /** Series that did not fit the palette (the table has them). */
  omittedSeries: number
}

export const MAX_SERIES = 8

/** A bucket key ("2026", "2026-03", "2026-03-14") as one number on a time axis, or null for something else. */
function timeValue(bucket: string, key: string): number | null {
  const parts = key.split('-').map(Number)
  if (parts.some((part) => !Number.isFinite(part))) return null
  if (bucket === 'year') return parts[0]
  if (bucket === 'month') return parts[0] * 12 + (parts[1] - 1)
  return Date.UTC(parts[0], parts[1] - 1, parts[2]) / 86_400_000
}

/** Where the rows of a date dimension are in time - null when it is not one, or a row (the empty group) has no place. */
function timePositions(dimension: Dimension, kind: string, result: StatisticResult): number[] | null {
  if (!dimension.bucket || !(kind === 'date' || kind === 'datetime' || kind === 'timestamp')) return null
  const positions = result.rows.map((row) => (typeof row.key === 'string' ? timeValue(dimension.bucket as string, row.key) : null))
  return positions.every((position) => position !== null) ? (positions as number[]) : null
}

/** The result as what the charts draw: one series for one dimension, a series per column for two. */
export function toChartData(
  result: StatisticResult,
  dimensions: Dimension[],
  attributes: Attribute[],
  aggregation: Aggregation,
  language: string,
  t: Translate,
): ChartData {
  const kinds = dimensions.map((dimension) => dimensionKind(dimension, attributes))
  const categories = result.rows.map((row) => keyText(dimensions[0], kinds[0], row, language, t))
  const neutral = result.rows.map((row) => row.key === null)
  const positions = timePositions(dimensions[0], kinds[0], result)
  if (result.dimensions === 1) {
    return { categories, positions, neutral, series: [{ name: aggregationText(aggregation, attributes, t), values: result.values.map((row) => row[0]) }], omittedSeries: 0 }
  }
  const series = result.columns.map((column, index) => ({
    name: keyText(dimensions[1], kinds[1], column, language, t),
    values: result.values.map((row) => row[index]),
  }))
  return { categories, positions, neutral, series: series.slice(0, MAX_SERIES), omittedSeries: Math.max(0, series.length - MAX_SERIES) }
}
