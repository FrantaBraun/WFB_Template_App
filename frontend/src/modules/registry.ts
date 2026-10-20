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
// see useEnabledModules below.
import { useEffect, useState } from 'react'
import i18n from '../i18n'
import type { ModuleDefinition } from './types'

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

for (const module of allModules) {
  if (module.locales?.cs) i18n.addResourceBundle('cs', module.key, module.locales.cs)
  if (module.locales?.en) i18n.addResourceBundle('en', module.key, module.locales.en)
}

let enabledKeysPromise: Promise<Set<string>> | null = null

/**
 * One message per enabled module whose `requires` isn't satisfied - either
 * the required module isn't enabled or no module with that key exists (a
 * typo). Pure, so it can be reasoned about (and reused) without the console.
 */
export function findMissingRequirements(modules: ModuleDefinition[], enabledKeys: Set<string>): string[] {
  const known = new Set(modules.map((module) => module.key))
  const problems: string[] = []
  for (const module of modules) {
    if (!enabledKeys.has(module.key)) continue
    for (const required of module.requires ?? []) {
      if (!known.has(required)) problems.push(`module "${module.key}" requires unknown module "${required}"`)
      else if (!enabledKeys.has(required)) {
        problems.push(`module "${module.key}" is enabled but requires "${required}", which is not enabled`)
      }
    }
  }
  return problems
}

async function loadEnabledKeys(): Promise<Set<string>> {
  const resp = await fetch('/modules.json')
  if (!resp.ok) return new Set()
  const config: { enabled?: string[] } = await resp.json()
  const keys = new Set(config.enabled ?? [])
  // Once per page load, when the list is first read: a warning, never a block.
  for (const problem of findMissingRequirements(allModules, keys)) console.warn(problem)
  return keys
}

/** Discovered modules whose key is listed in public/modules.json's `enabled` array. */
export async function getEnabledModules(): Promise<ModuleDefinition[]> {
  enabledKeysPromise ??= loadEnabledKeys()
  const enabledKeys = await enabledKeysPromise
  return allModules.filter((module) => enabledKeys.has(module.key))
}

/** React hook wrapping getEnabledModules() for components that render module routes/nav. */
export function useEnabledModules(): ModuleDefinition[] {
  const [modules, setModules] = useState<ModuleDefinition[]>([])

  useEffect(() => {
    let cancelled = false
    getEnabledModules().then((found) => {
      if (!cancelled) setModules(found)
    })
    return () => {
      cancelled = true
    }
  }, [])

  return modules
}
