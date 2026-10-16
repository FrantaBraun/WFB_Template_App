/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { RedocStandalone } from 'redoc'

/**
 * ReDoc rendering of an already-fetched spec object. untrustedSpec makes
 * ReDoc sanitize every piece of markdown/HTML the spec supplies, which matters
 * because any visitor can open a public document whose spec someone else
 * wrote. ReDoc's own download button is hidden: it would re-serialize the
 * parsed object, while this app's Download button returns the file exactly as
 * it was uploaded.
 */
export default function RedocViewer({ spec }: { spec: object }) {
  return <RedocStandalone spec={spec} options={{ untrustedSpec: true, hideDownloadButton: true }} />
}
