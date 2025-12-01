'use client';

import { useState, useRef, useEffect } from 'react';
import { useAppStore } from '@/lib/store';
import { themeManager } from '@/lib/theme';
import type { Theme } from '@/lib/types';
import styles from './ThemeDropdown.module.css';

export default function ThemeDropdown() {
  const { state, dispatch } = useAppStore();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  const themes: Array<{ value: Theme; label: string; icon: string }> = [
    { value: 'light', label: 'Light', icon: '☀' },
    { value: 'dark', label: 'Dark', icon: '☾' },
    { value: 'system', label: 'System', icon: '⚙' },
  ];

  const currentTheme = themeManager.getTheme();
  const currentThemeData = themes.find(t => t.value === currentTheme) || themes[0];

  const handleThemeChange = (theme: Theme) => {
    themeManager.setTheme(theme);
    dispatch({ type: 'SET_THEME', payload: theme });
    setIsOpen(false);
  };

  return (
    <div className={styles.dropdown} ref={dropdownRef}>
      <button
        className={styles.trigger}
        onClick={() => setIsOpen(!isOpen)}
        aria-label="Theme selector"
      >
        <span className={styles.triggerIcon}>{currentThemeData.icon}</span>
        <span className={styles.triggerLabel}>{currentThemeData.label}</span>
        <span className={styles.triggerArrow}>{isOpen ? '▲' : '▼'}</span>
      </button>

      {isOpen && (
        <div className={styles.menu}>
          {themes.map(theme => (
            <button
              key={theme.value}
              className={`${styles.menuItem} ${currentTheme === theme.value ? styles.active : ''}`}
              onClick={() => handleThemeChange(theme.value)}
            >
              <span className={styles.menuIcon}>{theme.icon}</span>
              <span className={styles.menuLabel}>{theme.label}</span>
              {currentTheme === theme.value && (
                <span className={styles.checkmark}>✓</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
