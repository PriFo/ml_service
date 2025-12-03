'use client';

import { useState } from 'react';
import { useAppStore } from '@/lib/store';
import { api } from '@/lib/api';
import styles from './Login.module.css';

interface LoginProps {
  onLogin: (token: string, tier?: string) => void;
}

type AuthMethod = 'token' | 'credentials';

export default function Login({ onLogin }: LoginProps) {
  const [authMethod, setAuthMethod] = useState<AuthMethod>('token');
  const [token, setToken] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      if (authMethod === 'token') {
        // Token-based authentication
        if (!token && process.env.NODE_ENV === 'development') {
          // In development mode, allow empty token (default to admin in dev)
          if (typeof window !== 'undefined') {
            sessionStorage.setItem('api_token', '');
            localStorage.setItem('api_token', '');
            sessionStorage.setItem('user_tier', 'admin');
            localStorage.setItem('user_tier', 'admin');
          }
          onLogin('', 'admin');
          setIsLoading(false);
          return;
        }

        // Test token and get user info
        try {
          // First test if token is valid
          const healthResponse = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8085'}/health`, {
            headers: {
              'X-Admin-Token': token,
            },
          });

          if (healthResponse.ok || healthResponse.status === 403) {
            // Token is valid, get user info
            try {
              const userInfo = await api.getUserInfo();
              const tier = userInfo.tier || 'basic';
              
              if (typeof window !== 'undefined') {
                sessionStorage.setItem('api_token', token);
                localStorage.setItem('api_token', token);
                sessionStorage.setItem('user_tier', tier);
                localStorage.setItem('user_tier', tier);
              }
              onLogin(token, tier);
            } catch (infoError) {
              // If user-info endpoint fails, assume basic tier
              const tier = 'basic';
              if (typeof window !== 'undefined') {
                sessionStorage.setItem('api_token', token);
                localStorage.setItem('api_token', token);
                sessionStorage.setItem('user_tier', tier);
                localStorage.setItem('user_tier', tier);
              }
              onLogin(token, tier);
            }
          } else {
            setError('Invalid token');
          }
        } catch (err) {
          setError('Failed to validate token');
        }
      } else {
        // Credentials-based authentication
        // In dev mode, allow empty credentials
        if (!username && !password && process.env.NODE_ENV !== 'development') {
          setError('Username and password are required');
          setIsLoading(false);
          return;
        }
        
        // In dev mode with empty credentials, allow access
        if (!username && !password && process.env.NODE_ENV === 'development') {
          const devToken = `dev_anonymous_${Date.now()}`;
          if (typeof window !== 'undefined') {
            sessionStorage.setItem('api_token', devToken);
            localStorage.setItem('api_token', devToken);
            sessionStorage.setItem('user_tier', 'admin');
            localStorage.setItem('user_tier', 'admin');
          }
          onLogin(devToken, 'admin');
          setIsLoading(false);
          return;
        }

        // Authenticate via API
        try {
          const loginData = await api.login(username, password);
          if (loginData.token) {
            const tier = loginData.tier || 'basic';
            if (typeof window !== 'undefined') {
              sessionStorage.setItem('api_token', loginData.token);
              localStorage.setItem('api_token', loginData.token);
              sessionStorage.setItem('user_tier', tier);
              localStorage.setItem('user_tier', tier);
            }
            onLogin(loginData.token, tier);
          } else {
            setError('No token received from server');
          }
        } catch (apiError: any) {
          // If API endpoint doesn't exist or fails, try fallback for dev mode
          if (process.env.NODE_ENV === 'development') {
            // In dev mode, allow default credentials
            const defaultUsers = [
              { username: 'admin', password: 'admin' },
              { username: 'user', password: 'user' },
            ];
            
            const isValid = defaultUsers.some(u => u.username === username && u.password === password);
            
            if (isValid || (!username && !password)) {
              // Generate a simple token for dev mode
              const devToken = `dev_${username || 'anonymous'}_${Date.now()}`;
              const tier = username === 'admin' ? 'admin' : 'basic';
              if (typeof window !== 'undefined') {
                sessionStorage.setItem('api_token', devToken);
                localStorage.setItem('api_token', devToken);
                sessionStorage.setItem('user_tier', tier);
                localStorage.setItem('user_tier', tier);
              }
              onLogin(devToken, tier);
            } else {
              setError(apiError?.message || 'Invalid username or password');
            }
          } else {
            setError(apiError?.message || 'Authentication failed');
          }
        }
      }
    } catch (err) {
      setError(`Failed to authenticate: ${(err as Error).message}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={styles.loginContainer}>
      <div className={styles.loginBox}>
        <h1 className={styles.title}>ML Service 0.9.1</h1>
        <p className={styles.subtitle}>Sign in to continue</p>
        
        {/* Auth Method Selector */}
        <div className={styles.authMethodSelector}>
          <button
            type="button"
            className={`${styles.methodButton} ${authMethod === 'token' ? styles.active : ''}`}
            onClick={() => {
              setAuthMethod('token');
              setError(null);
            }}
          >
            API Token
          </button>
          <button
            type="button"
            className={`${styles.methodButton} ${authMethod === 'credentials' ? styles.active : ''}`}
            onClick={() => {
              setAuthMethod('credentials');
              setError(null);
            }}
          >
            Username/Password
          </button>
        </div>

        <form onSubmit={handleSubmit} className={styles.form}>
          {authMethod === 'token' ? (
            <div className={styles.inputGroup}>
              <label htmlFor="token" className={styles.label}>
                Admin Token
              </label>
              <input
                id="token"
                type="password"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="Enter admin token (optional in dev mode)"
                className={styles.input}
                autoFocus
              />
            </div>
          ) : (
            <>
              <div className={styles.inputGroup}>
                <label htmlFor="username" className={styles.label}>
                  Username
                </label>
                <input
                  id="username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Enter username"
                  className={styles.input}
                  autoFocus
                  required
                />
              </div>
              <div className={styles.inputGroup}>
                <label htmlFor="password" className={styles.label}>
                  Password
                </label>
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter password"
                  className={styles.input}
                  required
                />
              </div>
              {process.env.NODE_ENV === 'development' && (
                <p className={styles.hint}>
                  Dev mode: Try 'admin/admin' or 'user/user', or leave empty
                </p>
              )}
            </>
          )}

          {error && (
            <div className={styles.error}>{error}</div>
          )}

          <button
            type="submit"
            disabled={isLoading}
            className={styles.button}
          >
            {isLoading ? 'Authenticating...' : 'Login'}
          </button>

          {authMethod === 'token' && (
            <p className={styles.hint}>
              In development mode, you can leave this empty if no token is configured.
            </p>
          )}
        </form>
      </div>
    </div>
  );
}

