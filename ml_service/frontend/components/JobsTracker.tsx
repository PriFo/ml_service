'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { Job } from '@/lib/types';
import styles from './JobsTracker.module.css';

export default function JobsTracker() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<'all' | 'queued' | 'running' | 'completed' | 'failed'>('all');
  const [typeFilter, setTypeFilter] = useState<'all' | 'train' | 'predict' | 'drift' | 'other'>('all');

  useEffect(() => {
    loadJobs();
    const interval = setInterval(loadJobs, 5000); // Refresh every 5 seconds
    return () => clearInterval(interval);
  }, [statusFilter, typeFilter]);

  const loadJobs = async () => {
    try {
      setIsLoading(true);
      const response = await api.listJobs({
        status: statusFilter !== 'all' ? statusFilter : undefined,
        job_type: typeFilter !== 'all' ? typeFilter : undefined,
        limit: 50,
      });
      setJobs(response.jobs);
    } catch (error) {
      // Silently handle connection errors when backend is not running
      const errorMessage = error instanceof Error ? error.message : String(error);
      if (!errorMessage.includes('Unable to connect to backend')) {
        console.error('Failed to load jobs:', error);
      }
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

  const getTypeColor = (jobType: string) => {
    switch (jobType) {
      case 'train': return styles.typeTrain;
      case 'predict': return styles.typePredict;
      case 'drift': return styles.typeDrift;
      case 'other': return styles.typeOther;
      default: return '';
    }
  };

  const getSourceLabel = (source?: string) => {
    switch (source) {
      case 'api': return 'API';
      case 'gui': return 'GUI';
      case 'system': return 'System';
      default: return 'Unknown';
    }
  };

  return (
    <div className={styles.tracker}>
      <div className={styles.header}>
        <h3 className={styles.title}>Jobs</h3>
        <div className={styles.filters}>
          <div className={styles.filterGroup}>
            <label className={styles.filterLabel}>Type:</label>
            {(['all', 'train', 'predict', 'drift', 'other'] as const).map((f) => (
              <button
                key={f}
                onClick={() => setTypeFilter(f)}
                className={`${styles.filterButton} ${typeFilter === f ? styles.active : ''}`}
              >
                {f.charAt(0).toUpperCase() + f.slice(1)}
              </button>
            ))}
          </div>
          <div className={styles.filterGroup}>
            <label className={styles.filterLabel}>Status:</label>
            {(['all', 'queued', 'running', 'completed', 'failed'] as const).map((f) => (
              <button
                key={f}
                onClick={() => setStatusFilter(f)}
                className={`${styles.filterButton} ${statusFilter === f ? styles.active : ''}`}
              >
                {f.charAt(0).toUpperCase() + f.slice(1)}
              </button>
            ))}
          </div>
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
                <div className={styles.jobHeaderLeft}>
                  <span className={`${styles.typeBadge} ${getTypeColor(job.job_type)}`}>
                    {job.job_type}
                  </span>
                  <span className={`${styles.statusBadge} ${getStatusColor(job.status)}`}>
                    {job.status}
                  </span>
                  {job.stage && (
                    <span className={styles.stageBadge}>
                      {job.stage}
                    </span>
                  )}
                </div>
                <span className={styles.jobId}>{job.job_id}</span>
              </div>
              <div className={styles.jobDetails}>
                <div className={styles.jobDetailRow}>
                  <span className={styles.detailLabel}>Model:</span>
                  <span className={styles.detailValue}>{job.model_key}</span>
                </div>
                {job.dataset_size && (
                  <div className={styles.jobDetailRow}>
                    <span className={styles.detailLabel}>Dataset Size:</span>
                    <span className={styles.detailValue}>{job.dataset_size} items</span>
                  </div>
                )}
                <div className={styles.jobDetailRow}>
                  <span className={styles.detailLabel}>Source:</span>
                  <span className={styles.detailValue}>{getSourceLabel(job.source)}</span>
                </div>
                {job.client_ip && (
                  <div className={styles.jobDetailRow}>
                    <span className={styles.detailLabel}>IP:</span>
                    <span className={`${styles.detailValue} ${styles.ipValue}`}>
                      {job.client_ip}
                    </span>
                  </div>
                )}
                {job.user_agent && (
                  <div className={styles.jobDetailRow}>
                    <span className={styles.detailLabel}>User-Agent:</span>
                    <span className={`${styles.detailValue} ${styles.userAgentValue}`}>
                      {job.user_agent}
                    </span>
                  </div>
                )}
                {job.created_at && (
                  <div className={styles.jobDetailRow}>
                    <span className={styles.detailLabel}>Created:</span>
                    <span className={styles.detailValue}>
                      {new Date(job.created_at).toLocaleString()}
                    </span>
                  </div>
                )}
                {job.started_at && (
                  <div className={styles.jobDetailRow}>
                    <span className={styles.detailLabel}>Started:</span>
                    <span className={styles.detailValue}>
                      {new Date(job.started_at).toLocaleString()}
                    </span>
                  </div>
                )}
                {job.completed_at && (
                  <div className={styles.jobDetailRow}>
                    <span className={styles.detailLabel}>Completed:</span>
                    <span className={styles.detailValue}>
                      {new Date(job.completed_at).toLocaleString()}
                    </span>
                  </div>
                )}
                {job.error_message && (
                  <div className={styles.jobDetailRow}>
                    <span className={styles.detailLabel}>Error:</span>
                    <span className={`${styles.detailValue} ${styles.error}`}>
                      {job.error_message}
                    </span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

