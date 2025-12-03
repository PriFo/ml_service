'use client';

import { useEffect, useState } from 'react';
import { useAppStore } from '@/lib/store';
import { api, wsClient } from '@/lib/api';
import Dashboard from '@/components/Dashboard';
import Login from '@/components/Login';

export default function Home() {
  const { state, dispatch } = useAppStore();
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);

  // Check authentication on mount
  useEffect(() => {
    const checkAuth = async () => {
      if (typeof window === 'undefined') {
        setIsCheckingAuth(false);
        return;
      }

      // Get token from storage
      const token = sessionStorage.getItem('api_token') || localStorage.getItem('api_token');
      const storedTier = sessionStorage.getItem('user_tier') || localStorage.getItem('user_tier');

      if (!token) {
        // No token - show login
        setIsCheckingAuth(false);
        dispatch({
          type: 'SET_AUTHENTICATED',
          payload: { isAuthenticated: false, token: null, tier: null },
        });
        return;
      }

      // Validate token with server by calling a protected endpoint
      try {
        // Try to get user info first (if endpoint exists)
        let userTier = storedTier || null;
        try {
          const userInfo = await api.getUserInfo();
          userTier = userInfo.tier || storedTier || null;
        } catch (userInfoError: any) {
          // If getUserInfo fails, try to validate token by calling /models
          // This will throw 401 if token is invalid
          await api.getModels();
          // If we get here, token is valid but getUserInfo doesn't exist
          // Keep stored tier or default to null
        }
        
        // Token is valid
        dispatch({
          type: 'SET_AUTHENTICATED',
          payload: {
            isAuthenticated: true,
            token: token,
            tier: userTier,
          },
        });
      } catch (error: any) {
        // Check if it's a 401 error
        const isUnauthorized = error.status === 401 || 
                              error.message?.includes('401') || 
                              error.message?.includes('Unauthorized') ||
                              error.message?.includes('Invalid or expired authentication token') ||
                              error.message?.includes('Missing authentication token');
        
        if (isUnauthorized) {
          // Token is invalid (401) - clear it and show login
          // Note: httpRequest already clears tokens on 401, but we do it here too for safety
          sessionStorage.removeItem('api_token');
          localStorage.removeItem('api_token');
          sessionStorage.removeItem('user_tier');
          localStorage.removeItem('user_tier');
        }
        
        dispatch({
          type: 'SET_AUTHENTICATED',
          payload: { isAuthenticated: false, token: null, tier: null },
        });
      } finally {
        setIsCheckingAuth(false);
      }
    };

    checkAuth();
  }, [dispatch]);

  useEffect(() => {
    if (!state.isAuthenticated || isCheckingAuth) {
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
      } catch (error: any) {
        // Check if it's a 401 error - token expired or invalid
        const isUnauthorized = error.status === 401 || 
                              error.message?.includes('401') || 
                              error.message?.includes('Unauthorized') ||
                              error.message?.includes('Invalid or expired authentication token') ||
                              error.message?.includes('Missing authentication token');
        
        if (isUnauthorized) {
          // Token expired or invalid - logout and show login
          dispatch({ type: 'LOGOUT' });
        } else {
          dispatch({ type: 'SET_ERROR', payload: (error as Error).message });
        }
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

  // Show loading while checking authentication
  if (isCheckingAuth) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100vh',
        fontSize: '1.2rem',
        color: '#666'
      }}>
        Checking authentication...
      </div>
    );
  }

  // Show login if not authenticated
  if (!state.isAuthenticated) {
    return <Login onLogin={handleLogin} />;
  }

  // Show dashboard if authenticated
  return <Dashboard />;
}

