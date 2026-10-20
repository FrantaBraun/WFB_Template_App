/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import type { Question } from './api'
import { visibleQuestions } from './conditions'

/**
 * What FormRenderer holds for each question while the visitor types: text,
 * radio, date, time and datetime a string, checkbox a list of option ids, and
 * number the string as typed (an input can't hold a half-typed number as a
 * number). A key that is missing means "not touched".
 */
export type FormValues = Record<string, string | string[]>

/** The typed answer for a question: a number as a number, "" as "no answer". */
export function typedValue(question: Pick<Question, 'type'>, value: string | string[] | undefined): unknown {
  if (value === undefined) return undefined
  if (question.type === 'number') {
    if (typeof value !== 'string' || value.trim() === '') return undefined
    const number = Number(value)
    return Number.isFinite(number) ? number : undefined
  }
  return value
}

export function typedValues(questions: Question[], values: FormValues): Record<string, unknown> {
  const typed: Record<string, unknown> = {}
  for (const question of questions) {
    const value = typedValue(question, values[question.id])
    if (value !== undefined) typed[question.id] = value
  }
  return typed
}

/** The questions the visitor should currently see. */
export function shownQuestions(questions: Question[], values: FormValues): Question[] {
  return visibleQuestions(questions, typedValues(questions, values))
}

/**
 * The answers to send to the server: only the questions currently shown and
 * only those answered, typed (numbers as numbers). What was typed into a
 * question that has since been hidden again is left out - the server would
 * throw it away anyway.
 */
export function collectAnswers(questions: Question[], values: FormValues): Record<string, unknown> {
  const typed = typedValues(questions, values)
  const answers: Record<string, unknown> = {}
  for (const question of visibleQuestions(questions, typed)) {
    const value = typed[question.id]
    if (value === undefined || value === '' || (Array.isArray(value) && value.length === 0)) continue
    answers[question.id] = value
  }
  return answers
}
