/**
 * Part of the With FBraun project template.
 * Author: František Braun <frantisek.braun95@gmail.com>
 * Freely available as a template for building custom applications.
 */

import { createContext, useContext, useEffect, useState } from 'react'

interface ThemeContextType {
  darkMode: boolean
  setDarkMode: (value: boolean) => void
}

const ThemeContext = createContext<ThemeContextType>({
  darkMode: false,
  setDarkMode: () => {},
})

const STORAGE_KEY = 'dark_mode'

/**
 * Local theme state only - toggles the .dark class on <html> (see index.css's
 * @custom-variant dark) and persists to localStorage for instant reapplication
 * on the next load, default false (light). Syncing this with the signed-in
 * user's stored profile preference (user_data.darkMode) happens in
 * AuthContext.tsx's loadUser(), not here, so this provider works standalone
 * even for a logged-out visitor.
 */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [darkMode, setDarkMode] = useState<boolean>(() => localStorage.getItem(STORAGE_KEY) === 'true')

  useEffect(() => {
    document.documentElement.classList.toggle('dark', darkMode)
    localStorage.setItem(STORAGE_KEY, String(darkMode))
  }, [darkMode])

  return <ThemeContext.Provider value={{ darkMode, setDarkMode }}>{children}</ThemeContext.Provider>
}

/** Reads the current ThemeContextType (darkMode, setDarkMode) from the nearest ThemeProvider. */
export function useTheme() {
  return useContext(ThemeContext)
}
