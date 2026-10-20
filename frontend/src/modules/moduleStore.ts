/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

// What is known about the modules at run time: the discovered list (handed
// over by registry.ts) and which of them public/modules.json enables.
//
// This is deliberately a separate file from registry.ts. registry.ts
// imports every module's index.tsx (import.meta.glob, eager), and a module
// that renders <ModuleSlot> - or a page that imports a module's exports, as
// an application's home page imports the event calendar - needs the enabled
// list in turn. If that code imported registry.ts it would form a cycle, and
// whichever of the two a page happened to import first decided whether the
// app started or died with "Cannot access 'default' before initialization".
// So anything that a module (or a page importing one) uses imports THIS file;
// only the application's entry point imports registry.ts, which fills it.
import { useEffect, useState } from 'react'
import type { ModuleDefinition } from './types'

let allModules: ModuleDefinition[] = []
let enabledKeysPromise: Promise<Set<string>> | null = null

/** Called once by registry.ts with every discovered module, before anything asks which are enabled. */
export function registerModules(modules: ModuleDefinition[]): void {
  allModules = modules
}

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

/** React hook wrapping getEnabledModules() for components that render module routes/nav/slots. */
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
