'use client';

import React, { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import styles from './ModelsTab.module.css';

interface ModelsTabProps {
  onNavigateToTraining?: () => void;
}

interface Model {
  model_key: string;
  versions: string[];
  active_version: string;
  accuracy?: number;
}

export default function ModelsTab({ onNavigateToTraining }: ModelsTabProps = {}) {
  const [models, setModels] = useState<Model[]>([]);
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const [selectedVersion, setSelectedVersion] = useState<string | null>(null);

  useEffect(() => {
    loadModels();
  }, []);

  const loadModels = async () => {
    try {
      const response = await api.getModels();
      setModels(response.models || []);
    } catch (error) {
      console.error('Failed to load models:', error);
    }
  };

  const selectedModelData = models.find((m) => m.model_key === selectedModel);

  return (
    <div className={styles.modelsTab}>
      <div className={styles.panel1}>
        <h3>Models</h3>
        {models.map((model) => (
          <div
            key={model.model_key}
            className={`${styles.modelItem} ${
              selectedModel === model.model_key ? styles.selected : ''
            }`}
            onClick={() => {
              setSelectedModel(model.model_key);
              setSelectedVersion(null);
            }}
          >
            {model.model_key}
          </div>
        ))}
        <button 
          className={styles.newButton}
          onClick={() => {
            if (onNavigateToTraining) {
              onNavigateToTraining();
            } else {
              // Fallback: try to find Dashboard and switch tab
              const event = new CustomEvent('navigate', { detail: { tab: 'training' } });
              window.dispatchEvent(event);
            }
          }}
        >
          + New Model
        </button>
      </div>

      {selectedModelData && (
        <div className={styles.panel2}>
          <h3>Versions</h3>
          {selectedModelData.versions.map((version) => (
            <div
              key={version}
              className={`${styles.versionItem} ${
                selectedVersion === version ? styles.selected : ''
              }`}
              onClick={() => setSelectedVersion(version)}
            >
              {version}
              {version === selectedModelData.active_version && (
                <span className={styles.activeBadge}>*active*</span>
              )}
            </div>
          ))}
          <button className={styles.newButton}>+ New Version</button>
        </div>
      )}

      {selectedModelData && selectedVersion && (
        <div className={styles.panel3}>
          <h3>Model Details</h3>
          <div className={styles.metrics}>
            <h4>Metrics:</h4>
            <div>Accuracy: {selectedModelData.accuracy || 'N/A'}</div>
          </div>
          <div className={styles.actions}>
            <button onClick={() => {
              // Navigate to predict tab with selected model
              window.location.hash = `predict?model=${selectedModel}&version=${selectedVersion}`;
            }}>Use for Prediction</button>
            <button onClick={() => {
              // Navigate to training tab for retraining
              window.location.hash = 'training';
            }}>Retrain Version</button>
            <button onClick={async () => {
              // Download model (would need API endpoint)
              console.log('Download model:', selectedModel, selectedVersion);
            }}>Download Model</button>
            <button 
              className={styles.deleteButton}
              onClick={async () => {
                if (!confirm(`Are you sure you want to delete model "${selectedModel}"? This will delete all versions and related data.`)) {
                  return;
                }
                try {
                  await api.deleteModel(selectedModel, true);
                  alert('Model deleted successfully');
                  loadModels();
                  setSelectedModel(null);
                  setSelectedVersion(null);
                } catch (error) {
                  console.error('Failed to delete model:', error);
                  alert(`Failed to delete model: ${(error as Error).message}`);
                }
              }}
            >Delete Model</button>
          </div>
        </div>
      )}
    </div>
  );
}

