'use client';

import React, { useState } from 'react';
import { useJob } from '@/lib/hooks/useJob';
import { api } from '@/lib/api';
import ProgressBar from './ProgressBar';
import styles from './TrainingTab.module.css';

export default function TrainingTab() {
  const [submitted, setSubmitted] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    modelName: '',
    version: '',
    taskType: 'classification',
    dataset: null as File | null,
    datasetName: '',
    items: [] as any[],
    features: [] as string[],
    target: '',
    batchSize: 'auto',
    useGpu: false,
    earlyStopping: true,
    validationSplit: 0.1,
    hiddenLayers: '', // Optional: e.g., "512,256,128"
    maxIter: 500,
    learningRate: 0.001,
    alpha: 0.0001,
  });

  const { job, loading } = useJob(jobId);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setFormData({ ...formData, dataset: file, datasetName: file.name });

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const text = event.target?.result as string;
        let data: any[] = [];

        if (file.name.endsWith('.json')) {
          const json = JSON.parse(text);
          data = Array.isArray(json) ? json : json.data || json.items || [];
        } else if (file.name.endsWith('.csv')) {
          // Simple CSV parsing
          const lines = text.split('\n').filter(line => line.trim());
          if (lines.length < 2) {
            setError('CSV file must have at least a header and one data row');
            return;
          }
          const headers = lines[0].split(',').map(h => h.trim().replace(/^"|"$/g, ''));
          data = lines.slice(1).map(line => {
            const values = line.split(',').map(v => v.trim().replace(/^"|"$/g, ''));
            const row: any = {};
            headers.forEach((header, index) => {
              row[header] = values[index] || null;
            });
            return row;
          });
        }

        if (data.length === 0) {
          setError('Dataset is empty or could not be parsed');
          return;
        }

        // Auto-detect available fields from data
        const availableFields = data.length > 0 ? Object.keys(data[0]) : [];
        
        setFormData({ 
          ...formData, 
          items: data, 
          dataset: file, 
          datasetName: file.name,
          // Auto-fill features if not set (all fields except target if target is set)
          features: formData.features.length === 0 && formData.target 
            ? availableFields.filter(f => f !== formData.target)
            : formData.features
        });
        setError(null);
      } catch (err) {
        setError(`Failed to parse file: ${(err as Error).message}`);
      }
    };
    reader.readAsText(file);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validation
    if (!formData.modelName.trim()) {
      setError('Model name is required');
      return;
    }
    if (!formData.version.trim()) {
      setError('Version is required');
      return;
    }
    if (formData.items.length === 0) {
      setError('Please upload a dataset file');
      return;
    }
    if (!formData.target.trim()) {
      setError('Target field is required');
      return;
    }

    try {
      // Prepare request - feature_fields is optional, will be auto-detected if empty
      const requestData: any = {
        model_key: formData.modelName,
        version: formData.version,
        task_type: formData.taskType,
        target_field: formData.target,
        dataset_name: formData.datasetName || 'uploaded_dataset',
        items: formData.items,
        batch_size: formData.batchSize,
        use_gpu_if_available: formData.useGpu,
        early_stopping: formData.earlyStopping,
        validation_split: formData.validationSplit,
      };
      
      // Only include feature_fields if explicitly provided
      if (formData.features.length > 0) {
        requestData.feature_fields = formData.features;
      }
      
      // Include model parameters if provided
      if (formData.hiddenLayers.trim()) {
        requestData.hidden_layers = formData.hiddenLayers;
      }
      if (formData.maxIter && formData.maxIter !== 500) {
        requestData.max_iter = formData.maxIter;
      }
      if (formData.learningRate && formData.learningRate !== 0.001) {
        requestData.learning_rate_init = formData.learningRate;
      }
      if (formData.alpha && formData.alpha !== 0.0001) {
        requestData.alpha = formData.alpha;
      }
      
      const response = await api.trainModel(requestData);
      setJobId(response.job_id);
      setSubmitted(true);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to start training';
      setError(errorMessage);
      console.error('Failed to start training:', err);
    }
  };

  if (submitted && jobId) {
    return (
      <div className={styles.trainingTab}>
        <div className={styles.disabledForm}>
          <form>
            {/* Disabled form fields */}
          </form>
        </div>
        <div className={styles.statusPanel}>
          <h3>Training Status</h3>
          {job && (
            <>
              <div>Status: {job.status}</div>
              <div>Job: {job.job_id}</div>
              <ProgressBar
                progress={job.progress?.percent || 0}
                status={job.status as any}
              />
              {job.status === 'completed' && job.metrics && (
                <div className={styles.metrics}>
                  <h4>Metrics:</h4>
                  <pre>{JSON.stringify(job.metrics, null, 2)}</pre>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className={styles.trainingTab}>
      <form onSubmit={handleSubmit} className={styles.trainingForm}>
        <h2 className={styles.formTitle}>Train New Model</h2>
        {error && <div className={styles.error}>{error}</div>}
        
        <div className={styles.framesContainer}>
          {/* Frame 1: Model Information */}
          <div className={styles.frame}>
            <div className={styles.frameHeader}>
              <h3>Model Information</h3>
            </div>
            <div className={styles.frameContent}>
              <div className={styles.formGroup}>
                <label>Model Name:</label>
                <input
                  type="text"
                  value={formData.modelName}
                  onChange={(e) =>
                    setFormData({ ...formData, modelName: e.target.value })
                  }
                  placeholder="e.g., my_classifier"
                  required
                />
              </div>
              
              <div className={styles.formGroup}>
                <label>Version:</label>
                <input
                  type="text"
                  value={formData.version}
                  onChange={(e) =>
                    setFormData({ ...formData, version: e.target.value })
                  }
                  placeholder="v1.0.0"
                  required
                />
              </div>

              <div className={styles.formGroup}>
                <label>Task Type:</label>
                <select
                  value={formData.taskType}
                  onChange={(e) =>
                    setFormData({ ...formData, taskType: e.target.value })
                  }
                >
                  <option value="classification">Classification</option>
                  <option value="regression">Regression</option>
                </select>
              </div>
            </div>
          </div>

          {/* Frame 2: Training Data */}
          <div className={styles.frame}>
            <div className={styles.frameHeader}>
              <h3>Training Data</h3>
            </div>
            <div className={styles.frameContent}>
              <div className={styles.formGroup}>
                <label>Dataset File (JSON or CSV):</label>
                <input
                  type="file"
                  accept=".json,.csv"
                  onChange={handleFileUpload}
                  required
                />
                {formData.datasetName && (
                  <div className={styles.info}>
                    ✓ Loaded: {formData.datasetName} ({formData.items.length} items)
                  </div>
                )}
              </div>

              <div className={styles.formGroup}>
                <label>Target Field:</label>
                <input
                  type="text"
                  value={formData.target}
                  onChange={(e) =>
                    setFormData({ ...formData, target: e.target.value })
                  }
                  placeholder="Column name for target"
                  required
                />
              </div>

              <div className={styles.formGroup}>
                <label>Feature Fields (optional - auto-detected if empty):</label>
                <input
                  type="text"
                  value={formData.features.join(', ')}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      features: e.target.value.split(',').map(f => f.trim()).filter(f => f),
                    })
                  }
                  placeholder="Leave empty to use all fields except target"
                />
                {formData.items.length > 0 && (
                  <div className={styles.info}>
                    Available fields: {Object.keys(formData.items[0] || {}).join(', ')}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Frame 3: Model Settings */}
          <div className={styles.frame}>
            <div className={styles.frameHeader}>
              <h3>Model Settings</h3>
            </div>
            <div className={styles.frameContent}>
              <div className={styles.formGroup}>
                <label>Hidden Layers (optional, e.g., "512,256,128"):</label>
                <input
                  type="text"
                  value={formData.hiddenLayers}
                  onChange={(e) =>
                    setFormData({ ...formData, hiddenLayers: e.target.value })
                  }
                  placeholder="Auto-detected based on dataset size"
                />
                <div className={styles.info}>
                  Leave empty for automatic configuration
                </div>
              </div>

              <div className={styles.formGroup}>
                <label>Batch Size:</label>
                <select
                  value={formData.batchSize}
                  onChange={(e) =>
                    setFormData({ ...formData, batchSize: e.target.value })
                  }
                >
                  <option value="auto">Auto</option>
                  <option value="32">32</option>
                  <option value="64">64</option>
                  <option value="128">128</option>
                  <option value="256">256</option>
                </select>
              </div>

              <div className={styles.formGroup}>
                <label>Max Iterations:</label>
                <input
                  type="number"
                  min="1"
                  max="10000"
                  value={formData.maxIter}
                  onChange={(e) =>
                    setFormData({ ...formData, maxIter: parseInt(e.target.value) || 500 })
                  }
                />
              </div>

              <div className={styles.formGroup}>
                <label>Learning Rate:</label>
                <input
                  type="number"
                  min="0.0001"
                  max="1"
                  step="0.0001"
                  value={formData.learningRate}
                  onChange={(e) =>
                    setFormData({ ...formData, learningRate: parseFloat(e.target.value) || 0.001 })
                  }
                />
              </div>

              <div className={styles.formGroup}>
                <label>Regularization (Alpha):</label>
                <input
                  type="number"
                  min="0"
                  max="1"
                  step="0.0001"
                  value={formData.alpha}
                  onChange={(e) =>
                    setFormData({ ...formData, alpha: parseFloat(e.target.value) || 0.0001 })
                  }
                />
              </div>

              <div className={styles.formGroup}>
                <label>Validation Split:</label>
                <input
                  type="number"
                  min="0"
                  max="0.5"
                  step="0.01"
                  value={formData.validationSplit}
                  onChange={(e) =>
                    setFormData({ ...formData, validationSplit: parseFloat(e.target.value) || 0.1 })
                  }
                />
                <div className={styles.info}>
                  Fraction of data to use for validation (0.0 - 0.5)
                </div>
              </div>

              <div className={styles.checkboxGroup}>
                <label className={styles.checkboxLabel}>
                  <input
                    type="checkbox"
                    checked={formData.useGpu}
                    onChange={(e) =>
                      setFormData({ ...formData, useGpu: e.target.checked })
                    }
                  />
                  <span>Use GPU if available</span>
                </label>
              </div>

              <div className={styles.checkboxGroup}>
                <label className={styles.checkboxLabel}>
                  <input
                    type="checkbox"
                    checked={formData.earlyStopping}
                    onChange={(e) =>
                      setFormData({ ...formData, earlyStopping: e.target.checked })
                    }
                  />
                  <span>Early Stopping</span>
                </label>
              </div>
            </div>
          </div>
        </div>

        <div className={styles.submitContainer}>
          <button 
            type="submit" 
            className={styles.submitButton}
            disabled={formData.items.length === 0}
          >
            Train Model
          </button>
        </div>
      </form>
    </div>
  );
}

