'use client';

import { useAppStore } from '@/lib/store';
import { api } from '@/lib/api';
import { useState, useEffect } from 'react';
import { Event } from '@/lib/types';
import styles from './EventFeed.module.css';
import EventDashboard from './EventDashboard';

interface EventItem {
  id: string;
  type: 'alert' | 'event' | 'job';
  severity: 'info' | 'warning' | 'critical' | 'success';
  title: string;
  description: string;
  timestamp: string;
  modelKey?: string;
  jobId?: string;
  eventId?: string;
  source?: 'api' | 'gui' | 'system';
  clientIp?: string;
  isSuspicious?: boolean;
}

export default function EventFeed() {
  const { state } = useAppStore();
  const [events, setEvents] = useState<EventItem[]>([]);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);

  useEffect(() => {
    const loadEvents = async () => {
      try {
        const [alertsResponse, eventsResponse, jobsResponse] = await Promise.all([
          api.getAlerts(),
          api.getEvents({ limit: 30 }),
          api.listJobs({ limit: 20 }),
        ]);

        const eventItems: EventItem[] = [];

        // Add alerts as events
        alertsResponse.alerts.forEach(alert => {
          eventItems.push({
            id: `alert-${alert.alert_id}`,
            type: 'alert',
            severity: alert.severity,
            title: alert.type || 'Alert',
            description: alert.message,
            timestamp: alert.created_at,
            modelKey: alert.model_key,
          });
        });

        // Add events (drift, predict, train)
        (eventsResponse.events || []).forEach((event: Event) => {
          let severity: 'info' | 'warning' | 'critical' | 'success' = 'info';
          let title = `${event.event_type.charAt(0).toUpperCase() + event.event_type.slice(1)} ${event.status}`;
          let description = `${event.event_type} request from ${event.source}`;
          
          if (event.status === 'completed') {
            severity = 'success';
          } else if (event.status === 'failed') {
            severity = 'critical';
            description += event.error_message ? `: ${event.error_message}` : '';
          } else if (event.status === 'running') {
            severity = 'info';
            description += ` (${event.stage || 'processing'})`;
          }

          // Check if suspicious (multiple events from same IP)
          const isSuspicious = event.client_ip && event.source !== 'system';

          eventItems.push({
            id: `event-${event.event_id}`,
            type: 'event',
            severity,
            title,
            description,
            timestamp: event.created_at,
            modelKey: event.model_key,
            eventId: event.event_id,
            source: event.source,
            clientIp: event.client_ip,
            isSuspicious,
          });
        });

        // Add jobs as events
        (jobsResponse.jobs || []).forEach((job: any) => {
          let severity: 'info' | 'warning' | 'critical' | 'success' = 'info';
          let description = `${job.job_type} job ${job.status} for model ${job.model_key}`;
          
          if (job.status === 'completed') {
            severity = 'success';
          } else if (job.status === 'failed') {
            severity = 'critical';
            description += job.error_message ? `: ${job.error_message}` : '';
          } else if (job.status === 'running') {
            severity = 'info';
            description += ` (${job.stage || 'processing'})`;
          }

          eventItems.push({
            id: `job-${job.job_id}`,
            type: 'job',
            severity,
            title: `${job.job_type.charAt(0).toUpperCase() + job.job_type.slice(1)} Job ${job.status}`,
            description,
            timestamp: job.created_at || new Date().toISOString(),
            modelKey: job.model_key,
            jobId: job.job_id,
            source: job.source,
            clientIp: job.client_ip,
          });
        });

        // Sort by timestamp (newest first)
        eventItems.sort((a, b) => 
          new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
        );

        setEvents(eventItems.slice(0, 50)); // Limit to 50 most recent
      } catch (error) {
        // Silently handle connection errors when backend is not running
        const errorMessage = error instanceof Error ? error.message : String(error);
        if (!errorMessage.includes('Unable to connect to backend')) {
          console.error('Failed to load events:', error);
        }
      }
    };

    loadEvents();
    const interval = setInterval(loadEvents, 5000); // Update every 5 seconds
    return () => clearInterval(interval);
  }, [state.alerts]);

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'critical': return '🚨';
      case 'warning': return '⚠️';
      case 'success': return '✅';
      default: return 'ℹ️';
    }
  };

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;
    return date.toLocaleDateString();
  };

  const handleEventClick = (event: EventItem) => {
    if (event.eventId) {
      setSelectedEventId(event.eventId);
    }
  };

  const handleCloseDashboard = () => {
    setSelectedEventId(null);
  };

  const getSourceLabel = (source?: string) => {
    switch (source) {
      case 'api': return 'API';
      case 'gui': return 'GUI';
      case 'system': return 'System';
      default: return '';
    }
  };

  return (
    <>
      <div className={styles.feed}>
        <h2 className={styles.title}>Event Feed</h2>
        <div className={styles.eventsList}>
          {events.length === 0 ? (
            <div className={styles.empty}>No events to display</div>
          ) : (
            events.map(event => (
              <div
                key={event.id}
                className={`${styles.eventItem} ${styles[`event-${event.severity}`]} ${event.isSuspicious ? styles.suspicious : ''} ${event.eventId ? styles.clickable : ''}`}
                onClick={() => event.eventId && handleEventClick(event)}
              >
                <div className={styles.eventIcon}>
                  {getSeverityIcon(event.severity)}
                </div>
                <div className={styles.eventContent}>
                  <div className={styles.eventHeader}>
                    <h3 className={styles.eventTitle}>{event.title}</h3>
                    <span className={styles.eventTime}>{formatTime(event.timestamp)}</span>
                  </div>
                  <p className={styles.eventDescription}>{event.description}</p>
                  <div className={styles.eventTags}>
                    {event.modelKey && (
                      <span className={styles.eventTag}>Model: {event.modelKey}</span>
                    )}
                    {event.jobId && (
                      <span className={styles.eventTag}>Job: {event.jobId}</span>
                    )}
                    {event.source && (
                      <span className={styles.eventTag}>Source: {getSourceLabel(event.source)}</span>
                    )}
                    {event.clientIp && (
                      <span className={`${styles.eventTag} ${event.isSuspicious ? styles.suspiciousIp : ''}`}>
                        IP: {event.clientIp}
                      </span>
                    )}
                    {event.isSuspicious && (
                      <span className={`${styles.eventTag} ${styles.suspiciousBadge}`}>
                        ⚠️ Suspicious
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
      {selectedEventId && (
        <EventDashboard eventId={selectedEventId} onClose={handleCloseDashboard} />
      )}
    </>
  );
}

