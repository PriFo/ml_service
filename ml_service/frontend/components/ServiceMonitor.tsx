'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import styles from './ServiceMonitor.module.css';

interface ServiceStatus {
  status: string;
  version: string;
  timestamp: string;
}

export default function ServiceMonitor() {
  const [status, setStatus] = useState<ServiceStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const checkStatus = async () => {
      try {
        const health = await api.getHealthStatus();
        setStatus(health);
        setError(null);
      } catch (err) {
        setError((err as Error).message);
        setStatus(null);
      } finally {
        setIsLoading(false);
      }
    };

    checkStatus();
    const interval = setInterval(checkStatus, 30000); // Check every 30 seconds

    return () => clearInterval(interval);
  }, []);

  if (isLoading) {
    return <div className={styles.monitor}>Checking service status...</div>;
  }

  return (
    <div className={styles.monitor}>
      <h3 className={styles.title}>Service Status</h3>
      {error ? (
        <div className={styles.error}>
          <span className={styles.statusBadge}>Error</span>
          <p>{error}</p>
        </div>
      ) : status ? (
        <div className={styles.status}>
          <span className={`${styles.statusBadge} ${status.status === 'healthy' ? styles.healthy : styles.degraded}`}>
            {status.status}
          </span>
          <div className={styles.details}>
            <p><strong>Version:</strong> {status.version}</p>
            <p><strong>Last Check:</strong> {new Date(status.timestamp).toLocaleString()}</p>
          </div>
        </div>
      ) : null}
    </div>
  );
}

