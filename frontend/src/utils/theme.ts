import { useEffect, useState } from 'react';

export type ThemeMode = 'dark' | 'light';

const STORAGE_KEY = 'hf-theme';

export function getStoredTheme(): ThemeMode {
  if (typeof document === 'undefined') return 'dark';
  const current = document.documentElement.dataset.theme;
  if (current === 'light' || current === 'dark') return current;
  try {
    return localStorage.getItem(STORAGE_KEY) === 'light' ? 'light' : 'dark';
  } catch {
    return 'dark';
  }
}

export function applyTheme(theme: ThemeMode): void {
  if (typeof document !== 'undefined') {
    document.documentElement.dataset.theme = theme;
  }
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // ignore storage errors
  }
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('hf-theme-change', { detail: theme }));
  }
}

export function useTheme(): [ThemeMode, () => void] {
  const [theme, setTheme] = useState<ThemeMode>(getStoredTheme);

  useEffect(() => {
    const sync = () => setTheme(getStoredTheme());
    window.addEventListener('hf-theme-change', sync);
    window.addEventListener('storage', sync);
    return () => {
      window.removeEventListener('hf-theme-change', sync);
      window.removeEventListener('storage', sync);
    };
  }, []);

  const toggle = () => {
    const next: ThemeMode = theme === 'dark' ? 'light' : 'dark';
    applyTheme(next);
    setTheme(next);
  };

  return [theme, toggle];
}
