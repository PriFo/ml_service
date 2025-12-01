// API client using Fetch API
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8085';
const WS_URL = process.env.NEXT_PUBLIC_WEBSOCKET_URL || 'ws://localhost:8085/ws';

interface RequestOptions {
  method?: string;
  body?: any;
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

async function httpRequest<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const token = typeof window !== 'undefined' 
    ? sessionStorage.getItem('api_token') || localStorage.getItem('api_token') || ''
    : '';

  try {
    const response = await fetch(`${API_URL}${endpoint}`, {
      method: options.method || 'GET',
      headers: {
        'Content-Type': 'application/json',
        'X-Admin-Token': token,
        ...options.headers,
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
      signal: options.signal,
    });

    if (!response.ok) {
      let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
      try {
        const errorData = await response.json();
        if (errorData.detail) {
          errorMessage = errorData.detail;
        }
      } catch {
        // If response is not JSON, use status text
      }
      throw new Error(errorMessage);
    }

    return response.json();
  } catch (error) {
    // Handle network errors
    if (error instanceof TypeError && error.message === 'Failed to fetch') {
      throw new Error(`Unable to connect to backend at ${API_URL}. Please ensure the backend is running.`);
    }
    // Re-throw other errors
    throw error;
  }
}

// API methods
export const api = {
  getModels: () => httpRequest<{ models: any[] }>('/models'),
  
  getModel: (key: string) => httpRequest(`/models/${key}`),
  
  trainModel: (data: any) => httpRequest('/train', {
    method: 'POST',
    body: data,
  }),
  
  predict: (modelKey: string, data: any[], version?: string) => httpRequest<{ job_id: string; status: string; model_key: string; version?: string; estimated_time?: number }>('/predict', {
    method: 'POST',
    body: {
      model_key: modelKey,
      version: version,
      data: data,
    },
  }),

  getPredictResult: (jobId: string) => httpRequest<{ job_id: string; status: string; predictions?: any[]; processing_time_ms?: number; unexpected_items?: any[]; error_message?: string }>(`/predict/${jobId}`),
  
  getQuality: (modelKey: string, version?: string) => httpRequest('/quality', {
    method: 'POST',
    body: { model_key: modelKey, version },
  }),
  
  getDriftReports: (modelKey?: string) => {
    const endpoint = modelKey 
      ? `/drift/daily-reports?model_key=${modelKey}`
      : '/drift/daily-reports';
    return httpRequest<{ reports: any[] }>(endpoint);
  },
  
  getAlerts: () => httpRequest<{ alerts: any[] }>('/health/alerts'),
  
  dismissAlert: (alertId: string) => httpRequest(`/health/alerts/${alertId}/dismiss`, {
    method: 'POST',
  }),

  getJobStatus: (jobId: string) => httpRequest(`/jobs/${jobId}`),

  listJobs: (params?: { model_key?: string; status?: string; job_type?: string; limit?: number }) => {
    const query = new URLSearchParams();
    if (params?.model_key) query.append('model_key', params.model_key);
    if (params?.status) query.append('status', params.status);
    if (params?.job_type) query.append('job_type', params.job_type);
    if (params?.limit) query.append('limit', params.limit.toString());
    const endpoint = query.toString() ? `/jobs?${query}` : '/jobs';
    return httpRequest<{ jobs: any[] }>(endpoint);
  },

  getJobStatus: (jobId: string) => httpRequest<{ job_id: string; status: string; stage?: string; model_key: string; job_type: string; error_message?: string }>(`/jobs/${jobId}`),

  getModelDetails: (modelKey: string, version?: string) => {
    const endpoint = version 
      ? `/models/${modelKey}?version=${version}`
      : `/models/${modelKey}`;
    return httpRequest(endpoint);
  },

  getHealthStatus: () => httpRequest('/health'),

  // Events
  getEvents: (params?: { event_type?: string; source?: string; status?: string; client_ip?: string; limit?: number }) => {
    const query = new URLSearchParams();
    if (params?.event_type) query.append('event_type', params.event_type);
    if (params?.source) query.append('source', params.source);
    if (params?.status) query.append('status', params.status);
    if (params?.client_ip) query.append('client_ip', params.client_ip);
    if (params?.limit) query.append('limit', params.limit.toString());
    const endpoint = query.toString() ? `/events?${query}` : '/events';
    return httpRequest<{ events: any[] }>(endpoint);
  },

  getEvent: (eventId: string) => httpRequest(`/events/${eventId}`),

  getSuspiciousEvents: (limit?: number) => {
    const endpoint = limit ? `/events/suspicious?limit=${limit}` : '/events/suspicious';
    return httpRequest<{ events: any[] }>(endpoint);
  },

  getEventsByIp: (ip: string, limit?: number) => {
    const endpoint = limit ? `/events/by-ip/${ip}?limit=${limit}` : `/events/by-ip/${ip}`;
    return httpRequest<{ events: any[] }>(endpoint);
  },

  checkDrift: (data: any) => httpRequest('/drift/check', {
    method: 'POST',
    body: data,
  }),
};

// WebSocket client
export class WebSocketClient {
  private ws: WebSocket | null = null;
  private listeners: Map<string, Function[]> = new Map();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(WS_URL);
        
