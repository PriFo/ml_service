'use client';

import { useEffect } from 'react';
import { useAppStore } from '@/lib/store';
import { api, wsClient } from '@/lib/api';
import Dashboard from '@/components/Dashboard';
import Login from '@/components/Login';

export default function Home() {
  const { state, dispatch } = useAppStore();

  useEffect(() => {
    if (!state.isAuthenticated) {
      return;
    }

    // Load initial data
    const loadData = async () => {
      try {
        dispatch({ type: 'SET_LOADING', payload: true });
        
        // Load models
        const modelsResponse = await api.getModels();
        dispatch({ type: 'SET_MODELS', payload: modelsResponse.models });
        
        // Load alerts
        const alertsResponse = await api.getAlerts();
        alertsResponse.alerts.forEach(alert => {
          dispatch({ type: 'ADD_ALERT', payload: alert });
        });
        
        dispatch({ type: 'SET_LOADING', payload: false });
      } catch (error) {
        dispatch({ type: 'SET_ERROR', payload: (error as Error).message });
        dispatch({ type: 'SET_LOADING', payload: false });
      }
    };

    loadData();

    // Connect WebSocket
    wsClient.connect().catch((error) => {
      // WebSocket connection failed - log but don't block the app
      console.warn('WebSocket connection failed, continuing without real-time updates:', error);
    });
    
    // Subscribe to events
    wsClient.on('alerts:new', (alert: any) => {
      dispatch({ type: 'ADD_ALERT', payload: alert });
    });

    wsClient.on('queue:task_completed', (data: any) => {
      // Reload models when training completes
      api.getModels().then(response => {
        dispatch({ type: 'SET_MODELS', payload: response.models });
      }).catch(err => {
        console.error('Failed to reload models after training:', err);
      });
    });

    return () => {
      wsClient.disconnect();
    };
  }, [dispatch, state.isAuthenticated]);

  const handleLogin = (token: string, tier?: string) => {
    dispatch({
      type: 'SET_AUTHENTICATED',
      payload: { isAuthenticated: true, token, tier: tier || null },
    });
  };

  if (!state.isAuthenticated) {
    return <Login onLogin={handleLogin} />;
  }

  return <Dashboard />;
}

