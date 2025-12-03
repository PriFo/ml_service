// TypeScript interfaces
export type Theme = 'system' | 'light' | 'dark';

export interface Model {
  model_key: string;
  versions: string[];
  active_version: string;
  status: string;
  accuracy?: number;
  last_trained?: string;
}

export interface Alert {
  alert_id: string;
  type: string;
  severity: 'info' | 'warning' | 'critical';
  model_key?: string;
  message: string;
  details?: Record<string, any>;
  created_at: string;
  dismissible: boolean;
}

export interface DriftReport {
  check_id: string;
  model_key: string;
  check_date: string;
  psi_value?: number;
  js_divergence?: number;
  drift_detected: boolean;
  items_analyzed?: number;
  created_at: string;
}

export interface Consent {
  essential: boolean;
  analytics: boolean;
  preferences: boolean;
  timestamp: number;
}

export interface Job {
  job_id: string;
  model_key: string;
  job_type: 'train' | 'predict' | 'drift' | 'other';
  status: 'queued' | 'running' | 'completed' | 'failed';
  stage?: string;
  source: 'api' | 'gui' | 'system';
  dataset_size?: number;
  created_at?: string;
  started_at?: string;
  completed_at?: string;
  metrics?: Record<string, any>;
  error_message?: string;
  client_ip?: string;
  user_agent?: string;
}

// Backward compatibility alias
export type TrainingJob = Job;

export interface Event {
  event_id: string;
  event_type: 'drift' | 'predict' | 'train';
  source: 'api' | 'gui' | 'system';
  model_key?: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  stage?: string;
  input_data?: Record<string, any>;
  output_data?: Record<string, any>;
  user_agent?: string;
  client_ip?: string;
  created_at: string;
  completed_at?: string;
  error_message?: string;
}

export interface ModelVersion {
  version: string;
  status: string;
  accuracy?: number;
  created_at?: string;
  last_trained?: string;
  task_type?: string;
  target_field?: string;
  feature_fields: string[];
}

export interface ModelDetails {
  model_key: string;
  current_version: string;
  versions: ModelVersion[];
  recent_jobs: Job[];
}

export interface ServiceStatus {
  status: 'healthy' | 'degraded' | 'down';
  version: string;
  timestamp: string;
  uptime?: number;
  errors?: string[];
}

export interface AppState {
  theme: Theme;
  selectedModel: string | null;
  models: Model[];
  alerts: Alert[];
  recentDrift: DriftReport[];
  cookieConsent: Consent | null;
  isLoading: boolean;
  error: string | null;
  isAuthenticated: boolean;
  userToken: string | null;
  userTier: string | null; // 'admin' | 'premium' | 'basic' | null
}

