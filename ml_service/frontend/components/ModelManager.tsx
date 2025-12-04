'use client';

import { useState, useEffect } from 'react';
import { useAppStore } from '@/lib/store';
import { api } from '@/lib/api';
import { useModal } from '@/lib/hooks/useModal';
import Modal from './Modal';
import styles from './ModelManager.module.css';

export default function ModelManager() {
  const { state, dispatch } = useAppStore();
  const { modal, showAlert, showError, showSuccess } = useModal();
  const [activeTab, setActiveTab] = useState<'train' | 'view'>('train');
  const [selectedModelKey, setSelectedModelKey] = useState<string | null>(state.selectedModel);
  const [modelDetails, setModelDetails] = useState<any>(null);
  const [isTraining, setIsTraining] = useState(false);
  const [isLoadingDetails, setIsLoadingDetails] = useState(false);
  const [trainingData, setTrainingData] = useState({
    model_key: '',
    version: '1.0.0',
    target_field: '',
    feature_fields: [] as string[],
    items: [] as any[],
    task_type: 'classification',
    dataset_name: '',
    batch_size: 'auto',
    use_gpu_if_available: false,
    early_stopping: true,
    validation_split: 0.1,
  });

  // Load details when model is selected from ModelSelector
  useEffect(() => {
    if (state.selectedModel && state.selectedModel !== selectedModelKey) {
      setSelectedModelKey(state.selectedModel);
      if (activeTab === 'view') {
        loadModelDetails(state.selectedModel);
      }
    }
  }, [state.selectedModel, activeTab, selectedModelKey]);

  useEffect(() => {
    if (selectedModelKey && activeTab === 'view') {
      loadModelDetails(selectedModelKey);
    } else if (!selectedModelKey && activeTab === 'view') {
      setModelDetails(null);
    }
  }, [selectedModelKey, activeTab]);

  const loadModelDetails = async (modelKey: string) => {
    if (!modelKey) {
      setModelDetails(null);
      return;
    }

    setIsLoadingDetails(true);
    try {
      const details = await api.getModelDetails(modelKey);
      setModelDetails(details);
    } catch (error) {
      console.error('Failed to load model details:', error);
      setModelDetails(null);
      // Show user-friendly error message
      const errorMessage = (error as Error).message;
      if (errorMessage.includes('Unable to connect')) {
        dispatch({ type: 'SET_ERROR', payload: errorMessage });
      } else if (errorMessage.includes('404')) {
        dispatch({ type: 'SET_ERROR', payload: `Model "${modelKey}" not found` });
      } else {
        dispatch({ type: 'SET_ERROR', payload: `Failed to load model details: ${errorMessage}` });
      }
    } finally {
      setIsLoadingDetails(false);
    }
  };

  const handleTrain = async () => {
    if (!trainingData.model_key || !trainingData.target_field || trainingData.items.length === 0) {
      await showError('Пожалуйста, заполните все обязательные поля');
      return;
    }

    setIsTraining(true);
    try {
      const response = await api.trainModel({
        model_key: trainingData.model_key,
        version: trainingData.version,
        task_type: trainingData.task_type,
        target_field: trainingData.target_field,
        feature_fields: trainingData.feature_fields,
        dataset_name: trainingData.dataset_name || `${trainingData.model_key}_dataset`,
        batch_size: trainingData.batch_size,
        use_gpu_if_available: trainingData.use_gpu_if_available,
        early_stopping: trainingData.early_stopping,
        validation_split: trainingData.validation_split,
        items: trainingData.items,
      });
      
      await showSuccess(`Обучение запущено! ID задачи: ${response.job_id}`);
      setTrainingData({
        model_key: '',
        version: '1.0.0',
        target_field: '',
        feature_fields: [],
        items: [],
        task_type: 'classification',
        dataset_name: '',
        batch_size: 'auto',
        use_gpu_if_available: false,
        early_stopping: true,
        validation_split: 0.1,
      });
      
      // Reload models
      const modelsResponse = await api.getModels();
      dispatch({ type: 'SET_MODELS', payload: modelsResponse.models });
    } catch (error) {
      await showError(`Ошибка обучения: ${(error as Error).message}`);
    } finally {
      setIsTraining(false);
    }
  };

  const parseCSV = (csvText: string): any[] => {
    const lines = csvText.split('\n').filter(line => line.trim());
    if (lines.length === 0) return [];
    
    // Simple CSV parser that handles quoted values
    const parseCSVLine = (line: string): string[] => {
      const result: string[] = [];
      let current = '';
      let inQuotes = false;
      
      for (let i = 0; i < line.length; i++) {
        const char = line[i];
        const nextChar = line[i + 1];
        
        if (char === '"') {
          if (inQuotes && nextChar === '"') {
            current += '"';
            i++; // Skip next quote
          } else {
            inQuotes = !inQuotes;
          }
        } else if (char === ',' && !inQuotes) {
          result.push(current.trim());
          current = '';
        } else {
          current += char;
        }
      }
      result.push(current.trim());
      return result;
    };
    
    const headers = parseCSVLine(lines[0]).map(h => h.replace(/^"|"$/g, ''));
    const data: any[] = [];
    
    for (let i = 1; i < lines.length; i++) {
      const values = parseCSVLine(lines[i]).map(v => v.replace(/^"|"$/g, ''));
      if (values.length !== headers.length) continue;
      
      const row: any = {};
      headers.forEach((header, index) => {
        const value = values[index];
        // Try to parse as number
        const numValue = Number(value);
        row[header] = value === '' ? null : (isNaN(numValue) ? value : numValue);
      });
      data.push(row);
    }
    
    return data;
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async (event) => {
      try {
        const text = event.target?.result as string;
        let data: any[] = [];
        
        if (file.name.endsWith('.csv')) {
          data = parseCSV(text);
        } else if (file.name.endsWith('.json')) {
          const parsed = JSON.parse(text);
          if (Array.isArray(parsed)) {
            data = parsed;
          } else {
            await showError('Неверный формат JSON. Ожидается массив JSON.');
            return;
          }
        } else {
          await showError('Неподдерживаемый формат файла. Пожалуйста, загрузите CSV или JSON файл.');
          return;
        }
        
        if (data.length === 0) {
          await showError('Файл пуст или не содержит валидных данных.');
          return;
        }
        
        setTrainingData(prev => ({
          ...prev,
          items: data,
          feature_fields: data.length > 0 ? Object.keys(data[0]).filter(k => k !== prev.target_field) : [],
        }));
      } catch (error) {
        await showError(`Ошибка парсинга файла: ${(error as Error).message}`);
      }
    };
    reader.readAsText(file);
  };

  return (
    <>
      <Modal
        isOpen={modal.isOpen}
        type={modal.type}
        title={modal.title}
        message={modal.message}
        onConfirm={modal.onConfirm}
        onCancel={modal.onCancel}
        confirmText={modal.confirmText}
        cancelText={modal.cancelText}
      />
      <div className={styles.manager}>
        <h2 className={styles.sectionTitle}>Model Management</h2>

      <div className={styles.tabs}>
        <button
          className={`${styles.tab} ${activeTab === 'train' ? styles.active : ''}`}
          onClick={() => setActiveTab('train')}
        >
          Train New Model
        </button>
        <button
          className={`${styles.tab} ${activeTab === 'view' ? styles.active : ''}`}
          onClick={() => setActiveTab('view')}
        >
          View Models
        </button>
      </div>

      <div className={styles.content}>
        {activeTab === 'train' && (
        <div className={styles.trainSection}>
          <h3>Train New Model</h3>
          
          <div className={styles.form}>
            <div className={styles.inputGroup}>
              <label>Model Key</label>
              <input
                type="text"
                value={trainingData.model_key}
                onChange={(e) => setTrainingData(prev => ({ ...prev, model_key: e.target.value }))}
                placeholder="e.g., my_classifier"
              />
            </div>

            <div className={styles.inputGroup}>
              <label>Version</label>
              <input
                type="text"
                value={trainingData.version}
                onChange={(e) => setTrainingData(prev => ({ ...prev, version: e.target.value }))}
                placeholder="e.g., 1.0.0"
              />
            </div>

            <div className={styles.inputGroup}>
              <label>Target Field</label>
              <input
                type="text"
                value={trainingData.target_field}
                onChange={(e) => setTrainingData(prev => ({ ...prev, target_field: e.target.value }))}
                placeholder="e.g., label"
              />
            </div>

            <div className={styles.inputGroup}>
              <label>Task Type</label>
              <select
                value={trainingData.task_type}
                onChange={(e) => setTrainingData(prev => ({ ...prev, task_type: e.target.value }))}
                className={styles.select}
              >
                <option value="classification">Classification</option>
                <option value="regression">Regression</option>
              </select>
            </div>

            <div className={styles.inputGroup}>
              <label>Dataset Name</label>
              <input
                type="text"
                value={trainingData.dataset_name}
                onChange={(e) => setTrainingData(prev => ({ ...prev, dataset_name: e.target.value }))}
                placeholder="Auto-generated if empty"
              />
            </div>

            <div className={styles.inputGroup}>
              <label>Batch Size</label>
              <select
                value={trainingData.batch_size}
                onChange={(e) => setTrainingData(prev => ({ ...prev, batch_size: e.target.value }))}
                className={styles.select}
              >
                <option value="auto">Auto</option>
                <option value="32">32</option>
                <option value="64">64</option>
                <option value="128">128</option>
                <option value="256">256</option>
              </select>
            </div>

            <div className={styles.inputGroup}>
              <label>Validation Split</label>
              <input
                type="number"
                min="0"
                max="1"
                step="0.1"
                value={trainingData.validation_split}
                onChange={(e) => setTrainingData(prev => ({ ...prev, validation_split: parseFloat(e.target.value) || 0.1 }))}
              />
            </div>

            <div className={styles.inputGroup}>
              <label className={styles.checkboxLabel}>
                <input
                  type="checkbox"
                  checked={trainingData.use_gpu_if_available}
                  onChange={(e) => setTrainingData(prev => ({ ...prev, use_gpu_if_available: e.target.checked }))}
                />
                Use GPU if available
              </label>
            </div>

            <div className={styles.inputGroup}>
              <label className={styles.checkboxLabel}>
                <input
                  type="checkbox"
                  checked={trainingData.early_stopping}
                  onChange={(e) => setTrainingData(prev => ({ ...prev, early_stopping: e.target.checked }))}
                />
                Enable Early Stopping
              </label>
            </div>

            <div className={styles.inputGroup}>
              <label>Upload Dataset (CSV or JSON)</label>
              <input
                type="file"
                accept=".csv,.json"
                onChange={handleFileUpload}
              />
              {trainingData.items.length > 0 && (
                <p className={styles.info}>Loaded {trainingData.items.length} items</p>
              )}
            </div>

            <button
              onClick={handleTrain}
              disabled={isTraining}
              className={styles.trainButton}
            >
              {isTraining ? 'Training...' : 'Start Training'}
            </button>
          </div>
        </div>
        )}

        {activeTab === 'view' && (
          <div className={styles.detailsSection}>
            <div className={styles.modelSelector}>
              <label>Select Model:</label>
              <select
                value={selectedModelKey || ''}
                onChange={(e) => {
                  const key = e.target.value || null;
                  setSelectedModelKey(key);
                  if (key) {
                    dispatch({ type: 'SELECT_MODEL', payload: key });
                    loadModelDetails(key);
                  }
                }}
                className={styles.select}
              >
                <option value="">-- Select a model --</option>
                {state.models.map(model => (
                  <option key={model.model_key} value={model.model_key}>
                    {model.model_key} (v{model.active_version})
                  </option>
                ))}
              </select>
            </div>

            {isLoadingDetails ? (
              <div className={styles.loading}>Loading model details...</div>
            ) : modelDetails ? (
              <>
                <h3>Model Details: {selectedModelKey}</h3>
                <div className={styles.modelInfo}>
                  <p><strong>Current Version:</strong> {modelDetails.current_version}</p>
                  <p><strong>Total Versions:</strong> {modelDetails.versions.length}</p>
                </div>
                
                <div className={styles.versions}>
                  <h4>All Versions</h4>
                  {modelDetails.versions.map((v: any, i: number) => (
                    <div key={i} className={styles.versionCard}>
                      <div className={styles.versionHeader}>
                        <span className={styles.versionNumber}>v{v.version}</span>
                        <span className={`${styles.statusBadge} ${v.status === 'active' ? styles.active : ''}`}>
                          {v.status}
                        </span>
                      </div>
                      <div className={styles.versionDetails}>
                        <p><strong>Accuracy:</strong> {v.accuracy !== null && v.accuracy !== undefined ? (v.accuracy * 100).toFixed(2) + '%' : 'N/A'}</p>
                        <p><strong>Task Type:</strong> {v.task_type || 'N/A'}</p>
                        <p><strong>Target Field:</strong> {v.target_field || 'N/A'}</p>
                        <p><strong>Feature Fields:</strong> {v.feature_fields?.join(', ') || 'N/A'}</p>
                        <p><strong>Created:</strong> {v.created_at ? new Date(v.created_at).toLocaleString() : 'N/A'}</p>
                        <p><strong>Last Trained:</strong> {v.last_trained ? new Date(v.last_trained).toLocaleString() : 'N/A'}</p>
                      </div>
                    </div>
                  ))}
                </div>

                {modelDetails.recent_jobs && modelDetails.recent_jobs.length > 0 && (
                  <div className={styles.recentJobs}>
                    <h4>Recent Training Jobs</h4>
                    {modelDetails.recent_jobs.map((job: any, i: number) => (
                      <div key={i} className={styles.jobCard}>
                        <p><strong>Job ID:</strong> {job.job_id}</p>
                        <p><strong>Status:</strong> {job.status}</p>
                        {job.created_at && (
                          <p><strong>Created:</strong> {new Date(job.created_at).toLocaleString()}</p>
                        )}
                        {job.error_message && (
                          <p className={styles.error}><strong>Error:</strong> {job.error_message}</p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </>
            ) : selectedModelKey ? (
              <div className={styles.empty}>No details available for this model</div>
            ) : (
              <div className={styles.empty}>Please select a model to view details</div>
            )}
          </div>
        )}
      </div>
    </>
  );
}

