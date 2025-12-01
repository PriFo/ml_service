'use client';

import { useEffect, useState } from 'react';
import { useAppStore } from '@/lib/store';
import { themeManager, Theme } from '@/lib/theme';
import styles from './ThemeToggle.module.css';

export default function ThemeToggle() {
  const { state, dispatch } = useAppStore();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const theme = themeManager.getTheme();
    dispatch({ type: 'SET_THEME', payload: theme });
  }, [dispatch]);

  const handleThemeChange = (theme: Theme) => {
    themeManager.setTheme(theme);
    dispatch({ type: 'SET_THEME', payload: theme });
  };

  if (!mounted) return null;

  return (
    <div className={styles.container}>
      <button
        onClick={() => handleThemeChange('light')}
        className={`${styles.button} ${state.theme === 'light' ? styles.active : ''}`}
        aria-label="Светлая тема"
      >
        ☀️
      </button>
      <button
        onClick={() => handleThemeChange('dark')}
        className={`${styles.button} ${state.theme === 'dark' ? styles.active : ''}`}
        aria-label="Темная тема"
      >
        🌙
      </button>
      <button
        onClick={() => handleThemeChange('system')}
        className={`${styles.button} ${state.theme === 'system' ? styles.active : ''}`}
        aria-label="Системная тема"
      >
        💻
      </button>
    </div>
  );
}

