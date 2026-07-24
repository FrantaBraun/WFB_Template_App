/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useEffect, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { apiFetch } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import usePageMeta from '../hooks/usePageMeta'
import { loadUserAttributes, type UserAttribute } from '../config/userAttributes'
import DynamicAttributeField from '../components/DynamicAttributeField'
import ThemeToggle from '../components/ThemeToggle'
import { applyUserLanguage } from '../i18n'

interface AccountData {
  id: string
  nickname: string | null
  created_at: string
  updated_at: string
}

interface ProfileData {
  application_group_id?: string | null
  [key: string]: unknown
}

type Message = { type: 'success' | 'error'; text: string } | null

const PROFILE_FIELDS = [
  'first_name',
  'last_name',
  'avatar_url',
  'language_code',
  'birth_date',
  'country_code',
] as const

/**
 * Controlled text/date inputs store an unset field as '' since React inputs
 * can't hold null - but the auth service validates fields like birth_date as
 * a real date-or-absent and rejects "" outright. Convert blanks to null right
 * before sending, so an untouched field is omitted upstream instead of
 * erroring.
 */
function blankToNull(form: Record<string, string>): Record<string, string | null> {
  return Object.fromEntries(Object.entries(form).map(([key, value]) => [key, value === '' ? null : value]))
}

/**
 * Two independent save flows that never cross endpoints: the account card
 * (nickname) PATCHes this backend's own local `/api/account/me` table, while
 * the profile card (name/attributes) PATCHes the upstream auth service via
 * `/api/auth/me` and `/api/auth/me/group-attributes/{id}`. Each has its own
 * loading/saving/message state so one failing never blocks the other.
 */
