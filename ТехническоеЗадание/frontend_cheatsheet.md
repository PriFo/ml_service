# Frontend CSS-first Cheatsheet

## 🎨 CSS Variables (theme.css)

```css
:root {
  /* Colors */
  --color-bg-primary: #ffffff;
  --color-bg-secondary: #f5f5f5;
  --color-text-primary: #1a1a1a;
  --color-text-secondary: #666666;
  --color-border: #e0e0e0;
  --color-primary: #3b82f6;
  --color-error: #ef4444;
  
  /* Animations */
  --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-normal: 250ms cubic-bezier(0.4, 0, 0.2, 1);
  
  /* Shadows */
  --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.1);
}

@media (prefers-color-scheme: dark) {
  :root {
    --color-bg-primary: #1a1a1a;
    --color-text-primary: #ffffff;
  }
}
```

---

## ✨ Animations (@keyframes only, NO JS)

### Slide In
```css
@keyframes slideInTop {
  from { transform: translateY(-20px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

@keyframes slideInLeft {
  from { transform: translateX(-20px); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}

.animate-slideInTop { animation: slideInTop var(--transition-normal) ease-out; }
```

### Fade
```css
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.animate-fadeIn { animation: fadeIn var(--transition-normal) ease-out; }
```

### Scale
```css
@keyframes scaleIn {
  from { transform: scale(0.95); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}

.animate-scaleIn { animation: scaleIn var(--transition-normal) ease-out; }
```

### Pulse (Loading)
```css
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.animate-pulse { animation: pulse 2s ease-in-out infinite; }
```

**GPU Rule:** Only `transform` and `opacity` — never width/height/top/left

---

## 🎯 State Management (Context API)

```typescript
// lib/store.tsx
import { createContext, useReducer } from 'react';

type Action =
  | { type: 'SET_THEME'; payload: 'light' | 'dark' | 'system' }
  | { type: 'ADD_ALERT'; payload: Alert }
  | { type: 'REMOVE_ALERT'; payload: string };

function reducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case 'SET_THEME':
      return { ...state, theme: action.payload };
    case 'ADD_ALERT':
      return { ...state, alerts: [...state.alerts, action.payload] };
    case 'REMOVE_ALERT':
      return { ...state, alerts: state.alerts.filter(a => a.id !== action.payload) };
    default:
      return state;
  }
}

// In component:
const { state, dispatch } = useAppStore();
dispatch({ type: 'ADD_ALERT', payload: newAlert });
```

---

## 📡 API Client (Fetch only, NO axios)

```typescript
// lib/api.ts
const API_URL = process.env.NEXT_PUBLIC_API_URL;

async function httpRequest<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const response = await fetch(`${API_URL}${endpoint}`, {
    method: options.method || 'GET',
    headers: {
      'Content-Type': 'application/json',
      'X-Admin-Token': localStorage.getItem('api_token') || '',
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

// Usage
const models = await httpRequest('/models');
const result = await httpRequest('/predict', { method: 'POST', body: data });
```

---

## 🌙 Dark/Light Mode (CSS only)

```typescript
// lib/theme.ts
class ThemeManager {
  setTheme(theme: 'light' | 'dark' | 'system') {
    const html = document.documentElement;
    
    if (theme === 'system') {
      html.removeAttribute('data-theme');
    } else {
      html.setAttribute('data-theme', theme);
    }
    
    sessionStorage.setItem('app-theme', theme);
  }
  
  toggleTheme() {
    const current = this.getResolvedTheme();
    this.setTheme(current === 'light' ? 'dark' : 'light');
  }
}

export const themeManager = new ThemeManager();
```

**In component:**
```tsx
<button onClick={() => themeManager.toggleTheme()}>🌙</button>
```

---

## 🍪 Cookie Consent (GDPR)

```typescript
interface Consent {
  essential: boolean;   // Always true
  analytics: boolean;
  preferences: boolean;
  timestamp: number;
}

function saveConsent(consent: Consent) {
  // Always sessionStorage
  sessionStorage.setItem('consent', JSON.stringify(consent));
  
  // localStorage only if preferences allowed
  if (consent.preferences) {
    localStorage.setItem('consent', JSON.stringify(consent));
  }
}

// Check consent before using features
function canUseAnalytics() {
  const stored = sessionStorage.getItem('consent');
  const consent = JSON.parse(stored || '{}') as Consent;
  return consent.analytics ?? false;
}
```

