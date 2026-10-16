/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { Component, lazy, Suspense, useEffect, useState, type ErrorInfo, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { load as parseYaml } from 'js-yaml'
import usePageMeta from '../hooks/usePageMeta'
import { fetchVersionSpec, saveSpecBlob, SpecFetchError, type SpecFormat } from '../utils/versionSpec'

// Each viewer library is large, so they load only when that viewer is shown -
// opening "Docs" never downloads ReDoc and vice versa, and neither weighs on
// the rest of the app.
const SwaggerViewer = lazy(() => import('../components/spec/SwaggerViewer'))
const RedocViewer = lazy(() => import('../components/spec/RedocViewer'))

type ViewerKind = 'docs' | 'redoc'

interface LoadedSpec {
  blob: Blob
  format: SpecFormat
  spec: Record<string, unknown>
}

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; reason: 'notFound' | 'invalid' | 'failed' }
  | ({ status: 'ready' } & LoadedSpec)

async function loadSpec(documentId: string, versionId: string): Promise<LoadedSpec> {
  const { blob, format } = await fetchVersionSpec(documentId, versionId)
  const text = await blob.text()
  const parsed: unknown = format === 'json' ? JSON.parse(text) : parseYaml(text)
  if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) throw new SyntaxError('Spec is not an object')
  return { blob, format, spec: parsed as Record<string, unknown> }
}

/**
 * A spec is untrusted third-party content, and a viewer library can still
 * throw while rendering a malformed one - without a boundary that would
 * unmount the whole app instead of just this panel.
 */
class ViewerErrorBoundary extends Component<{ children: ReactNode; fallback: ReactNode }, { failed: boolean }> {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Spec viewer failed to render', error, info.componentStack)
  }

  render() {
    return this.state.failed ? this.props.fallback : this.props.children
  }
}

/**
 * Renders one stored version of a document's spec in Swagger UI ("Docs") or
 * ReDoc. The spec is fetched through apiFetch (see utils/versionSpec.ts for
 * why that matters) and parsed here, then handed to the viewer as an object,
 * so the viewers never make a request of their own for it.
 */
export default function VersionSpecViewer() {
  const { t } = useTranslation()
  const { id, versionId } = useParams<{ id: string; versionId: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const [state, setState] = useState<LoadState>({ status: 'loading' })
  usePageMeta({ title: t('apiDocs.viewer.pageTitle') })

  const viewer: ViewerKind = searchParams.get('viewer') === 'redoc' ? 'redoc' : 'docs'

  useEffect(() => {
    if (!id || !versionId) return
    let cancelled = false
    setState({ status: 'loading' })
    loadSpec(id, versionId)
      .then((loaded) => {
        if (!cancelled) setState({ status: 'ready', ...loaded })
      })
      .catch((err: unknown) => {
        if (cancelled) return
        if (err instanceof SpecFetchError) setState({ status: 'error', reason: err.status === 404 ? 'notFound' : 'failed' })
        else if (err instanceof SyntaxError || (err instanceof Error && err.name === 'YAMLException')) setState({ status: 'error', reason: 'invalid' })
        else setState({ status: 'error', reason: 'failed' })
      })
    return () => {
      cancelled = true
    }
  }, [id, versionId])

  const info = state.status === 'ready' ? (state.spec.info as { title?: unknown; version?: unknown } | undefined) : undefined
  const specTitle = typeof info?.title === 'string' ? info.title : null
  const specVersion = typeof info?.version === 'string' || typeof info?.version === 'number' ? String(info.version) : null

  function handleDownload() {
    if (state.status !== 'ready') return
    saveSpecBlob(state.blob, [specTitle, specVersion].filter(Boolean).join(' '), state.format)
  }

  const toggleClass = (active: boolean) =>
    `rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
      active
        ? 'bg-slate-900 text-slate-100 dark:bg-slate-100 dark:text-slate-900'
        : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
    }`

  const viewerFallback = <p className="p-6 text-sm text-red-600">{t('apiDocs.viewer.renderError')}</p>

  return (
    <div className="mx-auto w-full max-w-[1400px] space-y-4 px-4 py-6 text-slate-900 dark:text-slate-100 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <Link
            to={id ? `/api-docs/${id}` : '/api-docs'}
            className="text-sm text-slate-600 underline hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100"
          >
            {t('apiDocs.viewer.back')}
          </Link>
          {state.status === 'ready' && (
            <h1 className="mt-1 truncate text-xl font-semibold tracking-tight">
              {specTitle ?? t('apiDocs.viewer.untitled')}
              {specVersion && <span className="ml-2 text-base font-normal text-slate-500 dark:text-slate-400">{specVersion}</span>}
            </h1>
          )}
        </div>

        {state.status === 'ready' && (
          <div className="flex flex-wrap items-center gap-2">
            <div role="group" aria-label={t('apiDocs.viewer.viewerLabel')} className="flex gap-1 rounded-xl border border-slate-200 p-1 dark:border-slate-700">
              <button type="button" aria-pressed={viewer === 'docs'} onClick={() => setSearchParams({ viewer: 'docs' }, { replace: true })} className={toggleClass(viewer === 'docs')}>
                {t('apiDocs.viewer.docs')}
              </button>
              <button type="button" aria-pressed={viewer === 'redoc'} onClick={() => setSearchParams({ viewer: 'redoc' }, { replace: true })} className={toggleClass(viewer === 'redoc')}>
                {t('apiDocs.viewer.redoc')}
              </button>
            </div>
            <button
              type="button"
              onClick={handleDownload}
              title={t('apiDocs.viewer.downloadTitle')}
              className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              {t('apiDocs.viewer.download')}
            </button>
          </div>
        )}
      </div>

      {state.status === 'loading' && <p className="text-sm text-slate-600 dark:text-slate-400">{t('apiDocs.viewer.loading')}</p>}
      {state.status === 'error' && (
        <p className="text-sm text-red-600 dark:text-red-400">{t(`apiDocs.viewer.error.${state.reason}`)}</p>
      )}
      {state.status === 'ready' && (
        <div className="min-h-[60vh] rounded-2xl border border-slate-200 bg-white text-slate-900 dark:border-slate-700">
          <ViewerErrorBoundary key={viewer} fallback={viewerFallback}>
            <Suspense fallback={<p className="p-6 text-sm text-slate-500">{t('apiDocs.viewer.loadingViewer')}</p>}>
              {viewer === 'docs' ? <SwaggerViewer spec={state.spec} /> : <RedocViewer spec={state.spec} />}
            </Suspense>
          </ViewerErrorBoundary>
        </div>
      )}
    </div>
  )
}
