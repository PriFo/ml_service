'use client';

import React, { useState, useEffect } from 'react';
import JobCard from './JobCard';
import styles from './JobsTab.module.css';

interface Job {
  job_id: string;
  type?: string;
  job_type?: string;
  status: string;
  model_key?: string;
  [key: string]: any;
}

export default function JobsTab() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [filters, setFilters] = useState({
    type: 'all',
    status: 'all',
    model: 'all',
  });
  const [loading, setLoading] = useState(false);
  const [models, setModels] = useState<string[]>([]);
  const [selectedJobDetails, setSelectedJobDetails] = useState<Job | null>(null);

  useEffect(() => {
    loadModels();
  }, []);

  useEffect(() => {
    loadJobs();
  }, [filters]);

  const loadModels = async () => {
    try {
      const response = await fetch('/api/models');
      const data = await response.json();
      setModels(data.models?.map((m: any) => m.model_key) || []);
    } catch (error) {
      console.error('Failed to load models:', error);
    }
  };

  const loadJobs = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filters.type !== 'all') {
        params.append('job_type', filters.type);
      }
      if (filters.status !== 'all') {
        params.append('status', filters.status);
      }
      if (filters.model !== 'all') {
        params.append('model_key', filters.model);
      }
      const response = await fetch(`/api/jobs?${params}`);
      const data = await response.json();
      setJobs(data.jobs || []);
    } catch (error) {
      console.error('Failed to load jobs:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = async (jobId: string) => {
    try {
      await fetch(`/api/jobs/${jobId}/cancel`, { method: 'POST' });
      loadJobs();
    } catch (error) {
      console.error('Failed to cancel job:', error);
    }
  };

  return (
    <div className={styles.jobsTab}>
      <div className={styles.filtersPanel}>
        <div className={styles.filterGroup}>
          <label>Type:</label>
          <select
            value={filters.type}
            onChange={(e) => setFilters({ ...filters, type: e.target.value })}
          >
            <option value="all">All</option>
            <option value="train">Train</option>
            <option value="predict">Predict</option>
            <option value="retrain">Retrain</option>
          </select>
        </div>

        <div className={styles.filterGroup}>
          <label>Status:</label>
          <select
            value={filters.status}
            onChange={(e) => setFilters({ ...filters, status: e.target.value })}
          >
            <option value="all">All</option>
            <option value="queued">Queued</option>
            <option value="running">Running</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>

        <div className={styles.filterGroup}>
          <label>Model:</label>
          <select
            value={filters.model}
            onChange={(e) => setFilters({ ...filters, model: e.target.value })}
          >
            <option value="all">All</option>
            {models.map((model) => (
              <option key={model} value={model}>
                {model}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className={styles.jobsList}>
        {loading ? (
          <div>Loading jobs...</div>
        ) : jobs.length === 0 ? (
          <div>No jobs found</div>
        ) : (
          jobs.map((job) => (
            <JobCard
              key={job.job_id}
              job={job}
              onCancel={handleCancel}
              onDetails={(id) => {
                const job = jobs.find(j => j.job_id === id);
                if (job) setSelectedJobDetails(job);
              }}
            />
          ))
        )}
      </div>

      {selectedJobDetails && (
        <div className={styles.modal} onClick={() => setSelectedJobDetails(null)}>
          <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <h3>Job Details</h3>
              <button className={styles.closeButton} onClick={() => setSelectedJobDetails(null)}>×</button>
            </div>
            <div className={styles.modalBody}>
              <div className={styles.detailRow}>
                <strong>Job ID:</strong> {selectedJobDetails.job_id}
              </div>
              <div className={styles.detailRow}>
                <strong>Type:</strong> {selectedJobDetails.job_type || selectedJobDetails.type || 'unknown'}
              </div>
              <div className={styles.detailRow}>
                <strong>Status:</strong> {selectedJobDetails.status}
              </div>
              {selectedJobDetails.model_key && (
                <div className={styles.detailRow}>
                  <strong>Model:</strong> {selectedJobDetails.model_key}
                </div>
              )}
              {selectedJobDetails.created_at && (
                <div className={styles.detailRow}>
                  <strong>Created:</strong> {new Date(selectedJobDetails.created_at).toLocaleString()}
                </div>
              )}
              {selectedJobDetails.started_at && (
                <div className={styles.detailRow}>
                  <strong>Started:</strong> {new Date(selectedJobDetails.started_at).toLocaleString()}
                </div>
              )}
              {selectedJobDetails.completed_at && (
                <div className={styles.detailRow}>
                  <strong>Completed:</strong> {new Date(selectedJobDetails.completed_at).toLocaleString()}
                </div>
              )}
              {selectedJobDetails.error_message && (
                <div className={styles.detailRow}>
                  <strong>Error:</strong> <span className={styles.errorText}>{selectedJobDetails.error_message}</span>
                </div>
              )}
              {selectedJobDetails.metrics && (
                <div className={styles.detailRow}>
                  <strong>Metrics:</strong>
                  <pre className={styles.metricsPre}>{JSON.stringify(JSON.parse(selectedJobDetails.metrics), null, 2)}</pre>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

