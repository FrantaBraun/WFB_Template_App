/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import SwaggerUI from 'swagger-ui-react'
import 'swagger-ui-react/swagger-ui.css'
import './swagger-viewer.css'

/**
 * Swagger UI rendering of an already-fetched spec object. This is a read-only
 * archive of third-party documentation, not a client for those APIs, so
 * "Try it out" is switched off (an empty supportedSubmitMethods list removes
 * the button) - nothing here should fire requests from this app's origin at
 * whatever servers an untrusted spec happens to list.
 */
export default function SwaggerViewer({ spec }: { spec: object }) {
  return (
    <div className="swagger-viewer">
      <SwaggerUI
        spec={spec}
        supportedSubmitMethods={[]}
        deepLinking={false}
        docExpansion="list"
        defaultModelsExpandDepth={1}
      />
    </div>
  )
}
