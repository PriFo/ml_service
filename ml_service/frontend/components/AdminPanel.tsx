'use client';

import { useState } from 'react';
import { useAppStore } from '@/lib/store';
import { api } from '@/lib/api';
import styles from './AdminPanel.module.css';

export default function AdminPanel() {
  const { state } = useAppStore();
  const [isOpen, setIsOpen] = useState(false);

  if (!state.isAuthenticated) {
    return null;
  }

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8085';
  const docsUrl = `${apiUrl}/docs`;
  const redocUrl = `${apiUrl}/redoc`;

  return (
    <div className={styles.adminPanel}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={styles.toggleButton}
      >
        {isOpen ? '▼' : '▶'} Admin Tools
      </button>

      {isOpen && (
        <div className={styles.panelContent}>
          <h3>Administrator Tools</h3>
          
          <div className={styles.tools}>
            <a
              href={docsUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={styles.toolLink}
            >
              📚 API Documentation (Swagger)
            </a>
            
            <a
              href={redocUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={styles.toolLink}
            >
              📖 API Documentation (ReDoc)
            </a>
            
            <div className={styles.info}>
              <p><strong>Note:</strong> API documentation is only accessible to authenticated administrators.</p>
              <p>These pages provide interactive documentation for all API endpoints, including:</p>
              <ul>
                <li>Request/response schemas</li>
                <li>Try-it-out functionality</li>
                <li>Authentication requirements</li>
                <li>Error codes and messages</li>
              </ul>
            </div>

            <div className={styles.dangerZone}>
              <h4>Danger Zone</h4>
              <button
                className={styles.dangerButton}
                onClick={async () => {
                  const backup = confirm('Create backup before recreating database?');
                  const restore = backup && confirm('Restore data from backup after recreation?');
                  
                  if (!confirm(
                    `WARNING: This will ${restore ? 'recreate' : 'DELETE ALL DATA'} in the database!\n\n` +
                    `Are you absolutely sure you want to proceed?`
                  )) {
                    return;
                  }

                  try {
                    const result = await api.recreateDatabase(backup, restore);
                    alert(
                      `Database recreated successfully!\n` +
                      (result.backup_path ? `Backup saved at: ${result.backup_path}` : '')
                    );
                    // Reload page to refresh data
                    window.location.reload();
                  } catch (error) {
                    console.error('Failed to recreate database:', error);
                    alert(`Failed to recreate database: ${(error as Error).message}`);
                  }
                }}
              >
                🔄 Recreate Database
              </button>
              <p className={styles.warning}>
                This will delete all data and recreate the database schema. 
                Make sure to create a backup first!
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

