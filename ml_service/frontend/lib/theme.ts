// Theme management
import type { Theme } from './types';
export type { Theme };

class ThemeManager {
  private currentTheme: Theme = 'system';

  setTheme(theme: Theme) {
    this.currentTheme = theme;
    const html = document.documentElement;

    if (theme === 'system') {
      html.removeAttribute('data-theme');
    } else {
      html.setAttribute('data-theme', theme);
    }

    // Save to sessionStorage (always allowed)
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('app-theme', theme);
      
      // Save to localStorage only if preferences consent given
      const consent = this.getConsent();
      if (consent?.preferences) {
        localStorage.setItem('app-theme', theme);
      }
    }

    window.dispatchEvent(new CustomEvent('theme-change', { detail: { theme } }));
  }

  getTheme(): Theme {
    if (typeof window === 'undefined') return 'system';
    
    // Check localStorage first (if consent given)
    const consent = this.getConsent();
    if (consent?.preferences) {
      const stored = localStorage.getItem('app-theme');
      if (stored && ['system', 'light', 'dark'].includes(stored)) {
        return stored as Theme;
      }
    }
    
    // Fallback to sessionStorage
    const sessionStored = sessionStorage.getItem('app-theme');
    if (sessionStored && ['system', 'light', 'dark'].includes(sessionStored)) {
      return sessionStored as Theme;
    }
    
    return 'system';
  }

  getResolvedTheme(): 'light' | 'dark' {
    const theme = this.getTheme();
    
    if (theme !== 'system') {
      return theme as 'light' | 'dark';
    }
    
    // System preference
    if (typeof window !== 'undefined' && window.matchMedia) {
      return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    
    return 'light';
  }

  toggleTheme() {
    const current = this.getResolvedTheme();
    this.setTheme(current === 'light' ? 'dark' : 'light');
  }

  private getConsent() {
    if (typeof window === 'undefined') return null;
    
    try {
      const consentStr = sessionStorage.getItem('consent') || localStorage.getItem('consent');
      return consentStr ? JSON.parse(consentStr) : null;
    } catch {
      return null;
    }
  }

  init() {
    const theme = this.getTheme();
    this.setTheme(theme);
  }
}

export const themeManager = new ThemeManager();

