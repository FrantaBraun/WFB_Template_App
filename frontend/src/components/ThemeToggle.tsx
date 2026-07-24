/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import { persistDarkModePreference } from '../theme'

/**
 * Light/dark toggle switch, shared by the header nav and Account.tsx's
 * dedicated theme section so both controls behave identically. Applies the
 * theme instantly (via ThemeContext) and, when signed in, immediately
 * persists it to the profile too - there's no separate "save" step for this
 * control, unlike the rest of the Profile form. Also updates the shared
 * `profileDarkMode` in ThemeContext optimistically, so every consumer (not
 * just this specific toggle instance) sees the new stored value right away.
 */
export default function ThemeToggle() {
  const { t } = useTranslation()
  const { darkMode, setDarkMode, setProfileDarkMode } = useTheme()
  const { user } = useAuth()

  function handleToggle() {
    const next = !darkMode
    setDarkMode(next)
    if (user?.application_group_id) {
      persistDarkModePreference(user.application_group_id, next)
      setProfileDarkMode(next)
    }
  }

  return (
    <button
      onClick={handleToggle}
      role="switch"
      aria-checked={darkMode}
      aria-label={t('common.toggleDarkMode')}
      className={`inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors ${
        darkMode ? 'bg-sky-600' : 'bg-slate-300 dark:bg-slate-700'
      }`}
    >
      <span
        className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
          darkMode ? 'translate-x-4' : 'translate-x-0.5'
        }`}
      />
    </button>
  )
}
