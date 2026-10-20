/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import type { ComponentType, ReactElement } from 'react'
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

/**
 * A component a module contributes to a named slot another module renders
 * with <ModuleSlot name="..." context={...} />. It receives that call's
 * `context` as one prop - each slot documents the shape it passes (`any`
 * here because one slots map holds components for differently-shaped slots).
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type ModuleSlotComponent = ComponentType<{ context: any }>

/** Contract a feature module's src/modules/<key>/index.tsx must default-export. */
export interface ModuleDefinition {
  /** Must match the module's folder name under src/modules/ and public/modules.json's `enabled` list. */
  key: string
  /**
   * Keys of other modules this one only works with. Advisory, like the
   * backend manifest's `requires`: enabling a module without them logs a
   * console warning once (see registry.ts), it never hides or disables anything.
   */
  requires?: string[]
  routes: ModuleRoute[]
  /**
   * Components this module contributes to slots rendered by other modules,
   * keyed by slot name (e.g. "article.detail"). A module defines the slots
   * it renders by placing <ModuleSlot name="..." /> in its pages and
   * documenting the name and `context` shape next to it; the slot lets a
   * module built on top of another extend its pages without the lower one
   * having to know about it. A disabled module contributes nothing.
   */
  slots?: Record<string, ModuleSlotComponent>
  nav?: ModuleNavItem[]
  /** Links rendered in the shared footer (e.g. legal pages) - same labelKey namespacing rule as `nav`. */
  footerLinks?: ModuleNavItem[]
  /** One element always rendered in the shared header (e.g. a notification bell), independent of routes/nav. */
  headerWidget?: ReactElement
  /** Registered as an i18next resource bundle under the `key` namespace, per shipped language. */
  locales?: Partial<Record<SupportedLanguage, Record<string, unknown>>>
}
