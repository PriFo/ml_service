'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { TrainingJob } from '@/lib/types';
import styles from './JobTracker.module.css';

export default function JobTracker() {
  const [jobs, setJobs] = useState<TrainingJob[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'queued' | 'running' | 'completed' | 'failed'>('all');

  useEffect(() => {
    loadJobs();
    const interval = setInterval(loadJobs, 5000); // Refresh every 5 seconds
    return () => clearInterval(interval);
  }, [filter]);

  const loadJobs = async () => {
    try {
      setIsLoading(true);
      const response = await api.listJobs({
        status: filter !== 'all' ? filter : undefined,
        limit: 50,
      });
      setJobs(response.jobs);
    } catch (error) {
      console.error('Failed to load jobs:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return styles.statusCompleted;
      case 'running': return styles.statusRunning;
      case 'failed': return styles.statusFailed;
      case 'queued': return styles.statusQueued;
      default: return '';
    }
  };

  return (
    <div className={styles.tracker}>
      <div className={styles.header}>
        <h3 className={styles.title}>Training Jobs</h3>
        <div className={styles.filters}>
          {(['all', 'queued', 'running', 'completed', 'failed'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`${styles.filterButton} ${filter === f ? styles.active : ''}`}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className={styles.loading}>Loading jobs...</div>
      ) : jobs.length === 0 ? (
        <div className={styles.empty}>No jobs found</div>
      ) : (
        <div className={styles.jobsList}>
          {jobs.map((job) => (
            <div key={job.job_id} className={styles.jobCard}>
              <div className={styles.jobHeader}>
                <span className={`${styles.statusBadge} ${getStatusColor(job.status)}`}>
                  {job.status}
                </span>
                <span className={styles.jobId}>{job.job_id}</span>
              </div>
              <div className={styles.jobDetails}>
                <p><strong>Model:</strong> {job.model_key}</p>
                {job.dataset_size && <p><strong>Dataset Size:</strong> {job.dataset_size} items</p>}
                {job.created_at && (
                  <p><strong>Created:</strong> {new Date(job.created_at).toLocaleString()}</p>
                )}
                {job.started_at && (
                  <p><strong>Started:</strong> {new Date(job.started_at).toLocaleString()}</p>
                )}
                {job.completed_at && (
                  <p><strong>Completed:</strong> {new Date(job.completed_at).toLocaleString()}</p>
                )}
                {job.error_message && (
                  <p className={styles.error}><strong>Error:</strong> {job.error_message}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

