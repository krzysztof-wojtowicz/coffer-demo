import { useCallback, useEffect, useState } from 'react'

export type ThemePreference = 'light' | 'dark' | 'system'

const KEY = 'coffer.theme'
const QUERY = '(prefers-color-scheme: dark)'
const THEME_COLORS = { light: '#faf7f0', dark: '#15171c' }
const listeners = new Set<(p: ThemePreference) => void>()
let current: ThemePreference | null = null

export function getStoredPreference(): ThemePreference {
  try {
    const v = localStorage.getItem(KEY)
    return v === 'light' || v === 'dark' || v === 'system' ? v : 'system'
  } catch {
    return 'system'
  }
}

function systemPrefersDark(): boolean {
  try {
    return typeof window.matchMedia !== 'function' || window.matchMedia(QUERY).matches
  } catch {
    return true
  }
}

export function resolveTheme(p: ThemePreference): 'light' | 'dark' {
  if (p === 'system') return systemPrefersDark() ? 'dark' : 'light'
  return p
}

export function applyTheme(t: 'light' | 'dark'): void {
  document.documentElement.dataset.theme = t
  document.documentElement.style.colorScheme = t
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', THEME_COLORS[t])
}

export function setPreference(p: ThemePreference): void {
  current = null
  try {
    localStorage.setItem(KEY, p)
  } catch {
    current = p
    // storage unavailable: preference lasts for this session only
  }
  applyTheme(resolveTheme(p))
  listeners.forEach((l) => l(p))
}

export function useTheme(): {
  preference: ThemePreference
  resolved: 'light' | 'dark'
  setPreference: (p: ThemePreference) => void
} {
  const [preference, setPref] = useState<ThemePreference>(() => current ?? getStoredPreference())
  const [resolved, setResolved] = useState<'light' | 'dark'>(() => resolveTheme(current ?? getStoredPreference()))

  useEffect(() => {
    const sync = (p: ThemePreference) => setPref(p)
    listeners.add(sync)
    return () => {
      listeners.delete(sync)
    }
  }, [])

  useEffect(() => {
    const r = resolveTheme(preference)
    setResolved(r)
    applyTheme(r)
    if (preference !== 'system' || typeof window.matchMedia !== 'function') return
    const mq = window.matchMedia(QUERY)
    const onChange = () => {
      const t = resolveTheme('system')
      setResolved(t)
      applyTheme(t)
    }
    mq.addEventListener?.('change', onChange)
    return () => mq.removeEventListener?.('change', onChange)
  }, [preference])

  const set = useCallback((p: ThemePreference) => {
    setPref(p)
    setPreference(p)
  }, [])

  return { preference, resolved, setPreference: set }
}
