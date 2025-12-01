'use client';

import { useState } from 'react';
import { useAppStore } from '@/lib/store';
import styles from './Login.module.css';

interface LoginProps {
  onLogin: (token: string) => void;
}

export default function Login({ onLogin }: LoginProps) {
  const [token, setToken] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      // Test token by making a request
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8085'}/health`, {
        headers: {
          'X-Admin-Token': token,
        },
      });

      if (response.ok || response.status === 403) {
        // Save token
        if (typeof window !== 'undefined') {
          sessionStorage.setItem('api_token', token);
          localStorage.setItem('api_token', token);
        }
        onLogin(token);
      } else {
        setError('Invalid token');
      }
    } catch (err) {
      // In development mode, allow empty token
      if (!token && process.env.NODE_ENV === 'development') {
        if (typeof window !== 'undefined') {
          sessionStorage.setItem('api_token', '');
          localStorage.setItem('api_token', '');
        }
        onLogin('');
      } else {
        setError('Failed to authenticate');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={styles.loginContainer}>
      <div className={styles.loginBox}>
        <h1 className={styles.title}>ML Service 0.9.1</h1>
        <p className={styles.subtitle}>Enter your admin token to continue</p>
        
        <form onSubmit={handleSubmit} className={styles.form}>
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

          <p className={styles.hint}>
            In development mode, you can leave this empty if no token is configured.
          </p>
        </form>
      </div>
    </div>
  );
}

