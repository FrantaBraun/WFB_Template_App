/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

// Auto-discovers every src/modules/<key>/index.tsx via Vite's import.meta.glob
// (eager, so this runs once at app startup, no per-module import wiring
// needed elsewhere) and registers each discovered module's i18n bundles
// immediately - unconditionally, regardless of enabled state, same as the
// backend registers every module's DB tables regardless of enabled state
// (see app/modules/registry.py). Which modules are actually enabled
// (public/modules.json) only gates which routes/nav items get rendered -
// see useEnabledModules in moduleStore.ts.
//
// Only the application's entry point imports this file (App.tsx, Footer.tsx
// via the hook below): modules and the pages that use them import
// moduleStore.ts instead, so that this file - which imports every module -
// never ends up in an import cycle with one of them.
import i18n from '../i18n'
import { registerModules } from './moduleStore'
import type { ModuleDefinition } from './types'

export { findMissingRequirements, getEnabledModules, useEnabledModules } from './moduleStore'

const moduleFiles = import.meta.glob<{ default: ModuleDefinition }>('./*/index.tsx', { eager: true })

const allModules: ModuleDefinition[] = Object.entries(moduleFiles)
  .map(([path, mod]) => {
    if (!mod.default) {
      console.warn(`${path}: module has no default export - skipped`)
      return null
    }
    return mod.default
  })
  .filter((module): module is ModuleDefinition => module !== null)

registerModules(allModules)

for (const module of allModules) {
  if (module.locales?.cs) i18n.addResourceBundle('cs', module.key, module.locales.cs)
  if (module.locales?.en) i18n.addResourceBundle('en', module.key, module.locales.en)
}
