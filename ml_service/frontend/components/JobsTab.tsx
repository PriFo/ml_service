'use client';

import React, { useState, useEffect } from 'react';
import { useAppStore } from '@/lib/store';
import { api } from '@/lib/api';
import { useModal } from '@/lib/hooks/useModal';
import Modal from './Modal';
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
  const { state, dispatch } = useAppStore();
  const { modal, showConfirm, showError, showSuccess } = useModal();
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
    // Only load if authenticated
    if (!state.isAuthenticated) {
      return;
    }
    loadModels();
  }, [state.isAuthenticated]);

  useEffect(() => {
    // Only load if authenticated
    if (!state.isAuthenticated) {
      return;
    }
    loadJobs();
  }, [filters, state.isAuthenticated]);

  const loadModels = async () => {
    if (!state.isAuthenticated) {
      return;
    }

    try {
      const response = await api.getModels();
      setModels(response.models?.map((m: any) => m.model_key) || []);
    } catch (error: any) {
      console.error('Failed to load models:', error);
      
      // Check if it's a 401 error
      const isUnauthorized = error.status === 401 || 
                            error.message?.includes('401') || 
                            error.message?.includes('Unauthorized') ||
                            error.message?.includes('Invalid or expired authentication token') ||
                            error.message?.includes('Missing authentication token');
      
      if (isUnauthorized) {
        dispatch({ type: 'LOGOUT' });
        if (typeof window !== 'undefined') {
          window.location.href = '/';
        }
      }
    }
  };

  const loadJobs = async () => {
    if (!state.isAuthenticated) {
      return;
    }

    setLoading(true);
    try {
      const params: any = { limit: 100 };
      if (filters.type !== 'all') {
        params.job_type = filters.type;
      }
      if (filters.status !== 'all') {
        params.status = filters.status;
      }
      if (filters.model !== 'all') {
        params.model_key = filters.model;
      }
      
      const response = await api.listJobs(params);
      setJobs(response.jobs || []);
    } catch (error: any) {
      console.error('Failed to load jobs:', error);
      
      // Check if it's a 401 error
      const isUnauthorized = error.status === 401 || 
                            error.message?.includes('401') || 
                            error.message?.includes('Unauthorized') ||
                            error.message?.includes('Invalid or expired authentication token') ||
                            error.message?.includes('Missing authentication token');
      
      if (isUnauthorized) {
        dispatch({ type: 'LOGOUT' });
        if (typeof window !== 'undefined') {
          window.location.href = '/';
        }
        return;
      }
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = async (jobId: string) => {
    if (!state.isAuthenticated) {
      return;
    }

    const job = jobs.find(j => j.job_id === jobId);
    const jobType = job?.job_type || job?.type || 'задание';
    const confirmed = await showConfirm(
      `Вы уверены, что хотите отменить ${jobType} задание "${jobId}"?`,
      'Подтверждение отмены'
    );
    if (!confirmed) {
      return;
    }

    try {
      await api.cancelJob(jobId);
      await showSuccess('Задание успешно отменено');
      loadJobs();
    } catch (error: any) {
      console.error('Failed to cancel job:', error);
      
      // Check if it's a 401 error
      const isUnauthorized = error.status === 401 || 
                            error.message?.includes('401') || 
                            error.message?.includes('Unauthorized') ||
                            error.message?.includes('Invalid or expired authentication token') ||
                            error.message?.includes('Missing authentication token');
      
      if (isUnauthorized) {
        dispatch({ type: 'LOGOUT' });
        if (typeof window !== 'undefined') {
          window.location.href = '/';
        }
      } else {
        await showError(`Не удалось отменить задание: ${error.message || 'Неизвестная ошибка'}`);
      }
    }
  };

  return (
    <>
      <Modal
        isOpen={modal.isOpen}
        type={modal.type}
        title={modal.title}
        message={modal.message}
        onConfirm={modal.onConfirm}
        onCancel={modal.onCancel}
        confirmText={modal.confirmText}
        cancelText={modal.cancelText}
      />
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
    </>
  );
}

