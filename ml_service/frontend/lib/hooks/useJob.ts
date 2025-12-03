import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '../api';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8085';
const getWebSocketUrl = (path: string) => {
  const wsProtocol = API_URL.startsWith('https') ? 'wss' : 'ws';
  const wsHost = API_URL.replace(/^https?:\/\//, '').replace(/\/$/, '');
  return `${wsProtocol}://${wsHost}${path}`;
};

interface Job {
  job_id: string;
  status: string;
  progress?: {
    current: number;
    total: number;
    percent: number;
  };
  [key: string]: any;
}

interface UseJobResult {
  job: Job | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export function useJob(jobId: string | null): UseJobResult {
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const fetchJob = useCallback(async () => {
    if (!jobId) {
      setJob(null);
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const jobData = await api.getJobStatus(jobId);
      setJob(jobData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    fetchJob();

    // Connect WebSocket for real-time updates
    if (jobId) {
      const wsUrl = getWebSocketUrl(`/ws/jobs/${jobId}`);
      
      const connectWebSocket = () => {
        try {
          const ws = new WebSocket(wsUrl);
          wsRef.current = ws;

          ws.onopen = () => {
            console.log(`WebSocket connected for job ${jobId}`);
            setError(null); // Clear any previous connection errors
          };

          ws.onmessage = (event) => {
            try {
              const message = JSON.parse(event.data);
              
              if (message.type === 'job:status') {
                setJob(message.job || { ...job, status: message.status });
              } else if (message.type === 'job:progress') {
                setJob((prevJob) => ({
                  ...prevJob,
                  progress: message.progress,
                } as Job));
              } else if (message.type === 'job:final') {
                setJob(message.job);
                ws.close();
                wsRef.current = null;
              }
            } catch (err) {
              console.error('Error parsing WebSocket message:', err);
            }
          };

          ws.onerror = (err) => {
            // WebSocket error event doesn't provide much info, log connection issue
            console.warn(`WebSocket connection error for job ${jobId}. This is usually harmless if the job is already completed.`);
            // Don't set error state for WebSocket errors as they're not critical
            // The job status can still be fetched via polling
          };

          ws.onclose = (event) => {
            wsRef.current = null;
            // Only reconnect if it wasn't a clean close and job is still active
            if (event.code !== 1000 && job && !['completed', 'failed', 'cancelled'].includes(job.status)) {
              reconnectTimeoutRef.current = setTimeout(() => {
                connectWebSocket();
              }, 2000);
            }
          };
        } catch (err) {
          console.error('Failed to connect WebSocket:', err);
          // Don't set error state - WebSocket is optional, polling will work
        }
      };

      connectWebSocket();

      return () => {
        if (wsRef.current) {
          wsRef.current.close();
          wsRef.current = null;
        }
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current);
        }
      };
    }
  }, [jobId, fetchJob]);

  const refetch = useCallback(async () => {
    await fetchJob();
  }, [fetchJob]);

  return { job, loading, error, refetch };
}