---

## 📨 WebSocket (Real-time)

```typescript
// lib/api.ts
class WebSocketClient {
  private ws: WebSocket | null = null;
  private listeners = new Map<string, Function[]>();
  
  connect() {
    this.ws = new WebSocket(process.env.NEXT_PUBLIC_WEBSOCKET_URL);
    this.ws.onmessage = (event) => {
      const { type, payload } = JSON.parse(event.data);
      this.listeners.get(type)?.forEach(fn => fn(payload));
    };
  }
  
  on(eventType: string, handler: Function) {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, []);
    }
    this.listeners.get(eventType)!.push(handler);
  }
  
  send(type: string, payload: any) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type, payload }));
    }
  }
}

export const wsClient = new WebSocketClient();

// Usage
wsClient.on('alerts:new', (alert) => {
  dispatch({ type: 'ADD_ALERT', payload: alert });
});
```

---

## 📦 Component Pattern

```typescript
// components/MyComponent.tsx
'use client';  // Client-side component

import styles from './MyComponent.module.css';
import { useAppStore } from '@/lib/store';

export function MyComponent() {
  const { state, dispatch } = useAppStore();
  
  return (
    <div className={`${styles.container} animate-slideInTop`}>
      {/* CSS class for animations */}
      <h1 className={styles.title}>{state.selectedModel}</h1>
    </div>
  );
}
```

```css
/* MyComponent.module.css */
.container {
  padding: 16px;
  background: var(--color-bg-secondary);
  border-radius: 8px;
  transition: all var(--transition-fast);
}

.container:hover {
  background: var(--color-border);
  box-shadow: var(--shadow-md);
}

.title {
  margin: 0;
  color: var(--color-text-primary);
  font-size: 18px;
}
```

---

## ⚡ Performance Checklist

- ✅ No `import zustand, axios, recharts, tailwind`
- ✅ Use CSS modules only (no CSS-in-JS)
- ✅ All animations via CSS (@keyframes)
- ✅ Only `transform` and `opacity` in animations
- ✅ Fetch API for HTTP requests
- ✅ React Context for state
- ✅ CSS variables for theme
- ✅ WebSocket for real-time
- ✅ Progressive Enhancement (works without JS)
- ✅ Bundle < 100KB gzip

---

## 🔧 Setup Commands

```bash
# Create next app with minimal config
npx create-next-app@latest frontend --typescript --no-tailwind --no-eslint

# Remove unnecessary packages
npm uninstall zustand axios recharts next-themes tailwindcss

# Install only essential
npm install

# Check bundle size
npm run build && npm run analyze

# Start dev
npm run dev
```

---

## 🎯 Common Patterns

### Alert Component
```tsx
<div className="animate-slideInTop alert alert-error">
  <p>{message}</p>
  <button onClick={dismiss}>×</button>
</div>
```

### Loading State
```tsx
<div className="skeleton">
  {/* Shimmer animation in CSS */}
</div>
```

### Modal
```tsx
<div className="modal-overlay animate-fadeIn">
  <div className="modal animate-scaleIn">
    {/* Content */}
  </div>
</div>
```

### Dropdown
```tsx
<select className="form-select" onChange={handleChange}>
  {options.map(opt => <option key={opt.id}>{opt.name}</option>)}
</select>
```

---

## ❌ DO NOT DO

```typescript
// ❌ NO Framer Motion
import { motion } from 'framer-motion';

// ❌ NO axios
import axios from 'axios';

// ❌ NO zustand
import { create } from 'zustand';

// ❌ NO recharts
import { LineChart } from 'recharts';

// ❌ NO Tailwind
className="flex justify-center items-center"

// ❌ NO Material-UI
import { Button } from '@mui/material';

// ❌ NO lodash
import { debounce } from 'lodash';

// ❌ NO styled-components
const StyledDiv = styled.div`...`;

// ❌ NO localStorage without consent
localStorage.setItem('key', 'value');  // Always check consent first

// ❌ NO animating width/height
animation: expand 0.3s;  // width changes = reflows

// ❌ NO page reloads
window.location.href = '/page';  // Use client routing
```

---

**Last Updated:** 01.12.2025  
**Version:** 3.2  
**Bundle Size Target:** < 100KB gzip  
**Lighthouse Target:** 98+
