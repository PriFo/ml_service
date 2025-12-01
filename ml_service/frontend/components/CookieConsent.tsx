'use client';

import { useState, useEffect } from 'react';
import { useAppStore } from '@/lib/store';
import { saveConsent, getConsent, Consent } from '@/lib/consent';
import styles from './CookieConsent.module.css';

export default function CookieConsent() {
  const { state, dispatch } = useAppStore();
  const [showDetails, setShowDetails] = useState(false);
  const [consent, setConsent] = useState<Consent>({
    essential: true,
    analytics: false,
    preferences: false,
    timestamp: Date.now(),
  });

  useEffect(() => {
    const existing = getConsent();
    if (existing) {
      dispatch({ type: 'SET_COOKIE_CONSENT', payload: existing });
    } else {
      // Show consent banner if not set
      dispatch({ type: 'SET_COOKIE_CONSENT', payload: null });
    }
  }, [dispatch]);

  const handleSave = () => {
    saveConsent(consent);
    dispatch({ type: 'SET_COOKIE_CONSENT', payload: consent });
  };

  if (state.cookieConsent) {
    return null; // Consent already given
  }

  return (
    <div className={styles.container}>
      <div className={styles.banner}>
        <div className={styles.content}>
          <h3 className={styles.title}>Использование cookies</h3>
          <p className={styles.text}>
            Мы используем cookies для улучшения работы сайта. Вы можете выбрать,
            какие типы cookies разрешить.
          </p>
          
          {showDetails && (
            <div className={styles.details}>
              <label className={styles.checkbox}>
                <input
                  type="checkbox"
                  checked={consent.essential}
                  disabled
                />
                <span>Обязательные (всегда включены)</span>
              </label>
              
              <label className={styles.checkbox}>
                <input
                  type="checkbox"
                  checked={consent.analytics}
                  onChange={(e) =>
                    setConsent({ ...consent, analytics: e.target.checked })
                  }
                />
                <span>Аналитика</span>
              </label>
              
              <label className={styles.checkbox}>
                <input
                  type="checkbox"
                  checked={consent.preferences}
                  onChange={(e) =>
                    setConsent({ ...consent, preferences: e.target.checked })
                  }
                />
                <span>Настройки (для сохранения темы)</span>
              </label>
            </div>
          )}
          
          <div className={styles.actions}>
            <button
              onClick={() => setShowDetails(!showDetails)}
              className={styles.detailsButton}
            >
              {showDetails ? 'Скрыть детали' : 'Показать детали'}
            </button>
            <button onClick={handleSave} className={styles.saveButton}>
              Сохранить
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

