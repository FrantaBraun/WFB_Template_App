/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { usePublicData, type ProviderInfo } from '../data'

/**
 * Who runs the site, as the backend has it configured in .env (PROVIDER_*):
 * GET /api/modules/freelancer/provider. Undefined-like (`null`) while loading
 * or when the backend does not answer - the legal pages then show the same
 * "details missing" notice as for an unconfigured provider.
 */
export function useProvider(): ProviderInfo | null {
  return usePublicData<ProviderInfo>('/api/modules/freelancer/provider')
}
