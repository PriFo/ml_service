'use client';

import React, { useState, useEffect } from 'react';
import { useAppStore } from '@/lib/store';
import { api } from '@/lib/api';
import styles from './OverviewTab.module.css';

export default function OverviewTab() {
  const { state } = useAppStore();
  const [stats, setStats] = useState<any>(null);
  const [models, setModels] = useState<any[]>([]);
  const [jobs, setJobs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  
  // Determine if user is admin based on tier
  const isAdmin = state.userTier === 'admin';

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000); // Update every 10 seconds
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const [statsData, modelsData, jobsData] = await Promise.all([
        api.getSchedulerStats(),
        api.getModels(),
        api.listJobs({ limit: 100 })
      ]);
      setStats(statsData);
      setModels(modelsData.models || []);
      setJobs(jobsData.jobs || []);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className={styles.loading}>Loading...</div>;
  if (!stats) return <div className={styles.error}>No stats available</div>;

  const systemResources = stats.system_resources || {};
  const queueStats = stats.queue_stats || {};
  const workerStats = stats.worker_stats || {};

  // Calculate job counts
  const activeJobs = jobs.filter(j => j.status === 'running');
  const queuedJobs = jobs.filter(j => j.status === 'queued');
  const failedJobs = jobs.filter(j => j.status === 'failed');
  const completedJobs = jobs.filter(j => j.status === 'completed');
  const allRequests = jobs.length;

  // Get unique models with versions
  const modelsWithVersions = models.reduce((acc: any, model: any) => {
    const existing = acc.find((m: any) => m.model_key === model.model_key);
    if (existing) {
      if (!existing.versions.includes(model.version)) {
        existing.versions.push(model.version);
      }
    } else {
      acc.push({
        model_key: model.model_key,
        versions: [model.version],
        status: model.status,
        accuracy: model.accuracy,
        last_trained: model.last_trained
      });
    }
    return acc;
  }, []);

  return (
    <div className={styles.overviewTab}>
      {/* 1. System Status + Service Status */}
      <div className={styles.row}>
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h3>System Status</h3>
          </div>
          <div className={styles.cardContent}>
            <div className={styles.statusIndicator}>
              <span className={stats.running ? styles.online : styles.offline}>
                {stats.running ? '●' : '○'}
              </span>
              <span>{stats.running ? 'Online' : 'Offline'}</span>
            </div>
          </div>
        </div>
        <div className={styles.section}>
          <h3 className={styles.sectionTitle}>Service Status</h3>
          <div className={styles.infoGrid}>
            <div className={styles.infoItem}>
              <span className={styles.infoLabel}>Status:</span>
              <span className={stats.running ? styles.statusOnline : styles.statusOffline}>
                {stats.running ? 'Online' : 'Offline'}
              </span>
            </div>
            <div className={styles.infoItem}>
              <span className={styles.infoLabel}>Scheduler:</span>
              <span>{stats.running ? 'Running' : 'Stopped'}</span>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Models (plate) + Models (frame) */}
      <div className={styles.row}>
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h3>Models</h3>
          </div>
          <div className={styles.cardContent}>
            <div className={styles.statValue}>{modelsWithVersions.length}</div>
            <div className={styles.statLabel}>Total Models</div>
          </div>
        </div>
        <div className={styles.section}>
          <h3 className={styles.sectionTitle}>Models ({modelsWithVersions.length})</h3>
          {modelsWithVersions.length === 0 ? (
            <div className={styles.empty}>No models available</div>
          ) : (
            <div className={styles.modelsList}>
              {modelsWithVersions.map((model: any) => (
                <div key={model.model_key} className={styles.modelItem}>
                  <div className={styles.modelHeader}>
                    <strong>{model.model_key}</strong>
                    <span className={styles.modelStatus}>{model.status || 'active'}</span>
                  </div>
                  <div className={styles.modelVersions}>
                    Versions: {model.versions.join(', ')}
                  </div>
                  {model.accuracy !== null && model.accuracy !== undefined && (
                    <div className={styles.modelAccuracy}>
                      Accuracy: {(model.accuracy * 100).toFixed(2)}%
                    </div>
                  )}
                  {model.last_trained && (
                    <div className={styles.modelDate}>
                      Last trained: {new Date(model.last_trained).toLocaleDateString()}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 3. (Vertical: CPU+RAM+GPU) + (Vertical: Server Specification+Resource Usage) */}
      <div className={styles.row}>
        <div className={styles.resourceCardsVertical}>
          <div className={styles.card}>
            <div className={styles.cardHeader}>
              <h3>CPU</h3>
            </div>
            <div className={styles.cardContent}>
              <div className={styles.statValue}>
                {systemResources.cpu_percent?.toFixed(1) || 'N/A'}%
              </div>
              <div className={styles.statLabel}>
                {systemResources.cpu_count || 'N/A'} cores
              </div>
            </div>
          </div>

          <div className={styles.card}>
            <div className={styles.cardHeader}>
              <h3>RAM</h3>
            </div>
            <div className={styles.cardContent}>
              <div className={styles.statValue}>
                {systemResources.memory_percent?.toFixed(1) || 'N/A'}%
              </div>
              <div className={styles.statLabel}>
                {systemResources.memory_total_gb 
                  ? `${systemResources.memory_used_gb?.toFixed(1) || 0} / ${systemResources.memory_total_gb.toFixed(1)} GB`
                  : 'N/A'}
              </div>
            </div>
          </div>

          {systemResources.gpu_available && (
            <div className={styles.card}>
              <div className={styles.cardHeader}>
                <h3>GPU</h3>
              </div>
              <div className={styles.cardContent}>
                <div className={styles.statValue}>
                  {systemResources.gpu_usage_percent?.toFixed(1) || 'N/A'}%
                </div>
                <div className={styles.statLabel}>
                  {systemResources.gpu_name || 'N/A'}
                </div>
              </div>
            </div>
          )}
        </div>

        <div className={styles.resourceFramesVertical}>
          {/* Server Specifications */}
          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>Server Specifications</h3>
            <div className={styles.specsGrid}>
              <div className={styles.specItem}>
                <span className={styles.specLabel}>CPU Cores:</span>
                <span>{systemResources.cpu_count || 'N/A'}</span>
              </div>
              <div className={styles.specItem}>
                <span className={styles.specLabel}>Total RAM:</span>
                <span>{systemResources.memory_total_gb ? `${systemResources.memory_total_gb.toFixed(1)} GB` : 'N/A'}</span>
              </div>
              {systemResources.gpu_available && (
                <div className={styles.specItem}>
                  <span className={styles.specLabel}>GPU:</span>
                  <span>{systemResources.gpu_name || 'N/A'}</span>
                </div>
              )}
            </div>
          </div>

          {/* Resource Usage */}
          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>Resource Usage</h3>
            <div className={styles.resourceUsage}>
              <div className={styles.resourceBar}>
                <div className={styles.resourceLabel}>
                  <span>CPU</span>
                  <span>{systemResources.cpu_percent?.toFixed(1) || 0}%</span>
                </div>
                <div className={styles.progressBar}>
                  <div 
                    className={styles.progressFill} 
                    style={{ width: `${systemResources.cpu_percent || 0}%` }}
                  />
                </div>
              </div>
              <div className={styles.resourceBar}>
                <div className={styles.resourceLabel}>
                  <span>Memory</span>
                  <span>{systemResources.memory_percent?.toFixed(1) || 0}%</span>
                </div>
                <div className={styles.progressBar}>
                  <div 
                    className={styles.progressFill} 
                    style={{ width: `${systemResources.memory_percent || 0}%` }}
                  />
                </div>
              </div>
              {systemResources.gpu_available && (
                <div className={styles.resourceBar}>
                  <div className={styles.resourceLabel}>
                    <span>GPU</span>
                    <span>{systemResources.gpu_usage_percent?.toFixed(1) || 0}%</span>
                  </div>
                  <div className={styles.progressBar}>
                    <div 
                      className={styles.progressFill} 
                      style={{ width: `${systemResources.gpu_usage_percent || 0}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 4. Active Requests (tile) + Active Requests List */}
      <div className={styles.row}>
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h3>Active Requests</h3>
          </div>
          <div className={styles.cardContent}>
            <div className={styles.statValue}>{activeJobs.length}</div>
            <div className={styles.statLabel}>Running</div>
          </div>
        </div>
        {isAdmin ? (
          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>Active Requests ({activeJobs.length})</h3>
            {activeJobs.length === 0 ? (
              <div className={styles.empty}>No active requests</div>
            ) : (
              <div className={styles.jobsList}>
                {activeJobs.slice(0, 10).map((job: any) => (
                  <div key={job.job_id} className={styles.jobItem}>
                    <div className={styles.jobHeader}>
                      <strong>{job.job_type || 'unknown'}</strong>
                      <span className={styles.jobStatus}>{job.status}</span>
                    </div>
                    <div className={styles.jobInfo}>
                      Model: {job.model_key || 'N/A'} | Job ID: {job.job_id?.substring(0, 8)}...
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>Active Requests</h3>
            <div className={styles.empty}>Access restricted to administrators</div>
          </div>
        )}
      </div>

      {/* Failed Requests (tile) + Failed Requests List */}
      <div className={styles.row}>
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h3>Failed Requests</h3>
          </div>
          <div className={styles.cardContent}>
            <div className={styles.statValue}>{failedJobs.length}</div>
            <div className={styles.statLabel}>Total Failed</div>
          </div>
        </div>
        {isAdmin ? (
          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>Failed Requests ({failedJobs.length})</h3>
            {failedJobs.length === 0 ? (
              <div className={styles.empty}>No failed requests</div>
            ) : (
              <div className={styles.jobsList}>
                {failedJobs.slice(0, 10).map((job: any) => (
                  <div key={job.job_id} className={styles.jobItem}>
                    <div className={styles.jobHeader}>
                      <strong>{job.job_type || 'unknown'}</strong>
                      <span className={styles.jobStatusFailed}>{job.status}</span>
                    </div>
                    <div className={styles.jobInfo}>
                      Model: {job.model_key || 'N/A'}
                    </div>
                    {job.error_message && (
                      <div className={styles.jobError}>
                        Error: {job.error_message.substring(0, 100)}...
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>Failed Requests</h3>
            <div className={styles.empty}>Access restricted to administrators</div>
          </div>
        )}
      </div>

      {/* Queued Requests (tile) + Queued Requests List */}
      <div className={styles.row}>
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h3>Queued Requests</h3>
          </div>
          <div className={styles.cardContent}>
            <div className={styles.statValue}>{queuedJobs.length}</div>
            <div className={styles.statLabel}>In Queue</div>
          </div>
        </div>
        {isAdmin ? (
          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>Queued Requests ({queuedJobs.length})</h3>
            {queuedJobs.length === 0 ? (
              <div className={styles.empty}>No queued requests</div>
            ) : (
              <div className={styles.jobsList}>
                {queuedJobs.slice(0, 10).map((job: any) => (
                  <div key={job.job_id} className={styles.jobItem}>
                    <div className={styles.jobHeader}>
                      <strong>{job.job_type || 'unknown'}</strong>
                      <span className={styles.jobStatusQueued}>{job.status}</span>
                    </div>
                    <div className={styles.jobInfo}>
                      Model: {job.model_key || 'N/A'} | Priority: {job.priority || 'N/A'}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>Queued Requests</h3>
            <div className={styles.empty}>Access restricted to administrators</div>
          </div>
        )}
      </div>
    </div>
  );
}
