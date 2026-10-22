/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

// What a table can be filtered and sorted by, and what the filter rows of the
// content page hold. Mirrors the backend's filters.py (OPERATORS, which fields
// there are): the server validates every definition and answers 422 for one it
// does not accept, so a mismatch here shows as an error, never as wrong data.

import { newId, type Attribute, type FilterDefinition, type RefInfo } from './api'

export type FieldKind = 'text' | 'number' | 'boolean' | 'date' | 'datetime' | 'reference' | 'timestamp'

export const OPERATORS: Record<FieldKind, readonly string[]> = {
  text: ['contains', 'equals', 'empty', 'not_empty'],
  number: ['eq', 'ne', 'lt', 'lte', 'gt', 'gte', 'between', 'empty', 'not_empty'],
  boolean: ['equals', 'empty', 'not_empty'],
  date: ['eq', 'before', 'after', 'between', 'empty', 'not_empty'],
  datetime: ['eq', 'before', 'after', 'between', 'empty', 'not_empty'],
  reference: ['equals', 'empty', 'not_empty'],
  timestamp: ['eq', 'before', 'after', 'between'],
}

const NO_VALUE = new Set(['empty', 'not_empty'])
const FILTERABLE_TYPES = new Set(['text', 'number', 'boolean', 'date', 'datetime', 'reference'])

export interface FieldInfo {
  /** `name`, `slug`, `created_on` or an attribute id. */
  key: string
  /** The attribute's own name; undefined for the system fields (the caller translates those). */
  label?: string
  kind: FieldKind
  /** For a reference: the table it points at. */
  tableId?: string
}

/** The fields a table can be filtered and sorted by: the system ones, then its attributes of a simple type. */
export function fieldsFor(attributes: Attribute[]): FieldInfo[] {
  return [
    { key: 'name', kind: 'text' },
    { key: 'slug', kind: 'text' },
    { key: 'created_on', kind: 'timestamp' },
    ...attributes
      .filter((attribute) => FILTERABLE_TYPES.has(attribute.type))
      .map((attribute) => ({ key: attribute.id, label: attribute.name, kind: attribute.type as FieldKind, tableId: attribute.config.table_id })),
  ]
}

/** One filter row as the page holds it. Values are text, as typed; a reference also keeps what is known about its record. */
export interface ConditionDraft {
  id: string
  field: string
  op: string
  value: string
  value2: string
  refInfo?: RefInfo
}

export function newCondition(field: FieldInfo): ConditionDraft {
  return { id: newId(), field: field.key, op: OPERATORS[field.kind][0], value: '', value2: '' }
}

export function operatorNeedsValue(op: string): boolean {
  return !NO_VALUE.has(op)
}

export function operatorNeedsTwoValues(op: string): boolean {
  return op === 'between'
}

function convert(kind: FieldKind, text: string): string | number | boolean | null {
  const trimmed = text.trim()
  if (trimmed === '') return null
  if (kind === 'number') {
    const number = Number(trimmed)
    return Number.isFinite(number) ? number : null
  }
  if (kind === 'boolean') return trimmed === 'true'
  return trimmed
}

export interface ConditionRequest {
  field: string
  op: string
  value?: string | number | boolean
  value2?: string | number | boolean
}

/** The condition to send, or null while the row is not complete (an empty value, say) - such a row is simply not applied yet. */
export function conditionToRequest(draft: ConditionDraft, field: FieldInfo | undefined): ConditionRequest | null {
  if (!field || !OPERATORS[field.kind].includes(draft.op)) return null
  if (!operatorNeedsValue(draft.op)) return { field: draft.field, op: draft.op }
  const value = convert(field.kind, draft.value)
  if (value === null) return null
  if (!operatorNeedsTwoValues(draft.op)) return { field: draft.field, op: draft.op, value }
  const value2 = convert(field.kind, draft.value2)
  return value2 === null ? null : { field: draft.field, op: draft.op, value, value2 }
}

export interface Sort {
  field: string
  dir: 'asc' | 'desc'
}

/** The sort after a click on a column header: ascending, then descending, then back to the default. */
export function nextSort(current: Sort | null, field: string): Sort | null {
  if (current?.field !== field) return { field, dir: 'asc' }
  return current.dir === 'asc' ? { field, dir: 'desc' } : null
}

// --- Saved filters ------------------------------------------------------------------

/** The definition of what the page shows now (what a saved filter would store): only complete rows count. */
export function buildDefinition(applied: ConditionRequest[], sort: Sort | null, includeDeleted: boolean, search: string): FilterDefinition {
  return { conditions: applied, sort, include_deleted: includeDeleted, q: search.trim() || null }
}

function sameValue(a: unknown, b: unknown): boolean {
  return (a ?? null) === (b ?? null)
}

/** Whether two definitions filter and sort the same way (the server's JSON key order is not ours). */
export function sameDefinition(a: FilterDefinition, b: FilterDefinition): boolean {
  if (a.conditions.length !== b.conditions.length) return false
  const sameConditions = a.conditions.every((condition, index) => {
    const other = b.conditions[index]
    return condition.field === other.field && condition.op === other.op && sameValue(condition.value, other.value) && sameValue(condition.value2, other.value2)
  })
  return sameConditions && sameValue(a.sort?.field, b.sort?.field) && sameValue(a.sort?.dir, b.sort?.dir) && a.include_deleted === b.include_deleted && sameValue(a.q, b.q)
}

function valueText(value: unknown): string {
  if (value === undefined || value === null) return ''
  return typeof value === 'boolean' ? (value ? 'true' : 'false') : String(value)
}

/** The filter rows of a saved definition, to put on the page. */
export function definitionToDrafts(definition: FilterDefinition, refs: Record<string, RefInfo>): ConditionDraft[] {
  return definition.conditions.map((condition) => ({
    id: newId(),
    field: condition.field,
    op: condition.op,
    value: valueText(condition.value),
    value2: valueText(condition.value2),
    refInfo: typeof condition.value === 'string' ? refs[condition.value] : undefined,
  }))
}
