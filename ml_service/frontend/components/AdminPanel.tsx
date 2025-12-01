'use client';

import { useState } from 'react';
import { useAppStore } from '@/lib/store';
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
          </div>
        </div>
      )}
    </div>
  );
}

