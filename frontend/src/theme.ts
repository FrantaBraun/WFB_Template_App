/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { apiFetch } from './api/client'

/**
 * Fetches the current group-attributes, merges in the given darkMode value,
 * and PATCHes the full user_data object back - PATCH replaces the whole
 * object, so sending just {darkMode} would silently drop every other stored
 * attribute (e.g. config.json-driven ones). Best-effort: swallows failures,
 * since the local theme (via ThemeContext) already applied regardless of
 * whether the profile save succeeds.
 */
export async function persistDarkModePreference(groupId: string, darkMode: boolean): Promise<void> {
  try {
    const getResp = await apiFetch(`/api/auth/me/group-attributes/${groupId}`)
    const current = getResp.ok ? await getResp.json() : null
    const userData = { ...(current?.user_data ?? {}), darkMode }
    await apiFetch(`/api/auth/me/group-attributes/${groupId}`, {
      method: 'PATCH',
      body: JSON.stringify({ user_data: userData }),
    })
  } catch {
    // best-effort profile sync - local theme is already applied either way
  }
}
