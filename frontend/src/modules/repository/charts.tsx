/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

// The charts of a statistic, drawn as plain SVG (no charting library).
//
// Marks are thin (bars at most 24px, with a 4px rounded data end and a square
// base; lines 2px; markers 8px), separated by 2px of the surface colour (the
// gap between bars and pie slices, the ring around a marker); gridlines and axes
// are hairlines; labels, values and legends wear the ink colours, never a series
// colour - identity comes from the coloured mark beside the text. Series colours
// come from .stat-viz in repository.css, in a fixed order. Every mark has a
// tooltip on hover AND on keyboard focus (the same text is in the table view),
// and a legend is always present for more than one series.

import { useCallback, useEffect, useId, useRef, useState, type KeyboardEvent, type PointerEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { compactNumber, formatValue, niceScale, type ChartData, type ChartSeries } from './statFormat'

export type ChartKind = 'bar' | 'line' | 'pie'

const SERIES_COLOR = (index: number) => `var(--series-${(index % 8) + 1})`
const OTHER_COLOR = 'var(--viz-neutral)'
const FONT = 12
const MAX_LABEL = 24
const CHART_HEIGHT = 260
const BAR_ROW_GAP = 12

function shorten(text: string, max = MAX_LABEL): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text
}

// --- Shared pieces --------------------------------------------------------------------

function useWidth(): [React.RefObject<HTMLDivElement | null>, number] {
  const ref = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(520)
  useEffect(() => {
    const element = ref.current
    if (!element) return
    setWidth(element.clientWidth || 520)
    const observer = new ResizeObserver(() => setWidth(element.clientWidth || 520))
    observer.observe(element)
    return () => observer.disconnect()
  }, [])
  return [ref, Math.max(240, width)]
}

interface TooltipRow {
  /** The series colour, drawn as a short line key. */
  color?: string
  name: string
  value: string
}

interface TooltipState {
  x: number
  y: number
  title: string
  rows: TooltipRow[]
}

function useTooltip() {
  const [tip, setTip] = useState<TooltipState | null>(null)
  const show = useCallback((state: TooltipState) => setTip(state), [])
  const hide = useCallback(() => setTip(null), [])
  return { tip, show, hide }
}

/** Where, inside `container`, a pointer event happened. */
function pointerPosition(event: PointerEvent, container: HTMLElement | null): { x: number; y: number } {
  const box = container?.getBoundingClientRect()
  return { x: event.clientX - (box?.left ?? 0), y: event.clientY - (box?.top ?? 0) }
}

/** Where, inside `container`, the middle of `target` is (for a tooltip on keyboard focus). */
function elementPosition(target: Element, container: HTMLElement | null): { x: number; y: number } {
  const box = target.getBoundingClientRect()
  const outer = container?.getBoundingClientRect()
  return { x: box.left + box.width / 2 - (outer?.left ?? 0), y: box.top + box.height / 2 - (outer?.top ?? 0) }
}

function Tooltip({ tip, width }: { tip: TooltipState | null; width: number }) {
  if (!tip) return null
  const flip = tip.x > width * 0.6
  return (
    <div
      role="tooltip"
      className="pointer-events-none absolute z-10 max-w-[16rem] rounded-lg border border-black/10 bg-white px-3 py-2 text-xs shadow-lg dark:border-white/10 dark:bg-slate-950"
      style={{ left: flip ? undefined : tip.x + 12, right: flip ? width - tip.x + 12 : undefined, top: Math.max(0, tip.y - 12) }}
    >
      <div className="mb-1 font-medium text-[var(--viz-ink-2)]">{tip.title}</div>
      {tip.rows.map((row, index) => (
        <div key={index} className="flex items-center gap-2">
          {row.color && <span className="inline-block h-0.5 w-3 shrink-0 rounded" style={{ backgroundColor: row.color }} aria-hidden="true" />}
          <span className="text-sm font-semibold text-[var(--viz-ink)]">{row.value}</span>
          {row.name && <span className="text-[var(--viz-ink-2)]">{row.name}</span>}
        </div>
      ))}
    </div>
  )
}

