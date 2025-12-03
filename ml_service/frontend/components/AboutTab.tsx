'use client';

import React from 'react';
import styles from './AboutTab.module.css';

export default function AboutTab() {
  const apiUrl = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_URL || window.location.origin.replace(':6565', ':8085'))
    : 'http://localhost:8085';
  
  const docsUrl = `${apiUrl}/docs`;
  const redocUrl = `${apiUrl}/redoc`;

  return (
    <div className={styles.aboutTab}>
      <div className={styles.header}>
        <h1 className={styles.title}>О проекте ML Service</h1>
        <p className={styles.version}>Версия 0.10.0</p>
      </div>

      <div className={styles.content}>
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>Описание</h2>
          <p className={styles.description}>
            ML Service — это production-grade платформа машинного обучения с поддержкой GPU, 
            мониторингом дрифта данных и real-time дашбордом. Система предназначена для обучения, 
            развертывания и мониторинга ML моделей с автоматическим обнаружением изменений в данных 
            и переобучением моделей.
          </p>
        </section>

        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>Основные возможности</h2>
          <ul className={styles.featuresList}>
            <li>✅ MLPClassifier с адаптивной архитектурой</li>
            <li>✅ Поддержка GPU (cuML, опционально)</li>
            <li>✅ Обнаружение дрифта данных (PSI + Jensen-Shannon divergence)</li>
            <li>✅ Автоматическое переобучение при обнаружении дрифта</li>
            <li>✅ Real-time дашборд (Next.js 15 + React 19)</li>
            <li>✅ Асинхронные задачи (обучение и предсказания)</li>
            <li>✅ Универсальная система отслеживания задач (jobs)</li>
            <li>✅ Мониторинг событий с метаданными (IP, User-Agent)</li>
            <li>✅ WebSocket для real-time обновлений</li>
            <li>✅ GDPR compliant (cookie consent)</li>
            <li>✅ Экспорт результатов предсказаний в JSON/CSV</li>
            <li>✅ Графический интерфейс для всех операций</li>
          </ul>
        </section>

        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>Технологический стек</h2>
          <div className={styles.techStack}>
            <div className={styles.techCategory}>
              <h3 className={styles.techTitle}>Backend</h3>
              <ul className={styles.techList}>
                <li>Python 3.9+</li>
                <li>FastAPI</li>
                <li>SQLite (с WAL режимом)</li>
                <li>scikit-learn</li>
                <li>cuML (опционально, для GPU)</li>
              </ul>
            </div>
            <div className={styles.techCategory}>
              <h3 className={styles.techTitle}>Frontend</h3>
              <ul className={styles.techList}>
                <li>Next.js 15</li>
                <li>React 19</li>
                <li>TypeScript</li>
                <li>CSS-first подход (zero-dependency)</li>
              </ul>
            </div>
            <div className={styles.techCategory}>
              <h3 className={styles.techTitle}>Инфраструктура</h3>
              <ul className={styles.techList}>
                <li>Docker & Docker Compose</li>
                <li>WebSocket для real-time коммуникации</li>
                <li>SSL/HTTPS поддержка</li>
              </ul>
            </div>
          </div>
        </section>

        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>Документация API</h2>
          <div className={styles.docsLinks}>
            <a
              href={docsUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={styles.docLink}
            >
              <span className={styles.docIcon}>📚</span>
              <div className={styles.docContent}>
                <h3 className={styles.docTitle}>Swagger UI</h3>
                <p className={styles.docDescription}>
                  Интерактивная документация API с возможностью тестирования endpoints
                </p>
              </div>
            </a>
            <a
              href={redocUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={styles.docLink}
            >
              <span className={styles.docIcon}>📖</span>
              <div className={styles.docContent}>
                <h3 className={styles.docTitle}>ReDoc</h3>
                <p className={styles.docDescription}>
                  Альтернативная документация API в формате ReDoc
                </p>
              </div>
            </a>
          </div>
          <p className={styles.docsNote}>
            Примечание: Документация API доступна только для аутентифицированных пользователей.
          </p>
        </section>

        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>Контакты</h2>
          <div className={styles.contactInfo}>
            <div className={styles.contactItem}>
              <span className={styles.contactLabel}>Разработчик:</span>
              <a
                href="https://t.me/pr1fo"
                target="_blank"
                rel="noopener noreferrer"
                className={styles.contactLink}
              >
                @pr1fo
              </a>
            </div>
          </div>
        </section>

        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>Порты и доступ</h2>
          <div className={styles.portsInfo}>
            <div className={styles.portItem}>
              <span className={styles.portLabel}>Backend API:</span>
              <span className={styles.portValue}>8085</span>
            </div>
            <div className={styles.portItem}>
              <span className={styles.portLabel}>Frontend:</span>
              <span className={styles.portValue}>6565</span>
            </div>
            <div className={styles.portItem}>
              <span className={styles.portLabel}>WebSocket:</span>
              <span className={styles.portValue}>ws://localhost:8085/ws</span>
            </div>
          </div>
        </section>

        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>Лицензия</h2>
          <p className={styles.license}>Proprietary</p>
        </section>
      </div>
    </div>
  );
}

