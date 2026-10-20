/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEnabledModules } from './registry'

/**
 * Renders what every enabled module contributes to the slot `name` (its
 * `slots[name]` component), in module-folder-name order, each given
 * `context` as a prop. Renders nothing when no enabled module contributes -
 * a page with a slot looks exactly like one without it until another module
 * is switched on.
 */
export default function ModuleSlot({ name, context }: { name: string; context?: Record<string, unknown> }) {
  const modules = useEnabledModules()
  return (
    <>
      {modules.map((module) => {
        const Contribution = module.slots?.[name]
        return Contribution ? <Contribution key={module.key} context={context ?? {}} /> : null
      })}
    </>
  )
}