/** A legend for two or more series (or the slices of a pie): the coloured mark beside the name in ink. */
function Legend({ items, line = false }: { items: { name: string; color: string; detail?: string }[]; line?: boolean }) {
  return (
    <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-[var(--viz-ink-2)]">
      {items.map((item, index) => (
        <li key={index} className="flex items-center gap-1.5">
          {line ? (
            <span className="inline-block h-0.5 w-4 rounded" style={{ backgroundColor: item.color }} aria-hidden="true" />
          ) : (
            <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: item.color }} aria-hidden="true" />
          )}
          <span>{item.name}</span>
          {item.detail && <span className="text-[var(--viz-muted)]">{item.detail}</span>}
        </li>
      ))}
    </ul>
  )
}

function seriesRange(series: ChartSeries[]): { min: number; max: number } {
  const values = series.flatMap((one) => one.values).filter((value): value is number => value !== null)
  return { min: values.length ? Math.min(...values) : 0, max: values.length ? Math.max(...values) : 0 }
}

// --- Bars ---------------------------------------------------------------------------------

/** A bar from the baseline x0 to x1 with a 4px rounded data end and a square base. */
function barPath(x0: number, x1: number, y: number, thickness: number): string {
  const length = Math.abs(x1 - x0)
  if (length < 0.5) return ''
  const radius = Math.min(4, length / 2, thickness / 2)
  const direction = x1 >= x0 ? 1 : -1
  const tip = x1
  const base = x0
  return [
    `M ${base} ${y}`,
    `H ${tip - direction * radius}`,
    `A ${radius} ${radius} 0 0 ${direction === 1 ? 1 : 0} ${tip} ${y + radius}`,
    `V ${y + thickness - radius}`,
    `A ${radius} ${radius} 0 0 ${direction === 1 ? 1 : 0} ${tip - direction * radius} ${y + thickness}`,
    `H ${base}`,
    'Z',
  ].join(' ')
}

/** Horizontal bars: a row per category (a cluster of bars when there are several series). */
export function BarChart({ data, language }: { data: ChartData; language: string }) {
  const { t } = useTranslation('repository')
  const [ref, width] = useWidth()
  const { tip, show, hide } = useTooltip()
  const [active, setActive] = useState<number | null>(null)
  const { categories, series } = data

  const labelWidth = Math.min(width * 0.4, Math.max(...categories.map((category) => shorten(category).length), 4) * 6.4 + 12)
  const left = labelWidth
  const right = 56
  const top = 24
  const plotWidth = Math.max(40, width - left - right)
  const { min, max } = seriesRange(series)
  const scale = niceScale(min, max)
  const x = (value: number) => left + ((value - scale.min) / (scale.max - scale.min || 1)) * plotWidth
  const thickness = series.length === 1 ? 20 : series.length <= 3 ? 14 : 10
  const slot = series.length * thickness + (series.length - 1) * 2 + BAR_ROW_GAP
  const height = top + categories.length * slot + 8
  const labelValues = series.length === 1 && categories.length <= 12

  function describe(index: number): TooltipState & { x: number; y: number } {
    return {
      x: 0,
      y: 0,
      title: categories[index],
      rows: series.map((one, seriesIndex) => ({
        color: series.length > 1 ? SERIES_COLOR(seriesIndex) : undefined,
        name: series.length > 1 ? one.name : '',
        value: formatValue(one.values[index], language),
      })),
    }
  }

  return (
    <div ref={ref} className="relative max-h-96 overflow-y-auto" onPointerLeave={() => { hide(); setActive(null) }}>
      <svg width={width} height={height} role="img" aria-label={t('statistics.chartLabel', { type: t('statistics.chart.bar') })} className="block">
        {scale.ticks.map((tick) => (
          <g key={tick}>
            <line x1={x(tick)} x2={x(tick)} y1={top - 4} y2={height - 8} stroke="var(--viz-grid)" strokeWidth={1} />
            <text x={x(tick)} y={top - 10} textAnchor="middle" fontSize={FONT} fill="var(--viz-muted)">
              {compactNumber(tick, language)}
            </text>
          </g>
        ))}
        <line x1={x(0)} x2={x(0)} y1={top - 4} y2={height - 8} stroke="var(--viz-axis)" strokeWidth={1} />
        {categories.map((category, index) => {
          const y = top + index * slot
          const groupHeight = slot - BAR_ROW_GAP
          return (
            <g
              key={index}
              tabIndex={0}
              role="img"
              aria-label={`${category}: ${series.map((one) => `${series.length > 1 ? `${one.name} ` : ''}${formatValue(one.values[index], language)}`).join(', ')}`}
              onPointerMove={(event) => { setActive(index); show({ ...describe(index), ...pointerPosition(event, ref.current) }) }}
              onFocus={(event) => { setActive(index); show({ ...describe(index), ...elementPosition(event.currentTarget, ref.current) }) }}
              onBlur={() => { hide(); setActive(null) }}
              className="outline-none focus-visible:[&>rect:first-child]:stroke-[var(--viz-ink)]"
            >
              <rect x={0} y={y - BAR_ROW_GAP / 2} width={width} height={slot} fill={active === index ? 'var(--viz-grid)' : 'transparent'} fillOpacity={0.5} stroke="none" strokeWidth={2} />
              <title>{category}</title>
              <text x={left - 8} y={y + groupHeight / 2 + 4} textAnchor="end" fontSize={FONT} fill="var(--viz-ink-2)">
                {shorten(category)}
              </text>
              {series.map((one, seriesIndex) => {
                const value = one.values[index]
                if (value === null) return null
                const barY = y + seriesIndex * (thickness + 2)
                return (
                  <g key={seriesIndex}>
                    <path d={barPath(x(0), x(value), barY, thickness)} fill={series.length === 1 && data.neutral[index] ? OTHER_COLOR : SERIES_COLOR(seriesIndex)} data-mark />
                    {labelValues && (
                      <text x={value >= 0 ? x(value) + 6 : x(value) - 6} y={barY + thickness / 2 + 4} textAnchor={value >= 0 ? 'start' : 'end'} fontSize={FONT} fill="var(--viz-ink)">
                        {formatValue(value, language)}
                      </text>
                    )}
                  </g>
                )
              })}
            </g>
          )
        })}
      </svg>
      <Tooltip tip={tip} width={width} />
      {series.length > 1 && <Legend items={series.map((one, index) => ({ name: one.name, color: SERIES_COLOR(index) }))} />}
    </div>
  )
}

