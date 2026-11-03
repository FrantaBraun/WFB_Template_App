/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { apiFetch } from '../api/client'

export type SpecFormat = 'json' | 'yaml' | 'graphql'

export class SpecFetchError extends Error {
  status: number

  constructor(status: number) {
    super(`Spec request failed with status ${status}`)
    this.status = status
  }
}

/**
 * Fetches one version's spec file exactly as it was stored. This has to go
 * through apiFetch: the backend authenticates with a bearer token only, and a
 * plain `<a href>` navigation never sends one, so any document that isn't
 * public answered that link with a 404 even for its own team's members. The
 * format comes from the response's Content-Type, which the backend derives
 * from the stored version's format (GraphQL SDL is neither JSON nor YAML).
 */
export async function fetchVersionSpec(documentId: string, versionId: string): Promise<{ blob: Blob; format: SpecFormat }> {
  const resp = await apiFetch(`/api/api-docs/${documentId}/versions/${versionId}/spec`)
  if (!resp.ok) throw new SpecFetchError(resp.status)
  const contentType = resp.headers.get('Content-Type') ?? ''
  const format: SpecFormat = contentType.includes('json') ? 'json' : contentType.includes('graphql') ? 'graphql' : 'yaml'
  return { blob: await resp.blob(), format }
}

function toFileName(baseName: string, format: SpecFormat): string {
  const cleaned = baseName.replace(/[\\/:*?"<>|\u0000-\u001f]/g, '_').replace(/\s+/g, ' ').trim().slice(0, 120)
  return `${cleaned || 'specification'}.${format}`
}

/** Hands an in-memory file to the browser as a download, then releases the object URL. */
export function saveSpecBlob(blob: Blob, baseName: string, format: SpecFormat): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = toFileName(baseName, format)
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export async function downloadVersionSpec(documentId: string, versionId: string, baseName: string): Promise<void> {
  const { blob, format } = await fetchVersionSpec(documentId, versionId)
  saveSpecBlob(blob, baseName, format)
}

/** One endpoint of a version (backend EndpointOut): an HTTP method and path, an AsyncAPI direction and channel, or a GraphQL operation type and field. */
export interface OutlineEndpoint {
  method: string
  path: string
  name: string | null
  description: string | null
  tags: string[]
  deprecated: boolean
  operation_id: string | null
}

/** What a stored version contains as a list of endpoints (backend VersionOutlineOut). */
export interface VersionOutline {
  spec_type: string
  title: string | null
  version: string
  endpoints: OutlineEndpoint[]
}

/**
 * The endpoints of one version - how a document of a kind that has no rendered
 * documentation here (AsyncAPI, Postman, GraphQL) is read. Same visibility as
 * the spec file; a 422 means the stored file no longer parses.
 */
export async function fetchVersionOutline(documentId: string, versionId: string): Promise<VersionOutline> {
  const resp = await apiFetch(`/api/api-docs/${documentId}/versions/${versionId}/outline`)
  if (!resp.ok) throw new SpecFetchError(resp.status)
  return resp.json()
}
