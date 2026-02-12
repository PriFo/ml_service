'use client';

import { useAppStore } from '@/lib/store';
import { api } from '@/lib/api';
import { useState, useEffect } from 'react';
import styles from './DashboardCards.module.css';

export default function DashboardCards() {
  const { state } = useAppStore();
  const [stats, setStats] = useState({
    totalModels: 0,
    activeJobs: 0,
    completedJobs: 0,
    failedJobs: 0,
    criticalAlerts: 0,
    warnings: 0,
  });

  useEffect(() => {
    const loadStats = async () => {
      try {
        const [modelsResponse, jobsResponse, alertsResponse] = await Promise.all([
          api.getModels(),
          api.listJobs({ limit: 100 }),
          api.getAlerts().catch(() => ({ alerts: [] })), // Fallback to empty array if fails
        ]);

        const jobs = jobsResponse.jobs || [];
        const activeJobs = jobs.filter(j => j.status === 'running' || j.status === 'queued').length;
        const completedJobs = jobs.filter(j => j.status === 'completed').length;
        const failedJobs = jobs.filter(j => j.status === 'failed').length;

        // Use alerts from API response, not from state
        const alerts = alertsResponse.alerts || [];
        const criticalAlerts = alerts.filter(a => a.severity === 'critical').length;
        const warnings = alerts.filter(a => a.severity === 'warning').length;

        setStats({
          totalModels: modelsResponse.models?.length || 0,
          activeJobs,
          completedJobs,
          failedJobs,
          criticalAlerts,
          warnings,
        });
      } catch (error) {
        // Silently handle connection errors when backend is not running
        const errorMessage = error instanceof Error ? error.message : String(error);
        if (!errorMessage.includes('Unable to connect to backend')) {
          console.error('Failed to load stats:', error);
        }
      }
    };

    loadStats();
    const interval = setInterval(loadStats, 10000); // Update every 10 seconds
    return () => clearInterval(interval);
  }, []);

  return (
    <div className={styles.cardsGrid}>
      <div className={`${styles.card} ${styles.cardInfo}`}>
        <div className={styles.cardContent}>
          <h3 className={styles.cardTitle}>Models</h3>
          <p className={styles.cardValue}>{stats.totalModels}</p>
          <p className={styles.cardLabel}>Total models</p>
        </div>
      </div>

      <div className={`${styles.card} ${styles.cardWarning}`}>
        <div className={styles.cardContent}>
          <h3 className={styles.cardTitle}>Active Jobs</h3>
          <p className={styles.cardValue}>{stats.activeJobs}</p>
          <p className={styles.cardLabel}>Running or queued</p>
        </div>
      </div>

      <div className={`${styles.card} ${styles.cardSuccess}`}>
        <div className={styles.cardContent}>
          <h3 className={styles.cardTitle}>Completed</h3>
          <p className={styles.cardValue}>{stats.completedJobs}</p>
          <p className={styles.cardLabel}>Successful jobs</p>
        </div>
      </div>

      <div className={`${styles.card} ${styles.cardError}`}>
        <div className={styles.cardContent}>
          <h3 className={styles.cardTitle}>Failed</h3>
          <p className={styles.cardValue}>{stats.failedJobs}</p>
          <p className={styles.cardLabel}>Failed jobs</p>
        </div>
      </div>

      <div className={`${styles.card} ${styles.cardCritical} ${stats.criticalAlerts > 0 ? styles.cardCriticalActive : ''}`}>
        <div className={styles.cardContent}>
          <h3 className={styles.cardTitle}>Critical Alerts</h3>
          <p className={styles.cardValue}>{stats.criticalAlerts}</p>
          <p className={styles.cardLabel}>Requires attention</p>
        </div>
      </div>

      <div className={`${styles.card} ${styles.cardWarning} ${stats.warnings > 0 ? styles.cardWarningActive : ''}`}>
        <div className={styles.cardContent}>
          <h3 className={styles.cardTitle}>Warnings</h3>
          <p className={styles.cardValue}>{stats.warnings}</p>
          <p className={styles.cardLabel}>Non-critical issues</p>
        </div>
      </div>
    </div>
  );
}

