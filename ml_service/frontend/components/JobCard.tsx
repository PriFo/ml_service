'use client';

import React from 'react';
import ProgressBar from './ProgressBar';
import styles from './JobCard.module.css';

interface Job {
  job_id: string;
  type?: string;
  job_type?: string;
  status: string;
  progress?: {
    current: number;
    total: number;
    percent: number;
  };
  model_key?: string;
  created_at?: string;
  [key: string]: any;
}

interface JobCardProps {
  job: Job;
  onCancel?: (jobId: string) => void;
  onDetails?: (jobId: string) => void;
}

export default function JobCard({ job, onCancel, onDetails }: JobCardProps) {
  const jobType = job.type || job.job_type || 'unknown';
  const status = job.status || 'queued';
  const progress = job.progress?.percent || 0;

  const getStatusIcon = () => {
    switch (status) {
      case 'queued':
        return '⏳';
      case 'running':
        return '⚙️';
      case 'completed':
        return '✓';
      case 'failed':
        return '✗';
      default:
        return '○';
    }
  };

  const getTypeColor = () => {
    switch (jobType) {
      case 'train':
        return '#8b5cf6';
      case 'predict':
        return '#3b82f6';
      case 'retrain':
        return '#f59e0b';
      default:
        return '#6b7280';
    }
  };

  const typeColor = getTypeColor();

  return (
    <div className={styles.jobCard} style={{ borderLeftColor: typeColor }}>
      <div className={styles.jobHeader}>
        <div className={styles.jobTypeBadge} style={{ backgroundColor: `${typeColor}20` }}>
          {jobType}
        </div>
        <div className={styles.jobStatus}>
          <span className={styles.statusIcon}>{getStatusIcon()}</span>
          <span>{status}</span>
        </div>
      </div>

      <div className={styles.jobInfo}>
        <div className={styles.jobId}>Job ID: {job.job_id}</div>
        {job.model_key && (
          <div className={styles.modelKey}>Model: {job.model_key}</div>
        )}
        {job.progress && (
          <div className={styles.progressInfo}>
            Progress: {job.progress.current} / {job.progress.total}
          </div>
        )}
      </div>

      <div className={styles.progressSection}>
        <ProgressBar progress={progress} status={status as any} />
      </div>

      <div className={styles.jobActions}>
        {status === 'running' && onCancel && (
          <button
            className={styles.cancelButton}
            onClick={() => onCancel(job.job_id)}
          >
            Cancel
          </button>
        )}
        {onDetails && (
          <button
            className={styles.detailsButton}
            onClick={() => onDetails(job.job_id)}
          >
            Details
          </button>
        )}
      </div>
    </div>
  );
}

