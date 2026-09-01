/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { useTranslation } from 'react-i18next'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import { persistDarkModePreference } from '../theme'

/** Sun glyph shown on the thumb while light mode is active. */
function SunIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" aria-hidden="true" className={className}>
      <circle cx="12" cy="12" r="4" fill="currentColor" stroke="none" />
      <path d="M12 2v2M12 20v2M4 12H2M22 12h-2M5.6 5.6 4.2 4.2M19.8 19.8l-1.4-1.4M18.4 5.6l1.4-1.4M4.2 19.8l1.4-1.4" />
    </svg>
  )
}

/** Crescent-moon glyph shown on the thumb while dark mode is active. */
function MoonIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" className={className}>
      <path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5Z" />
    </svg>
  )
}

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
        darkMode ? 'bg-teal' : 'bg-ink/20 dark:bg-ink-dark/25'
      }`}
    >
      <span
        className={`inline-flex h-4 w-4 transform items-center justify-center rounded-full bg-white shadow transition-transform ${
          darkMode ? 'translate-x-4' : 'translate-x-0.5'
        }`}
      >
        {darkMode ? <MoonIcon className="h-2.5 w-2.5 text-teal" /> : <SunIcon className="h-2.5 w-2.5 text-mustard" />}
      </span>
    </button>
  )
}
