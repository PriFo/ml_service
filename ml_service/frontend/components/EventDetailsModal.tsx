'use client';

import React, { useState } from 'react';
import styles from './EventDetailsModal.module.css';

interface Event {
  event_id: string;
  event_type: string;
  status: string;
  stage?: string;
  created_at: string;
  completed_at?: string;
  duration_ms?: number;
  error_message?: string;
  input_data?: any;
  output_data?: any;
  [key: string]: any;
}

interface EventDetailsModalProps {
  event: Event;
  isOpen: boolean;
  onClose: () => void;
}

export default function EventDetailsModal({ event, isOpen, onClose }: EventDetailsModalProps) {
  const [selectedRow, setSelectedRow] = useState<number | null>(null);

  if (!isOpen) return null;

  const parseJsonField = (field: any): any => {
    if (!field) return null;
    if (typeof field === 'string') {
      try {
        return JSON.parse(field);
      } catch {
        return field;
      }
    }
    return field;
  };

  const inputData = parseJsonField(event.input_data);
  const outputData = parseJsonField(event.output_data);

  const renderPredictDetails = () => {
    if (event.event_type !== 'predict') return null;

    const processedItems = outputData?.processed_items || [];
    const invalidItems = outputData?.invalid_items || [];
    const stats = outputData?.processing_stats || {};

    return (
      <div className={styles.section}>
        <h3>Детали предсказания</h3>
        
        {stats.total !== undefined && (
          <div className={styles.stats}>
            <div>Всего: {stats.total}</div>
            <div>Обработано: {stats.processed || 0}</div>
            <div>Необработано: {stats.invalid || 0}</div>
            {stats.success_rate !== undefined && (
              <div>Успешность: {(stats.success_rate * 100).toFixed(2)}%</div>
            )}
          </div>
        )}

        {processedItems.length > 0 && (
          <div className={styles.tableSection}>
            <h4>Обработанные данные</h4>
            <table className={styles.dataTable}>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Входные данные</th>
                  <th>Предсказание</th>
                  <th>Уверенность</th>
                </tr>
              </thead>
              <tbody>
                {processedItems.map((item: any, index: number) => (
                  <tr
                    key={index}
                    className={selectedRow === index ? styles.selectedRow : ''}
                    onClick={() => setSelectedRow(selectedRow === index ? null : index)}
                  >
                    <td>{index + 1}</td>
                    <td>
                      <pre className={styles.jsonCell}>
                        {JSON.stringify(item.input || item, null, 2)}
                      </pre>
                    </td>
                    <td>{JSON.stringify(item.prediction)}</td>
                    <td>
                      {item.confidence !== undefined
                        ? `${(item.confidence * 100).toFixed(2)}%`
                        : 'N/A'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            
            {selectedRow !== null && processedItems[selectedRow] && (
              <div className={styles.detailView}>
                <h5>Детали строки {selectedRow + 1}</h5>
                <pre>{JSON.stringify(processedItems[selectedRow], null, 2)}</pre>
              </div>
            )}
          </div>
        )}

        {invalidItems.length > 0 && (
          <div className={styles.tableSection}>
            <h4>Необработанные данные</h4>
            <table className={styles.dataTable}>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Данные</th>
                  <th>Причина</th>
                </tr>
              </thead>
              <tbody>
                {invalidItems.map((item: any, index: number) => (
                  <tr key={index}>
                    <td>{index + 1}</td>
                    <td>
                      <pre className={styles.jsonCell}>
                        {JSON.stringify(item.input || item.data || item, null, 2)}
                      </pre>
                    </td>
                    <td>{item.reason || item.error || 'Неизвестно'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    );
  };

  const renderTrainDetails = () => {
    if (event.event_type !== 'train' && event.event_type !== 'retrain') return null;

    const metrics = outputData?.metrics || outputData;
    const params = inputData?.params || inputData;

    return (
      <div className={styles.section}>
        <h3>Детали обучения</h3>
        
        {metrics && (
          <div className={styles.metricsSection}>
            <h4>Метрики</h4>
            <table className={styles.metricsTable}>
              <tbody>
                {Object.entries(metrics).map(([key, value]) => (
                  <tr key={key}>
                    <td className={styles.metricKey}>{key}</td>
                    <td className={styles.metricValue}>
                      {typeof value === 'number' 
                        ? value.toFixed(4) 
                        : String(value)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {params && (
          <div className={styles.paramsSection}>
            <h4>Параметры обучения</h4>
            <pre className={styles.jsonBlock}>
              {JSON.stringify(params, null, 2)}
            </pre>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className={styles.backdrop} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <h2>Детали события</h2>
          <button className={styles.closeButton} onClick={onClose}>×</button>
        </div>

        <div className={styles.content}>
          <div className={styles.section}>
            <h3>Общая информация</h3>
            <table className={styles.infoTable}>
              <tbody>
                <tr>
                  <td>ID события</td>
                  <td>{event.event_id}</td>
                </tr>
                <tr>
                  <td>Тип</td>
                  <td>{event.event_type}</td>
                </tr>
                <tr>
                  <td>Статус</td>
                  <td>{event.status}</td>
                </tr>
                {event.stage && (
                  <tr>
                    <td>Этап</td>
                    <td>{event.stage}</td>
                  </tr>
                )}
                <tr>
                  <td>Создано</td>
                  <td>{new Date(event.created_at).toLocaleString()}</td>
                </tr>
                {event.completed_at && (
                  <tr>
                    <td>Завершено</td>
                    <td>{new Date(event.completed_at).toLocaleString()}</td>
                  </tr>
                )}
                {event.duration_ms && (
                  <tr>
                    <td>Длительность</td>
                    <td>{event.duration_ms} мс</td>
                  </tr>
                )}
                {event.error_message && (
                  <tr>
                    <td>Ошибка</td>
                    <td className={styles.errorText}>{event.error_message}</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {renderPredictDetails()}
          {renderTrainDetails()}

          {(inputData || outputData) && (
            <div className={styles.section}>
              <h3>Полные данные</h3>
              {inputData && (
                <div className={styles.jsonSection}>
                  <h4>Входные данные</h4>
                  <pre className={styles.jsonBlock}>
                    {JSON.stringify(inputData, null, 2)}
                  </pre>
                </div>
              )}
              {outputData && (
                <div className={styles.jsonSection}>
                  <h4>Выходные данные</h4>
                  <pre className={styles.jsonBlock}>
                    {JSON.stringify(outputData, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>

        <div className={styles.footer}>
          <button className={styles.closeButton} onClick={onClose}>
            Закрыть
          </button>
        </div>
      </div>
    </div>
  );
}

