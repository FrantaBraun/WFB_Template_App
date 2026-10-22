/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

// The colour schemes of a repository. The backend validates only the keys
// (app/modules/repository/logic.py COLOR_SCHEMES); the colours - a light and a
// dark variant of each - are in repository.css, applied through the class
// schemeClass() returns. `swatch` is only what the picker draws.

export const COLOR_SCHEMES = ['blue', 'teal', 'green', 'amber', 'orange', 'red', 'pink', 'violet'] as const
export type ColorScheme = (typeof COLOR_SCHEMES)[number]
export const DEFAULT_SCHEME: ColorScheme = 'blue'

export const SCHEME_SWATCH: Record<ColorScheme, string> = {
  blue: '#2563eb',
  teal: '#0f766e',
  green: '#15803d',
  amber: '#b45309',
  orange: '#c2410c',
  red: '#dc2626',
  pink: '#db2777',
  violet: '#7c3aed',
}

export function isScheme(key: string): key is ColorScheme {
  return (COLOR_SCHEMES as readonly string[]).includes(key)
}

/** The class that sets the --repo-* custom properties for a scheme key (an unknown one falls back to the default). */
export function schemeClass(key: string): string {
  return `repo-scheme repo-scheme-${isScheme(key) ? key : DEFAULT_SCHEME}`
}
