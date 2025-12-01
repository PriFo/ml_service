'use client';

import { useAppStore } from '@/lib/store';
import styles from './ModelSelector.module.css';

export default function ModelSelector() {
  const { state, dispatch } = useAppStore();

  const handleSelect = (modelKey: string) => {
    dispatch({ type: 'SELECT_MODEL', payload: modelKey });
  };

  return (
    <div className={styles.container}>
      <h2 className={styles.title}>Models</h2>
      
      {state.models.length === 0 ? (
        <p className={styles.empty}>No models available</p>
      ) : (
        <div className={styles.list}>
          {state.models.map(model => (
            <div
              key={model.model_key}
              className={`${styles.item} ${
                state.selectedModel === model.model_key ? styles.selected : ''
              }`}
              onClick={() => handleSelect(model.model_key)}
            >
              <h3 className={styles.modelKey}>{model.model_key}</h3>
              <p className={styles.version}>Version: {model.active_version}</p>
              {model.accuracy !== null && model.accuracy !== undefined && (
                <p className={styles.accuracy}>
                  Accuracy: {(model.accuracy * 100).toFixed(2)}%
                </p>
              )}
              {model.last_trained && (
                <p className={styles.date}>
                  Trained: {new Date(model.last_trained).toLocaleDateString()}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