export default function Account() {
  const { t } = useTranslation()
  usePageMeta({ title: t('account.pageTitle'), description: t('account.pageDescription') })
  const { user, loading: authLoading } = useAuth()
  const { darkMode } = useTheme()
  const navigate = useNavigate()

  const [account, setAccount] = useState<AccountData | null>(null)
  const [nickname, setNickname] = useState('')
  const [accountSaving, setAccountSaving] = useState(false)
  const [accountMessage, setAccountMessage] = useState<Message>(null)

  const [profile, setProfile] = useState<ProfileData | null>(null)
  const [profileForm, setProfileForm] = useState<Record<string, string>>({})
  const [attributes, setAttributes] = useState<UserAttribute[]>([])
  const [attributeValues, setAttributeValues] = useState<Record<string, unknown>>({})
  const [groupId, setGroupId] = useState<string | null>(null)
  const [profileSaving, setProfileSaving] = useState(false)
  const [profileMessage, setProfileMessage] = useState<Message>(null)

  useEffect(() => {
    if (!authLoading && !user) {
      navigate('/login', { replace: true })
    }
  }, [authLoading, user, navigate])

  useEffect(() => {
    if (!user) return

    apiFetch('/api/account/me')
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data: AccountData) => {
        setAccount(data)
        setNickname(data.nickname ?? '')
      })
      .catch(() => setAccountMessage({ type: 'error', text: t('account.saveError') }))

    apiFetch('/api/auth/me')
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data: ProfileData) => {
        setProfile(data)
        setProfileForm(
          Object.fromEntries(PROFILE_FIELDS.map((field) => [field, (data[field] as string | null) ?? ''])),
        )
        if (data.application_group_id) setGroupId(data.application_group_id)
      })
      .catch(() => setProfileMessage({ type: 'error', text: t('account.saveError') }))

    loadUserAttributes().then(setAttributes)
  }, [user, t])

  useEffect(() => {
    if (!groupId) return
    apiFetch(`/api/auth/me/group-attributes/${groupId}`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((data: { user_data: Record<string, unknown> | null }) => {
        setAttributeValues(data.user_data ?? {})
      })
      .catch(() => {})
  }, [groupId])

  if (authLoading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-900 dark:text-slate-100">
        <p className="text-sm text-slate-600 dark:text-slate-400">{t('common.loading')}</p>
      </div>
    )
  }

  // What's actually persisted on the profile, per the last group-attributes
  // fetch/toggle - independent of the currently active theme (`darkMode`
  // from useTheme()), which may reflect a locally-cached value that hasn't
  // been reconciled with the server yet. Defaults to false (light), matching
  // the auth service's own stored default for a user who never set this.
  const storedDarkMode = typeof attributeValues.darkMode === 'boolean' ? attributeValues.darkMode : false

  async function handleAccountSubmit(e: FormEvent) {
    e.preventDefault()
    setAccountSaving(true)
    setAccountMessage(null)
    try {
      // Local data only - this call never reaches the auth service.
      const resp = await apiFetch('/api/account/me', {
        method: 'PATCH',
        body: JSON.stringify({ nickname: nickname || null }),
      })
      if (!resp.ok) throw new Error()
      setAccount(await resp.json())
      setAccountMessage({ type: 'success', text: t('account.saveSuccess') })
    } catch {
      setAccountMessage({ type: 'error', text: t('account.saveError') })
    } finally {
      setAccountSaving(false)
    }
  }

  async function handleProfileSubmit(e: FormEvent) {
    e.preventDefault()

    const missing = attributes.filter((attribute) => attribute.required && !attributeValues[attribute.key])
    if (missing.length > 0) {
      const labels = missing.map((attribute) => t(attribute.i18nKey)).join(', ')
      setProfileMessage({ type: 'error', text: `${t('common.requiredFieldsMissing')} (${labels})` })
      return
    }

    setProfileSaving(true)
    setProfileMessage(null)
    try {
      const profileResp = await apiFetch('/api/auth/me', {
        method: 'PATCH',
        body: JSON.stringify(blankToNull(profileForm)),
      })
      if (!profileResp.ok) throw new Error()
      const updatedProfile: ProfileData = await profileResp.json()
      setProfile(updatedProfile)
      // Keep the active UI language in sync if the user just changed their
      // stored preference here, same cascade as on login.
      applyUserLanguage(updatedProfile.language_code as string | null | undefined)

      if (groupId && attributes.length > 0) {
        // PATCH replaces the whole user_data object, so send the full set of
        // known values, not just whichever field changed.
        const attrResp = await apiFetch(`/api/auth/me/group-attributes/${groupId}`, {
          method: 'PATCH',
          body: JSON.stringify({ user_data: attributeValues }),
        })
        if (!attrResp.ok) throw new Error()
      }

      setProfileMessage({ type: 'success', text: t('account.saveSuccess') })
    } catch {
      setProfileMessage({ type: 'error', text: t('account.saveError') })
    } finally {
      setProfileSaving(false)
    }
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 px-6 py-16 text-slate-900 dark:text-slate-100">
      <h1 className="text-2xl font-semibold tracking-tight">{t('account.pageTitle')}</h1>

      <form
        onSubmit={handleAccountSubmit}
        className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900"
      >
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
          {t('account.accountCard.title')}
        </h2>

        <div>
          <label htmlFor="nickname" className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
            {t('account.accountCard.nicknameLabel')}
          </label>
          <input
            id="nickname"
            type="text"
            value={nickname}
            onChange={(e) => setNickname(e.target.value)}
            className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
          />
        </div>

        {accountMessage && (
          <p
            className={`text-sm ${
              accountMessage.type === 'success' ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'
            }`}
          >
            {accountMessage.text}
          </p>
        )}

        <button
          type="submit"
          disabled={accountSaving || !account}
          className="rounded-lg bg-slate-900 px-4 py-2 font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
        >
          {accountSaving ? t('common.saving') : t('common.save')}
        </button>
      </form>

      <form
        onSubmit={handleProfileSubmit}
        className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900"
      >
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
          {t('account.profileCard.title')}
        </h2>

        <div className="grid grid-cols-2 gap-4">
          {(
            [
              ['first_name', t('account.profileCard.firstNameLabel')],
              ['last_name', t('account.profileCard.lastNameLabel')],
              ['avatar_url', t('account.profileCard.avatarUrlLabel')],
              ['language_code', t('account.profileCard.languageCodeLabel')],
              ['birth_date', t('account.profileCard.birthDateLabel')],
              ['country_code', t('account.profileCard.countryCodeLabel')],
            ] as const
          ).map(([field, label]) => (
            <div key={field}>
              <label htmlFor={field} className="mb-1 block text-sm text-slate-600 dark:text-slate-400">
                {label}
              </label>
              <input
                id={field}
                type={field === 'birth_date' ? 'date' : 'text'}
                value={profileForm[field] ?? ''}
                onChange={(e) => setProfileForm((prev) => ({ ...prev, [field]: e.target.value }))}
                className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-slate-900 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-100"
              />
            </div>
          ))}
        </div>

        {attributes.length > 0 && (
          <div className="space-y-4 border-t border-slate-200 pt-4 dark:border-slate-800">
            {attributes.map((attribute) => (
              <DynamicAttributeField
                key={attribute.key}
                attribute={attribute}
                value={attributeValues[attribute.key]}
                onChange={(key, value) => setAttributeValues((prev) => ({ ...prev, [key]: value }))}
              />
            ))}
          </div>
        )}

        {profileMessage && (
          <p
            className={`text-sm ${
              profileMessage.type === 'success' ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'
            }`}
          >
            {profileMessage.text}
          </p>
        )}

        <button
          type="submit"
          disabled={profileSaving || !profile}
          className="rounded-lg bg-slate-900 px-4 py-2 font-medium text-slate-100 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900"
        >
          {profileSaving ? t('common.saving') : t('common.save')}
        </button>
      </form>

      {/* Deliberately not inside the Profile <form> above: this toggle saves
          instantly (see ThemeToggle), unlike the rest of the profile fields
          which wait for the Save button. */}
      <div className="space-y-3 rounded-2xl border border-sky-700/40 bg-sky-50 p-6 dark:border-sky-800/40 dark:bg-sky-950/20">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-400">
          {t('account.themeCard.title')}
        </h2>

        <p className="text-sm text-slate-600 dark:text-slate-400">
          {t('account.themeCard.storedLabel')}:{' '}
          <span className="font-medium text-slate-900 dark:text-slate-100">
            {storedDarkMode ? t('account.themeCard.dark') : t('account.themeCard.light')}
          </span>
        </p>

        {storedDarkMode !== darkMode && (
          <p className="text-sm text-amber-600 dark:text-amber-400">{t('account.themeCard.diverges')}</p>
        )}

        <label className="flex items-center gap-3 text-sm text-slate-700 dark:text-slate-300">
          <ThemeToggle onToggle={(next) => setAttributeValues((prev) => ({ ...prev, darkMode: next }))} />
          {t('account.themeCard.toggleLabel')}
        </label>
      </div>
    </div>
  )
}
