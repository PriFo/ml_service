'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { Event } from '@/lib/types';
import styles from './EventDashboard.module.css';

interface EventDashboardProps {
  eventId: string;
  onClose: () => void;
}

export default function EventDashboard({ eventId, onClose }: EventDashboardProps) {
  const [event, setEvent] = useState<Event | null>(null);
  const [loading, setLoading] = useState(true);
  const [showInputData, setShowInputData] = useState(false);
  const [showOutputData, setShowOutputData] = useState(false);
  const [relatedEvents, setRelatedEvents] = useState<Event[]>([]);

  useEffect(() => {
    const loadEvent = async () => {
      try {
        setLoading(true);
        const eventData = await api.getEvent(eventId);
        setEvent(eventData);

        // Load related events from same IP if available
        if (eventData.client_ip) {
          try {
            const related = await api.getEventsByIp(eventData.client_ip, 10);
            setRelatedEvents(related.events.filter(e => e.event_id !== eventId));
          } catch (err) {
            console.error('Failed to load related events:', err);
          }
        }
      } catch (error) {
        console.error('Failed to load event:', error);
      } finally {
        setLoading(false);
      }
    };

    loadEvent();
  }, [eventId]);

  const formatDataForTable = (data: Record<string, any>): Array<{ key: string; value: any }> => {
    if (!data) return [];
    return Object.entries(data).map(([key, value]) => ({
      key,
      value: typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)
    }));
  };

  const isSuspicious = event?.client_ip && event.source !== 'system';

  if (loading) {
    return (
      <div className={styles.overlay} onClick={onClose}>
        <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
          <div className={styles.loading}>Loading event details...</div>
        </div>
      </div>
    );
  }

  if (!event) {
    return (
      <div className={styles.overlay} onClick={onClose}>
        <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
          <div className={styles.error}>Event not found</div>
          <button className={styles.closeButton} onClick={onClose}>Close</button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <h2 className={styles.title}>Event Dashboard</h2>
          <button className={styles.closeButton} onClick={onClose}>×</button>
        </div>

        <div className={styles.content}>
          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>Event Information</h3>
            <div className={styles.infoGrid}>
              <div className={styles.infoItem}>
                <span className={styles.infoLabel}>Event ID:</span>
                <span className={styles.infoValue}>{event.event_id}</span>
              </div>
              <div className={styles.infoItem}>
                <span className={styles.infoLabel}>Type:</span>
                <span className={styles.infoValue}>{event.event_type}</span>
              </div>
              <div className={styles.infoItem}>
                <span className={styles.infoLabel}>Source:</span>
                <span className={styles.infoValue}>{event.source}</span>
              </div>
              <div className={styles.infoItem}>
                <span className={styles.infoLabel}>Status:</span>
                <span className={`${styles.infoValue} ${styles[`status-${event.status}`]}`}>
                  {event.status}
                </span>
              </div>
              {event.stage && (
                <div className={styles.infoItem}>
                  <span className={styles.infoLabel}>Stage:</span>
                  <span className={styles.infoValue}>{event.stage}</span>
                </div>
              )}
              {event.model_key && (
                <div className={styles.infoItem}>
                  <span className={styles.infoLabel}>Model:</span>
                  <span className={styles.infoValue}>{event.model_key}</span>
                </div>
              )}
              <div className={styles.infoItem}>
                <span className={styles.infoLabel}>Created:</span>
                <span className={styles.infoValue}>
                  {new Date(event.created_at).toLocaleString()}
                </span>
              </div>
              {event.completed_at && (
                <div className={styles.infoItem}>
                  <span className={styles.infoLabel}>Completed:</span>
                  <span className={styles.infoValue}>
                    {new Date(event.completed_at).toLocaleString()}
                  </span>
                </div>
              )}
            </div>
          </div>

          <div className={styles.section}>
            <h3 className={styles.sectionTitle}>Security Information</h3>
            <div className={`${styles.securityInfo} ${isSuspicious ? styles.suspicious : ''}`}>
              {event.client_ip && (
                <div className={styles.infoItem}>
                  <span className={styles.infoLabel}>Client IP:</span>
                  <span className={`${styles.infoValue} ${isSuspicious ? styles.suspiciousIp : ''}`}>
                    {event.client_ip}
                  </span>
                  {isSuspicious && (
                    <span className={styles.suspiciousBadge}>⚠️ Suspicious</span>
                  )}
                </div>
              )}
              {event.user_agent && (
                <div className={styles.infoItem}>
                  <span className={styles.infoLabel}>User-Agent:</span>
                  <span className={styles.infoValue}>{event.user_agent}</span>
                </div>
              )}
              {!event.client_ip && !event.user_agent && (
                <div className={styles.infoItem}>
                  <span className={styles.infoValue}>System event (no client information)</span>
                </div>
              )}
            </div>
          </div>

          {event.error_message && (
            <div className={styles.section}>
              <h3 className={styles.sectionTitle}>Error</h3>
              <div className={styles.errorMessage}>{event.error_message}</div>
            </div>
          )}

          <div className={styles.section}>
            <div className={styles.dataButtons}>
              <button
                className={styles.dataButton}
                onClick={() => setShowInputData(!showInputData)}
              >
                {showInputData ? 'Hide' : 'Show'} Input Data
              </button>
              <button
                className={styles.dataButton}
                onClick={() => setShowOutputData(!showOutputData)}
              >
                {showOutputData ? 'Hide' : 'Show'} Output Data
              </button>
            </div>

            {showInputData && event.input_data && (
              <div className={styles.dataSection}>
                <h4 className={styles.dataTitle}>Input Data</h4>
                <div className={styles.dataTable}>
                  <table>
                    <thead>
                      <tr>
                        <th>Key</th>
                        <th>Value</th>
                      </tr>
                    </thead>
                    <tbody>
                      {formatDataForTable(event.input_data).map((row, idx) => (
                        <tr key={idx}>
                          <td className={styles.tableKey}>{row.key}</td>
                          <td className={styles.tableValue}>
                            <pre>{row.value}</pre>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {showOutputData && event.output_data && (
              <div className={styles.dataSection}>
                <h4 className={styles.dataTitle}>Output Data</h4>
                <div className={styles.dataTable}>
                  <table>
                    <thead>
                      <tr>
                        <th>Key</th>
                        <th>Value</th>
                      </tr>
                    </thead>
                    <tbody>
                      {formatDataForTable(event.output_data).map((row, idx) => (
                        <tr key={idx}>
                          <td className={styles.tableKey}>{row.key}</td>
                          <td className={styles.tableValue}>
                            <pre>{row.value}</pre>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>

          {relatedEvents.length > 0 && (
            <div className={styles.section}>
              <h3 className={styles.sectionTitle}>
                Related Events from Same IP ({relatedEvents.length})
              </h3>
              <div className={styles.relatedEvents}>
                {relatedEvents.map((relatedEvent) => (
                  <div key={relatedEvent.event_id} className={styles.relatedEvent}>
                    <div className={styles.relatedEventHeader}>
                      <span className={styles.relatedEventType}>{relatedEvent.event_type}</span>
                      <span className={styles.relatedEventStatus}>{relatedEvent.status}</span>
                      <span className={styles.relatedEventTime}>
                        {new Date(relatedEvent.created_at).toLocaleString()}
                      </span>
                    </div>
                    {relatedEvent.model_key && (
                      <div className={styles.relatedEventModel}>
                        Model: {relatedEvent.model_key}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

