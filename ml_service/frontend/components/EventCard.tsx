'use client';

import React, { useState } from 'react';
import styles from './EventCard.module.css';
import ProgressBar from './ProgressBar';
import EventDetailsModal from './EventDetailsModal';

interface Event {
  event_id: string;
  event_type: string;
  status: string;
  stage?: string;
  created_at: string;
  duration_ms?: number;
  data_size_bytes?: number;
  client_ip?: string;
  user_agent?: string;
  input_data?: any;
  output_data?: any;
  [key: string]: any;
}

interface EventCardProps {
  event: Event;
}

export default function EventCard({ event }: EventCardProps) {
  const [showDetails, setShowDetails] = useState(false);

  const getTypeColor = () => {
    switch (event.event_type) {
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

  const getStatusColor = () => {
    const status = event.status?.toLowerCase();
    switch (status) {
      case 'failed':
        return '#dc2626';
      case 'completed':
        return '#10b981';
      case 'queued':
        return '#6b7280';
      case 'running':
        return '#3b82f6';
      case 'cancelled':
      case 'canceled':
        return '#9ca3af';
      case 'warning':
        return '#f59e0b';
      case 'suspicious':
        return '#f97316';
      default:
        return '#6b7280';
    }
  };

  const getProgress = (): number => {
    const status = event.status?.toLowerCase();
    const eventType = event.event_type?.toLowerCase();
    const stage = event.stage?.toLowerCase();

    if (status === 'queued') {
      return 0;
    }

    if (status === 'completed') {
      return 100;
    }

    if (status === 'failed') {
      // For failed events, return progress based on last stage
      if (eventType === 'train' || eventType === 'retrain') {
        if (stage === 'loading_data') return 10;
        if (stage === 'preparing_features') return 30;
        if (stage === 'training') return 50;
        if (stage === 'validating') return 80;
        return 0;
      }
      // For predict, try to get from output_data
      if (eventType === 'predict' && event.output_data) {
        try {
          const output = typeof event.output_data === 'string' 
            ? JSON.parse(event.output_data) 
            : event.output_data;
          if (output.processing_stats) {
            const { total, processed } = output.processing_stats;
            if (total > 0) {
              return Math.round((processed / total) * 100);
            }
          }
        } catch (e) {
          // Ignore parse errors
        }
      }
      return 0;
    }

    if (status === 'running') {
      // For train/retrain: determine by stage
      if (eventType === 'train' || eventType === 'retrain') {
        if (stage === 'loading_data') return 10;
        if (stage === 'preparing_features') return 30;
        if (stage === 'training') return 50;
        if (stage === 'validating') return 80;
        return 0;
      }

      // For predict: calculate from output_data
      if (eventType === 'predict' && event.output_data) {
        try {
          const output = typeof event.output_data === 'string' 
            ? JSON.parse(event.output_data) 
            : event.output_data;
          if (output.processing_stats) {
            const { total, processed } = output.processing_stats;
            if (total > 0) {
              return Math.round((processed / total) * 100);
            }
          }
        } catch (e) {
          // Ignore parse errors
        }
      }
      return 0;
    }

    return 0;
  };

  const color = getTypeColor();
  const statusColor = getStatusColor();
  const progress = getProgress();

  return (
    <div className={styles.eventCard} style={{ borderLeftColor: color }}>
      <div className={styles.eventHeader}>
        <div
          className={styles.eventTypeBadge}
          style={{ backgroundColor: `${color}20` }}
        >
          {event.event_type}
        </div>
        <div 
          className={styles.eventStatus}
          style={{ 
            color: statusColor,
            backgroundColor: `${statusColor}20`,
            padding: '0.25rem 0.75rem',
            borderRadius: '4px',
            fontWeight: 600,
            fontSize: '0.75rem',
            textTransform: 'uppercase'
          }}
        >
          {event.status}
        </div>
      </div>

      <div className={styles.eventInfo}>
        {event.stage && (
          <div className={styles.stageInfo}>Stage: {event.stage}</div>
        )}
        {(event.status === 'running' || event.status === 'queued' || event.status === 'failed') && (
          <div className={styles.progressContainer}>
            <ProgressBar 
              progress={progress} 
              status={event.status as any}
              color={color}
            />
          </div>
        )}
        {event.data_size_bytes && (
          <div>Data: {event.data_size_bytes} bytes</div>
        )}
        {event.duration_ms && <div>Duration: {event.duration_ms}ms</div>}
        {event.client_ip && (
          <div>
            User: {event.client_ip} {event.user_agent && `(${event.user_agent})`}
          </div>
        )}
        <div>Created: {new Date(event.created_at).toLocaleString()}</div>
      </div>

      <button
        className={styles.detailsButton}
        onClick={() => setShowDetails(!showDetails)}
      >
        {showDetails ? 'Скрыть детали' : 'Детали'}
      </button>

      {showDetails && (
        <EventDetailsModal
          event={event}
          isOpen={showDetails}
          onClose={() => setShowDetails(false)}
        />
      )}
    </div>
  );
}

