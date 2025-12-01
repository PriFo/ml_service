'use client';

import { useState } from 'react';
import { useAppStore } from '@/lib/store';
import AlertBanner from './AlertBanner';
import Sidebar from './Sidebar';
import ModelSelector from './ModelSelector';
import CookieConsent from './CookieConsent';
import ServiceMonitor from './ServiceMonitor';
import ModelManager from './ModelManager';
import Predictor from './Predictor';
import JobsTracker from './JobsTracker';
import AdminPanel from './AdminPanel';
import DashboardCards from './DashboardCards';
import EventFeed from './EventFeed';
import styles from './Dashboard.module.css';

type TabType = 'overview' | 'models' | 'predict' | 'jobs' | 'events';

export default function Dashboard() {
  const { state, dispatch } = useAppStore();
  const [activeTab, setActiveTab] = useState<TabType>('overview');

  return (
    <div className={styles.dashboard}>
      <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />
      
      <div className={styles.content}>
        <AlertBanner />
        
        <main className={styles.main}>
          {activeTab === 'overview' && (
            <>
              <DashboardCards />
              <ServiceMonitor />
              <EventFeed />
              <AdminPanel />
            </>
          )}

          {activeTab === 'models' && (
            <>
              <ModelManager />
              <ModelSelector />
            </>
          )}

          {activeTab === 'predict' && (
            <Predictor />
          )}

          {activeTab === 'jobs' && (
            <JobsTracker />
          )}

          {activeTab === 'events' && (
            <>
              <EventFeed />
              <DashboardCards />
            </>
          )}
          
          {state.isLoading && (
            <div className={styles.loading}>Loading...</div>
          )}
          
          {state.error && (
            <div className={styles.error}>
              <strong>Error:</strong> {state.error}
              <button
                onClick={() => dispatch({ type: 'SET_ERROR', payload: null })}
                className={styles.errorDismiss}
                aria-label="Dismiss error"
              >
                ×
              </button>
            </div>
          )}
        </main>
      </div>
      
      <CookieConsent />
    </div>
  );
}

