'use client';

import React, { useState, useEffect } from 'react';
import EventTile from './EventTile';
import EventCard from './EventCard';
import { api } from '@/lib/api';
import styles from './EventsTab.module.css';

interface Event {
  event_id: string;
  event_type: string;
  status: string;
  created_at: string;
  [key: string]: any;
}

export default function EventsTab() {
  const [events, setEvents] = useState<Event[]>([]);
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [selectedStatus, setSelectedStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const pageSize = 20;

  useEffect(() => {
    loadEvents();
  }, [selectedType, selectedStatus, page]);

  // Убрано автоматическое обновление - обновление только при ручном обновлении или при изменении фильтров

  const loadEvents = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        limit: pageSize.toString(),
        offset: ((page - 1) * pageSize).toString(),
      });
      if (selectedType) {
        params.append('event_type', selectedType);
      }
      if (selectedStatus) {
        params.append('status', selectedStatus);
      }
      const response = await api.getEvents({
        event_type: selectedType || undefined,
        status: selectedStatus || undefined,
        limit: pageSize,
      });
      setEvents(response.events || []);
    } catch (error) {
      console.error('Failed to load events:', error);
    } finally {
      setLoading(false);
    }
  };

  const getEventCounts = () => {
    // Count from loaded events (approximate)
    return {
      all: events.length,
      train: events.filter(e => e.event_type === 'train').length,
      predict: events.filter(e => e.event_type === 'predict').length,
      retrain: events.filter(e => e.event_type === 'retrain').length,
      alerts: events.filter(e => e.event_type === 'alert' || e.status === 'failed').length,
      warnings: events.filter(e => e.status === 'warning').length,
      suspicions: events.filter(e => e.status === 'suspicious').length,
      failed: events.filter(e => e.status === 'failed').length,
      completed: events.filter(e => e.status === 'completed').length,
      queued: events.filter(e => e.status === 'queued').length,
      running: events.filter(e => e.status === 'running').length,
      cancelled: events.filter(e => e.status === 'cancelled' || e.status === 'canceled').length,
    };
  };

  const counts = getEventCounts();

  return (
    <div className={styles.eventsTab}>
      <div className={styles.tilesPanel}>
        <div className={styles.tileSection}>
          <h4 className={styles.sectionTitle}>By Event Type</h4>
          <EventTile
            type="all"
            label="All Events"
            count={counts.all}
            color="#6b7280"
            active={selectedType === null && selectedStatus === null}
            onClick={() => { setSelectedType(null); setSelectedStatus(null); }}
          />
          <EventTile
            type="train"
            label="Train"
            count={counts.train}
            color="#8b5cf6"
            active={selectedType === 'train' && selectedStatus === null}
            onClick={() => { setSelectedType('train'); setSelectedStatus(null); }}
          />
          <EventTile
            type="predict"
            label="Predict"
            count={counts.predict}
            color="#3b82f6"
            active={selectedType === 'predict' && selectedStatus === null}
            onClick={() => { setSelectedType('predict'); setSelectedStatus(null); }}
          />
          <EventTile
            type="retrain"
            label="Retrain"
            count={counts.retrain}
            color="#f59e0b"
            active={selectedType === 'retrain' && selectedStatus === null}
            onClick={() => { setSelectedType('retrain'); setSelectedStatus(null); }}
          />
          <EventTile
            type="alerts"
            label="Alerts"
            count={counts.alerts}
            color="#ef4444"
            active={selectedType === 'alert' && selectedStatus === null}
            onClick={() => { setSelectedType('alert'); setSelectedStatus(null); }}
          />
          <EventTile
            type="warnings"
            label="Warnings"
            count={counts.warnings}
            color="#f59e0b"
            active={selectedStatus === 'warning'}
            onClick={() => { setSelectedType(null); setSelectedStatus('warning'); }}
          />
          <EventTile
            type="suspicions"
            label="Suspicions"
            count={counts.suspicions}
            color="#f97316"
            active={selectedStatus === 'suspicious'}
            onClick={() => { setSelectedType(null); setSelectedStatus('suspicious'); }}
          />
        </div>

        <div className={styles.tileSection}>
          <h4 className={styles.sectionTitle}>By Status</h4>
          <EventTile
            type="failed"
            label="Failed"
            count={counts.failed}
            color="#dc2626"
            active={selectedStatus === 'failed'}
            onClick={() => { setSelectedType(null); setSelectedStatus('failed'); }}
          />
          <EventTile
            type="completed"
            label="Completed"
            count={counts.completed}
            color="#10b981"
            active={selectedStatus === 'completed'}
            onClick={() => { setSelectedType(null); setSelectedStatus('completed'); }}
          />
          <EventTile
            type="queued"
            label="Queued"
            count={counts.queued}
            color="#6b7280"
            active={selectedStatus === 'queued'}
            onClick={() => { setSelectedType(null); setSelectedStatus('queued'); }}
          />
          <EventTile
            type="running"
            label="Running"
            count={counts.running}
            color="#3b82f6"
            active={selectedStatus === 'running'}
            onClick={() => { setSelectedType(null); setSelectedStatus('running'); }}
          />
          <EventTile
            type="cancelled"
            label="Canceled"
            count={counts.cancelled}
            color="#9ca3af"
            active={selectedStatus === 'cancelled' || selectedStatus === 'canceled'}
            onClick={() => { setSelectedType(null); setSelectedStatus('cancelled'); }}
          />
        </div>
      </div>

      <div className={styles.eventsList}>
        {loading ? (
          <div>Loading events...</div>
        ) : events.length === 0 ? (
          <div>No events found</div>
        ) : (
          <>
            {events.map((event) => (
              <EventCard key={event.event_id} event={event} />
            ))}
            <div className={styles.pagination}>
              <button
                disabled={page === 1}
                onClick={() => setPage(page - 1)}
              >
                Previous
              </button>
              <span>Page {page}</span>
              <button
                disabled={events.length < pageSize}
                onClick={() => setPage(page + 1)}
              >
                Next
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

