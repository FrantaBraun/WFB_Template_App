/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import usePageMeta from '../../hooks/usePageMeta'
import { repositoryPath } from './api'
import RepositoryForm from './RepositoryForm'
import { BackLink, RepositoryGate, cardClass } from './ui'

/** /repository/new - the form of a new repository. */
export default function RepositoryFormPage() {
  const { t } = useTranslation('repository')
  const navigate = useNavigate()
  usePageMeta({ title: t('repository.form.newTitle'), noindex: true })

  return (
    <RepositoryGate>
      <div className="mx-auto max-w-2xl px-3 py-10 text-slate-900 dark:text-slate-100 sm:px-6">
        <BackLink to="/">{t('common.home')}</BackLink>
        <h1 className="mb-6 mt-2 text-3xl font-semibold tracking-tight">{t('repository.form.newTitle')}</h1>
        <div className={`${cardClass} p-5`}>
          <RepositoryForm onSaved={(saved) => navigate(repositoryPath(saved.slug))} onCancel={() => navigate('/')} />
        </div>
      </div>
    </RepositoryGate>
  )
}
