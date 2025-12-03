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
import OverviewTab from './OverviewTab';
import EventsTab from './EventsTab';
import JobsTab from './JobsTab';
import TrainingTab from './TrainingTab';
import PredictTab from './PredictTab';
import ModelsTab from './ModelsTab';
import UsersTab from './UsersTab';
import ProfileTab from './ProfileTab';
import AboutTab from './AboutTab';
import styles from './Dashboard.module.css';

type TabType = 'overview' | 'models' | 'predict' | 'jobs' | 'events' | 'training' | 'users' | 'profile' | 'about';

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
            <OverviewTab />
          )}

          {activeTab === 'models' && (
            <ModelsTab onNavigateToTraining={() => setActiveTab('training')} />
          )}

          {activeTab === 'predict' && (
            <PredictTab />
          )}

          {activeTab === 'training' && (
            <TrainingTab />
          )}

          {activeTab === 'jobs' && (
            <JobsTab />
          )}

          {activeTab === 'events' && (
            <EventsTab />
          )}

          {activeTab === 'users' && (
            <UsersTab />
          )}

          {activeTab === 'profile' && (
            <ProfileTab />
          )}

          {activeTab === 'about' && (
            <AboutTab />
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