        this.ws.onopen = () => {
          console.log('WebSocket connected');
          this.reconnectAttempts = 0;
          resolve();
        };
        
        this.ws.onmessage = (event) => {
          try {
            const { type, payload } = JSON.parse(event.data);
            const handlers = this.listeners.get(type) || [];
            handlers.forEach(handler => handler(payload));
          } catch (e) {
            console.error('Error parsing WebSocket message:', e);
          }
        };
        
        this.ws.onerror = (event: Event) => {
          // WebSocket onerror receives Event, not Error
          // Only log if WebSocket is not already closed (onclose will handle that)
          if (this.ws?.readyState !== WebSocket.CLOSED && this.ws?.readyState !== WebSocket.CLOSING) {
            console.warn('WebSocket connection error - attempting to reconnect...');
          }
          // Don't reject here - let onclose handle reconnection
        };
        
        this.ws.onclose = (event) => {
          const wasClean = event.wasClean;
          const code = event.code;
          const reason = event.reason || 'Unknown reason';
          
          // Only log if it's not a clean disconnect or if it's an unexpected close
          if (!wasClean && code !== 1000) {
            // Common codes: 1006 = abnormal closure, 1001 = going away
            if (code === 1006) {
              console.warn('WebSocket connection lost - will attempt to reconnect');
            } else if (code !== 1001) {
              console.warn(`WebSocket disconnected (code: ${code})`);
            }
          }
          
          // Only reject if we haven't resolved yet (initial connection failed)
          if (this.reconnectAttempts === 0 && !wasClean && code !== 1001) {
            reject(new Error(`WebSocket connection failed: ${reason}`));
          }
          
          // Attempt reconnection (skip if it was a clean close or going away)
          if (code !== 1000 && code !== 1001 && this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            setTimeout(() => {
              this.connect().catch(err => {
                // Only log if it's not a connection error (those are expected)
                if (!err.message.includes('connection failed')) {
                  console.warn('WebSocket reconnection attempt failed, will retry...');
                }
              });
            }, 1000 * this.reconnectAttempts);
          } else if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.warn('WebSocket: Max reconnection attempts reached, giving up');
          }
        };
      } catch (error) {
        reject(error);
      }
    });
  }

  on(eventType: string, handler: Function) {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, []);
    }
    this.listeners.get(eventType)!.push(handler);
  }

  off(eventType: string, handler: Function) {
    const handlers = this.listeners.get(eventType) || [];
    const index = handlers.indexOf(handler);
    if (index > -1) {
      handlers.splice(index, 1);
    }
  }

  send(type: string, payload: any) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type, payload }));
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

export const wsClient = new WebSocketClient();

