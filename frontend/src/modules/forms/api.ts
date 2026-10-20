/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { apiFetch } from '../../api/client'
import type { Condition, QuestionType } from './conditions'

export { OPERATORS_BY_TYPE, isAnswered, visibleQuestions } from './conditions'
export type { Condition, Operator, QuestionType } from './conditions'

export const API_BASE = '/api/modules/forms'

export const QUESTION_TYPES: QuestionType[] = ['text', 'number', 'radio', 'checkbox', 'date', 'time', 'datetime']

export interface Option {
  id: string
  label: string
}

/** What a question's type needs, as the server stores it (see logic.py): only the keys of its own type are set. */
export interface QuestionConfig {
  options?: Option[]
  min_select?: number
  max_select?: number | null
  multiline?: boolean
  min_length?: number
  max_length?: number
  regex?: string | null
  kind?: 'integer' | 'decimal'
  min?: number | string | null
  max?: number | string | null
}

export interface Question {
  id: string
  position: number
  type: QuestionType
  label: string
  help_text: string
  required: boolean
  config: QuestionConfig
  conditions: Condition[]
}

export interface FormDefinition {
  id: string
  name: string
  created_at: string
  questions: Question[]
}

/** One question as it was worded and answered at the moment of submitting - the snapshot the server stores. */
export interface SubmissionEntry {
  question_id: string
  position: number
  label: string
  type: QuestionType
  shown: boolean
  value: unknown
  /** The value as readable text; an option by its label. */
  display: string
  options: Option[]
}

export interface Submission {
  id: string
  form_id: string
  created_at: string
  answers: SubmissionEntry[]
}

export interface SubmissionPage {
  items: Submission[]
  has_more: boolean
}

export interface OptionStats extends Option {
  count: number
  percent: number
}

export interface QuestionStats {
  question_id: string
  type: QuestionType
  label: string
  position: number
  shown_count: number
  answered_count: number
  options?: OptionStats[]
  average_selected?: number
  numeric?: { min: number; max: number; average: number; median: number }
  range?: { earliest: string; latest: string }
}

export interface FormStatsData {
  submission_count: number
  questions: QuestionStats[]
}

/** A new id for a question or an option; the server takes the id the client chooses. */
export function newId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  // Plain-http pages on a LAN address have no crypto.randomUUID.
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = Math.floor(Math.random() * 16)
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16)
  })
}

/** A short id for an option (letters, digits, - and _ are what the server accepts). */
export function newOptionId(): string {
  return `o${Math.random().toString(36).slice(2, 8)}`
}

export async function fetchJson<T>(path: string, init?: Parameters<typeof apiFetch>[1]): Promise<T> {
  const resp = await apiFetch(path, init)
  if (!resp.ok) {
    let detail: unknown = null
    try {
      detail = (await resp.json()).detail
    } catch {
      // not JSON
    }
    throw Object.assign(new Error(`HTTP ${resp.status}`), { status: resp.status, detail })
  }
  return resp.status === 204 ? (undefined as T) : resp.json()
}

export function formatDateTime(iso: string, language: string): string {
  return new Date(iso).toLocaleString(language, { dateStyle: 'medium', timeStyle: 'short' })
}