// --- Lines --------------------------------------------------------------------------------

/** Lines over the categories in their order (which is how a date axis sorts), a crosshair that snaps to the nearest category, and one tooltip for every series. */
export function LineChart({ data, language }: { data: ChartData; language: string }) {
  const { t } = useTranslation('repository')
  const [ref, width] = useWidth()
  const { tip, show, hide } = useTooltip()
  const [active, setActive] = useState<number | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const { categories, series } = data

  const left = 48
  const right = 24
  const top = 12
  const bottom = 36
  const plotWidth = Math.max(40, width - left - right)
  const plotHeight = CHART_HEIGHT - top - bottom
  const { min, max } = seriesRange(series)
  const scale = niceScale(min, max)
  const positions = data.positions
  const firstPosition = positions ? positions[0] : 0
  const lastPosition = positions ? positions[positions.length - 1] : categories.length - 1
  const x = (index: number) => {
    if (categories.length === 1) return left + plotWidth / 2
    const place = positions ? positions[index] : index
    return left + ((place - firstPosition) / (lastPosition - firstPosition || 1)) * plotWidth
  }
  const y = (value: number) => top + plotHeight - ((value - scale.min) / (scale.max - scale.min || 1)) * plotHeight
  // A label only where there is room for it (a date axis can bunch points together).
  const labelled: number[] = []
  categories.forEach((_, index) => {
    if (labelled.length === 0 || x(index) - x(labelled[labelled.length - 1]) >= 76) labelled.push(index)
  })
  const markEveryPoint = categories.length <= 24

  function describe(index: number) {
    return {
      title: categories[index],
      rows: series.map((one, seriesIndex) => ({
        color: SERIES_COLOR(seriesIndex),
        name: series.length > 1 ? one.name : '',
        value: formatValue(one.values[index], language),
      })),
    }
  }

  function nearest(clientX: number): number {
    const box = svgRef.current?.getBoundingClientRect()
    const position = clientX - (box?.left ?? 0)
    let best = 0
    for (let index = 1; index < categories.length; index++) if (Math.abs(x(index) - position) < Math.abs(x(best) - position)) best = index
    return best
  }

  function onMove(event: PointerEvent<SVGSVGElement>) {
    const index = nearest(event.clientX)
    setActive(index)
    show({ ...describe(index), x: x(index), y: pointerPosition(event, ref.current).y })
  }

  function onKey(event: KeyboardEvent<SVGSVGElement>) {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return
    event.preventDefault()
    const next = Math.min(categories.length - 1, Math.max(0, (active ?? (event.key === 'ArrowRight' ? -1 : categories.length)) + (event.key === 'ArrowRight' ? 1 : -1)))
    setActive(next)
    show({ ...describe(next), x: x(next), y: top + 16 })
  }

  /** The line's path, broken wherever a value is missing. */
  function linePath(values: (number | null)[]): string {
    let path = ''
    let pen = false
    values.forEach((value, index) => {
      if (value === null) {
        pen = false
        return
      }
      path += `${pen ? 'L' : 'M'} ${x(index)} ${y(value)} `
      pen = true
    })
    return path
  }

  return (
    <div ref={ref} className="relative">
      <svg
        ref={svgRef}
        width={width}
        height={CHART_HEIGHT}
        role="img"
        tabIndex={0}
        aria-label={t('statistics.chartLabel', { type: t('statistics.chart.line') })}
        onPointerMove={onMove}
        onPointerLeave={() => { hide(); setActive(null) }}
        onKeyDown={onKey}
        onBlur={() => { hide(); setActive(null) }}
        className="block outline-none focus-visible:outline-2 focus-visible:outline-[var(--viz-ink)]"
      >
        {scale.ticks.map((tick) => (
          <g key={tick}>
            <line x1={left} x2={width - right} y1={y(tick)} y2={y(tick)} stroke={tick === 0 ? 'var(--viz-axis)' : 'var(--viz-grid)'} strokeWidth={1} />
            <text x={left - 8} y={y(tick) + 4} textAnchor="end" fontSize={FONT} fill="var(--viz-muted)">
              {compactNumber(tick, language)}
            </text>
          </g>
        ))}
        {labelled.map((index) => (
          <text key={index} x={x(index)} y={CHART_HEIGHT - bottom + 20} textAnchor="middle" fontSize={FONT} fill="var(--viz-muted)">
            {shorten(categories[index], 12)}
          </text>
        ))}
        {active !== null && <line x1={x(active)} x2={x(active)} y1={top} y2={top + plotHeight} stroke="var(--viz-axis)" strokeWidth={1} />}
        {series.map((one, seriesIndex) => (
          <g key={seriesIndex}>
            <path d={linePath(one.values)} fill="none" stroke={SERIES_COLOR(seriesIndex)} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
            {one.values.map((value, index) =>
              value !== null && (markEveryPoint || index === one.values.length - 1 || index === active) ? (
                <circle key={index} cx={x(index)} cy={y(value)} r={4} fill={SERIES_COLOR(seriesIndex)} stroke="var(--viz-surface)" strokeWidth={2} data-mark />
              ) : null,
            )}
          </g>
        ))}
      </svg>
      <Tooltip tip={tip} width={width} />
      {series.length > 1 && <Legend line items={series.map((one, index) => ({ name: one.name, color: SERIES_COLOR(index) }))} />}
    </div>
  )
}

