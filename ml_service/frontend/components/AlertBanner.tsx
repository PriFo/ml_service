'use client';

import { useState, useEffect } from 'react';
import { useAppStore } from '@/lib/store';
import { api } from '@/lib/api';
import styles from './AlertBanner.module.css';

export default function AlertBanner() {
  const { state, dispatch } = useAppStore();
  const [dismissingId, setDismissingId] = useState<string | null>(null);

  const handleDismiss = async (alertId: string) => {
    setDismissingId(alertId);
    
    try {
      await api.dismissAlert(alertId);
      setTimeout(() => {
        dispatch({ type: 'REMOVE_ALERT', payload: alertId });
        setDismissingId(null);
      }, 150);
    } catch (error) {
      console.error('Error dismissing alert:', error);
      setDismissingId(null);
    }
  };

  // Auto-dismiss non-critical alerts after 5s
  useEffect(() => {
    state.alerts.forEach(alert => {
      if (alert.severity !== 'critical' && !dismissingId) {
        const timer = setTimeout(() => {
          handleDismiss(alert.alert_id);
        }, 5000);
        return () => clearTimeout(timer);
      }
    });
  }, [state.alerts]);

  if (state.alerts.length === 0) return null;

  return (
    <div className={styles.container}>
      {state.alerts.map(alert => (
        <div
          key={alert.alert_id}
          className={`${styles.alert} ${styles[`alert-${alert.severity}`]} ${
            dismissingId === alert.alert_id ? styles.dismissing : 'animate-slideInTop'
          }`}
        >
          <p className={styles.message}>{alert.message}</p>
          {alert.dismissible && (
            <button
              onClick={() => handleDismiss(alert.alert_id)}
              className={styles.dismissButton}
              aria-label="Закрыть"
            >
              ×
            </button>
          )}
        </div>
      ))}
    </div>
  );
}

