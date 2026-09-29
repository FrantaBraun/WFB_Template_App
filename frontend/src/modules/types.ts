/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import type { ReactElement } from 'react'
import { SUPPORTED_LANGUAGES } from '../i18n'

type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number]

/** One route a module contributes, in the shape react-router-dom's <Route> expects. */
export interface ModuleRoute {
  path: string
  element: ReactElement
}

/**
 * One nav-bar link a module contributes. labelKey must be namespaced as
 * "<moduleKey>:<key>" (i18next's default nsSeparator) so it resolves against
 * that module's own resource bundle - see ModuleDefinition.locales below.
 */
export interface ModuleNavItem {
  to: string
  labelKey: string
}

/** Contract a feature module's src/modules/<key>/index.tsx must default-export. */
export interface ModuleDefinition {
  /** Must match the module's folder name under src/modules/ and public/modules.json's `enabled` list. */
  key: string
  routes: ModuleRoute[]
  nav?: ModuleNavItem[]
  /** Links rendered in the shared footer (e.g. legal pages) - same labelKey namespacing rule as `nav`. */
  footerLinks?: ModuleNavItem[]
  /** One element always rendered in the shared header (e.g. a notification bell), independent of routes/nav. */
  headerWidget?: ReactElement
  /** Registered as an i18next resource bundle under the `key` namespace, per shipped language. */
  locales?: Partial<Record<SupportedLanguage, Record<string, unknown>>>
}