// --- Pie --------------------------------------------------------------------------------------

interface Slice {
  name: string
  value: number
  color: string
}

function slicePath(cx: number, cy: number, radius: number, from: number, to: number): string {
  const point = (angle: number) => `${cx + radius * Math.sin(angle)} ${cy - radius * Math.cos(angle)}`
  const large = to - from > Math.PI ? 1 : 0
  return `M ${cx} ${cy} L ${point(from)} A ${radius} ${radius} 0 ${large} 1 ${point(to)} Z`
}

/** A pie of one series: at most seven named slices and the rest folded into "Other" (in the neutral colour), with a legend that carries the values and shares. */
export function PieChart({ data, language }: { data: ChartData; language: string }) {
  const { t } = useTranslation('repository')
  const [ref, width] = useWidth()
  const { tip, show, hide } = useTooltip()
  const { categories, series } = data
  const parts = categories
    .map((name, index) => ({ name, value: series[0].values[index], neutral: data.neutral[index] }))
    .filter((part): part is { name: string; value: number; neutral: boolean } => part.value !== null && part.value > 0)
  const total = parts.reduce((sum, part) => sum + part.value, 0)
  // The empty group takes no palette slot (it is not a category); more than eight groups fold into "Other".
  const named = parts.filter((part) => !part.neutral)
  const empty = parts.filter((part) => part.neutral)
  const folded = named.length > 8 ? named.slice(7) : []
  const slices: Slice[] = [
    ...(folded.length ? named.slice(0, 7) : named).map((part, index) => ({ name: part.name, value: part.value, color: SERIES_COLOR(index) })),
    ...(folded.length ? [{ name: t('statistics.other'), value: folded.reduce((sum, part) => sum + part.value, 0), color: OTHER_COLOR }] : []),
    ...empty.map((part) => ({ name: part.name, value: part.value, color: OTHER_COLOR })),
  ]
  const size = Math.min(CHART_HEIGHT - 20, width - 16)
  const cx = size / 2 + 8
  const cy = size / 2 + 8
  const radius = size / 2

  if (total === 0) return <p className="text-sm text-[var(--viz-ink-2)]">{t('statistics.pieEmpty')}</p>

  let angle = 0
  const arcs = slices.map((slice) => {
    const from = angle
    angle += (slice.value / total) * Math.PI * 2
    return { slice, from, to: angle }
  })

  function describe(slice: Slice): TooltipState {
    return {
      x: 0,
      y: 0,
      title: slice.name,
      rows: [{ name: `(${((slice.value / total) * 100).toLocaleString(language, { maximumFractionDigits: 1 })} %)`, value: formatValue(slice.value, language) }],
    }
  }

  return (
    <div ref={ref} className="relative" onPointerLeave={hide}>
      <svg width={size + 16} height={size + 16} role="img" aria-label={t('statistics.chartLabel', { type: t('statistics.chart.pie') })} className="mx-auto block">
        {arcs.length === 1 ? (
          <circle
            cx={cx}
            cy={cy}
            r={radius}
            fill={arcs[0].slice.color}
            data-mark
            tabIndex={0}
            role="img"
            aria-label={`${arcs[0].slice.name}: ${formatValue(arcs[0].slice.value, language)}`}
            onPointerMove={(event) => show({ ...describe(arcs[0].slice), ...pointerPosition(event, ref.current) })}
            onFocus={(event) => show({ ...describe(arcs[0].slice), ...elementPosition(event.currentTarget, ref.current) })}
            onBlur={hide}
            className="outline-none"
          />
        ) : (
          arcs.map(({ slice, from, to }, index) => (
            <path
              key={index}
              d={slicePath(cx, cy, radius, from, to)}
              fill={slice.color}
              stroke="var(--viz-surface)"
              strokeWidth={2}
              data-mark
              tabIndex={0}
              role="img"
              aria-label={`${slice.name}: ${formatValue(slice.value, language)}`}
              onPointerMove={(event) => show({ ...describe(slice), ...pointerPosition(event, ref.current) })}
              onFocus={(event) => show({ ...describe(slice), ...elementPosition(event.currentTarget, ref.current) })}
              onBlur={hide}
              className="outline-none focus-visible:stroke-[var(--viz-ink)]"
            />
          ))
        )}
      </svg>
      <Tooltip tip={tip} width={width} />
      <Legend
        items={slices.map((slice) => ({
          name: slice.name,
          color: slice.color,
          detail: `${formatValue(slice.value, language)} (${((slice.value / total) * 100).toLocaleString(language, { maximumFractionDigits: 1 })} %)`,
        }))}
      />
    </div>
  )
}

// --- The dispatcher ------------------------------------------------------------------------------

/** The chart of `kind` for the data; a note when more series were given than the palette has. */
export default function StatChart({ kind, data, language }: { kind: ChartKind; data: ChartData; language: string }): ReactNode {
  const { t } = useTranslation('repository')
  const captionId = useId()
  if (data.categories.length === 0) return <p className="text-sm text-[var(--viz-ink-2)]">{t('statistics.noData')}</p>
  return (
    <figure className="stat-viz m-0" aria-describedby={data.omittedSeries > 0 ? captionId : undefined}>
      {kind === 'pie' ? <PieChart data={data} language={language} /> : kind === 'line' ? <LineChart data={data} language={language} /> : <BarChart data={data} language={language} />}
      {data.omittedSeries > 0 && (
        <figcaption id={captionId} className="mt-1 text-xs text-[var(--viz-muted)]">
          {t('statistics.omittedSeries', { count: data.omittedSeries })}
        </figcaption>
      )}
    </figure>
  )
}
