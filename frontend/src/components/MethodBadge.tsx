/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

const READ = 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300'
const CREATE = 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300'
const MODIFY = 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300'
const REMOVE = 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'
const STREAM = 'bg-violet-100 text-violet-800 dark:bg-violet-900/40 dark:text-violet-300'
const OTHER = 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300'

/**
 * The colour of an endpoint's method label: the HTTP methods of an OpenAPI
 * operation or a Postman request, the operation types of a GraphQL root field
 * (QUERY / MUTATION / SUBSCRIPTION) and the directions of an AsyncAPI
 * operation (PUBLISH / SUBSCRIBE in 2.x, SEND / RECEIVE in 3.x). Anything else
 * is grey.
 */
const STYLES: Record<string, string> = {
  GET: READ,
  HEAD: READ,
  OPTIONS: READ,
  QUERY: READ,
  POST: CREATE,
  MUTATION: CREATE,
  PUBLISH: CREATE,
  SEND: CREATE,
  PUT: MODIFY,
  PATCH: MODIFY,
  RECEIVE: MODIFY,
  DELETE: REMOVE,
  SUBSCRIPTION: STREAM,
  SUBSCRIBE: STREAM,
}

export default function MethodBadge({ method }: { method: string }) {
  return (
    <span
      className={`inline-block min-w-[4.5rem] shrink-0 rounded px-2 py-0.5 text-center font-mono text-xs font-semibold ${STYLES[method.toUpperCase()] ?? OTHER}`}
    >
      {method}
    </span>
  )
}
