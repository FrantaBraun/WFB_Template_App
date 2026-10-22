/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { createContext, useContext } from 'react'
import type { RepositoryDetail } from './api'

export interface AreaContextValue {
  /** The opened repository with its tables (the side menu). */
  repository: RepositoryDetail
  /** Loads the repository again - after a table was added, renamed, reordered or deleted. */
  reload: () => Promise<void>
}

export const AreaContext = createContext<AreaContextValue | null>(null)

/** The repository the current page belongs to; only valid inside RepositoryArea. */
export function useRepositoryArea(): AreaContextValue {
  const value = useContext(AreaContext)
  if (!value) throw new Error('useRepositoryArea() must be used inside <RepositoryArea>')
  return value
}
