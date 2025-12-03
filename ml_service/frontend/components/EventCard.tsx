'use client';

import React, { useState } from 'react';
import styles from './EventCard.module.css';

interface Event {
  event_id: string;
  event_type: string;
  status: string;
  created_at: string;
  duration_ms?: number;
  data_size_bytes?: number;
  client_ip?: string;
  user_agent?: string;
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

  const color = getTypeColor();

  return (
    <div className={styles.eventCard} style={{ borderLeftColor: color }}>
      <div className={styles.eventHeader}>
        <div
          className={styles.eventTypeBadge}
          style={{ backgroundColor: `${color}20` }}
        >
          {event.event_type}
        </div>
        <div className={styles.eventStatus}>{event.status}</div>
      </div>

      <div className={styles.eventInfo}>
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
        {showDetails ? 'Hide Details' : 'View Details'}
      </button>

      {showDetails && (
        <div className={styles.eventDetails}>
          <pre>{JSON.stringify(event, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}

