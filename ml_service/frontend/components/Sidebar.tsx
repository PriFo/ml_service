'use client';

import { useState } from 'react';
import { useAppStore } from '@/lib/store';
import ThemeDropdown from './ThemeDropdown';
import styles from './Sidebar.module.css';

type TabType = 'overview' | 'models' | 'predict' | 'training' | 'jobs' | 'events';

interface SidebarProps {
  activeTab: TabType;
  onTabChange: (tab: TabType) => void;
}

export default function Sidebar({ activeTab, onTabChange }: SidebarProps) {
  const { state, dispatch } = useAppStore();
  const [isCollapsed, setIsCollapsed] = useState(false);

  const menuItems: Array<{ id: TabType; label: string; icon: string }> = [
    { id: 'overview', label: 'Overview', icon: 'dashboard' },
    { id: 'models', label: 'Models', icon: 'model' },
    { id: 'predict', label: 'Predict', icon: 'predict' },
    { id: 'training', label: 'Training', icon: 'training' },
    { id: 'jobs', label: 'Jobs', icon: 'jobs' },
    { id: 'events', label: 'Events', icon: 'events' },
  ];

  const handleLogout = () => {
    dispatch({ type: 'LOGOUT' });
    // Reload page to reset all state
    if (typeof window !== 'undefined') {
      window.location.href = '/';
    }
  };

  return (
    <aside className={`${styles.sidebar} ${isCollapsed ? styles.collapsed : ''}`}>
      <div className={styles.sidebarHeader}>
        <h1 className={styles.logo}>ML Service</h1>
        <button
          className={styles.collapseButton}
          onClick={() => setIsCollapsed(!isCollapsed)}
          aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {isCollapsed ? '→' : '←'}
        </button>
      </div>

      <nav className={styles.nav}>
        {menuItems.map(item => (
          <button
            key={item.id}
            className={`${styles.navItem} ${activeTab === item.id ? styles.active : ''}`}
            onClick={() => onTabChange(item.id)}
            title={isCollapsed ? item.label : undefined}
          >
            <span className={styles.navIcon}>{getIcon(item.icon)}</span>
            {!isCollapsed && <span className={styles.navLabel}>{item.label}</span>}
          </button>
        ))}
      </nav>

      <div className={styles.sidebarFooter}>
        <ThemeDropdown />
        {state.isAuthenticated && (
          <button
            onClick={handleLogout}
            className={styles.logoutButton}
            title={isCollapsed ? 'Logout' : undefined}
          >
            <span className={styles.navIcon}>{getIcon('logout')}</span>
            {!isCollapsed && <span className={styles.navLabel}>Logout</span>}
          </button>
        )}
      </div>
    </aside>
  );
}

function getIcon(iconName: string): string {
  const icons: Record<string, string> = {
    dashboard: '▣',
    model: '⬟',
    predict: '▶',
    training: '🎓',
    jobs: '⚙',
    events: '⚡',
    logout: '◄',
  };
  return icons[iconName] || '•';
}
