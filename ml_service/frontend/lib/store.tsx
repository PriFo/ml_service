// State management with Context API + useReducer
'use client';

import React, { createContext, useContext, useReducer, ReactNode } from 'react';
import { AppState, Theme, Model, Alert, DriftReport, Consent } from './types';

// Re-export types for convenience
export type { Theme, Model, Alert, DriftReport, Consent, AppState };

// Initial state
const initialState: AppState = {
  theme: 'system',
  selectedModel: null,
  models: [],
  alerts: [],
  recentDrift: [],
  cookieConsent: null,
  isLoading: false,
  error: null,
  isAuthenticated: false,
  userToken: null,
};

// Action types
type Action =
  | { type: 'SET_THEME'; payload: Theme }
  | { type: 'SELECT_MODEL'; payload: string | null }
  | { type: 'SET_MODELS'; payload: Model[] }
  | { type: 'ADD_ALERT'; payload: Alert }
  | { type: 'REMOVE_ALERT'; payload: string }
  | { type: 'SET_DRIFT_DATA'; payload: DriftReport[] }
  | { type: 'SET_COOKIE_CONSENT'; payload: Consent | null }
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_ERROR'; payload: string | null }
  | { type: 'SET_AUTHENTICATED'; payload: { isAuthenticated: boolean; token: string | null } };

// Reducer
function appReducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case 'SET_THEME':
      return { ...state, theme: action.payload };
    
    case 'SELECT_MODEL':
      return { ...state, selectedModel: action.payload };
    
    case 'SET_MODELS':
      return { ...state, models: action.payload };
    
    case 'ADD_ALERT':
      return { ...state, alerts: [...state.alerts, action.payload] };
    
    case 'REMOVE_ALERT':
      return {
        ...state,
        alerts: state.alerts.filter(a => a.alert_id !== action.payload),
      };
    
    case 'SET_DRIFT_DATA':
      return { ...state, recentDrift: action.payload };
    
    case 'SET_COOKIE_CONSENT':
      return { ...state, cookieConsent: action.payload };
    
    case 'SET_LOADING':
      return { ...state, isLoading: action.payload };
    
    case 'SET_ERROR':
      return { ...state, error: action.payload };
    
    case 'SET_AUTHENTICATED':
      return {
        ...state,
        isAuthenticated: action.payload.isAuthenticated,
        userToken: action.payload.token,
      };
    
    default:
      return state;
  }
}

// Context
interface AppContextType {
  state: AppState;
  dispatch: React.Dispatch<Action>;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

// Provider
export function AppProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(appReducer, initialState);

  return (
    <AppContext.Provider value={{ state, dispatch }}>
      {children}
    </AppContext.Provider>
  );
}

// Hook
export function useAppStore() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useAppStore must be used within AppProvider');
  }
  return context;
}

